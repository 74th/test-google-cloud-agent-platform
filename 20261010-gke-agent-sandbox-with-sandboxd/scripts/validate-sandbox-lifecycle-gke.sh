#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${GKE_CLUSTER_NAME:?Set GKE_CLUSTER_NAME explicitly}"

expected_context="gke_${GKE_PROJECT_ID}_${GKE_LOCATION}_${GKE_CLUSTER_NAME}"
current_context="$(kubectl config current-context)"
if [[ "${current_context}" != "${expected_context}" ]]; then
  printf 'Refusing sandbox lifecycle validation: current context %s, expected %s\n' \
    "${current_context}" "${expected_context}" >&2
  exit 2
fi

namespace="session-sandboxes"
sandbox="sandboxd-smoke"
pvc="workspace-sandboxd-smoke"
kubectl get sandbox "${sandbox}" -n "${namespace}" -o jsonpath='{.metadata.labels.app\.kubernetes\.io/component}' | grep -Fxq smoke-test
sandbox_uid="$(kubectl get sandbox "${sandbox}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
pod_uid_before="$(kubectl get pod "${sandbox}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
pvc_uid_before="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
pv="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.spec.volumeName}')"
disk_handle="$(kubectl get pv "${pv}" -o jsonpath='{.spec.csi.volumeHandle}')"
disk="${disk_handle##*/disks/}"
zone="$(kubectl get pv "${pv}" -o jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]}')"
reclaim="$(kubectl get pv "${pv}" -o jsonpath='{.spec.persistentVolumeReclaimPolicy}')"
owner_uid="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.metadata.ownerReferences[?(@.kind=="Sandbox")].uid}')"

if [[ "${sandbox_uid}" != "${owner_uid}" || "${reclaim}" != "Delete" || -z "${disk}" ]]; then
  printf 'Unexpected sandbox/PVC ownership or PV reclaim configuration; refusing destructive lifecycle check\n' >&2
  exit 3
fi
before_content="$(kubectl exec "${sandbox}" -n "${namespace}" -- /bin/cat /workspace/management-runner.txt)"
if [[ "${before_content}" != "written-by-rest-read-by-grpc" ]]; then
  printf 'Expected smoke test data is absent; refusing to continue\n' >&2
  exit 4
fi

kubectl patch sandbox "${sandbox}" -n "${namespace}" --type=merge \
  -p '{"spec":{"operatingMode":"Suspended"}}'
kubectl wait --for=condition=Suspended sandbox/"${sandbox}" -n "${namespace}" --timeout=5m
kubectl wait --for=delete pod/"${sandbox}" -n "${namespace}" --timeout=5m
pvc_uid_suspended="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
owner_uid_suspended="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.metadata.ownerReferences[?(@.kind=="Sandbox")].uid}')"
if [[ "${pvc_uid_suspended}" != "${pvc_uid_before}" || "${owner_uid_suspended}" != "${sandbox_uid}" ]]; then
  printf 'PVC identity/owner changed while Sandbox was suspended\n' >&2
  exit 5
fi

kubectl patch sandbox "${sandbox}" -n "${namespace}" --type=merge \
  -p '{"spec":{"operatingMode":"Running"}}'
kubectl wait --for=condition=Ready sandbox/"${sandbox}" -n "${namespace}" --timeout=5m
pod_uid_after="$(kubectl get pod "${sandbox}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
pvc_uid_after="$(kubectl get pvc "${pvc}" -n "${namespace}" -o jsonpath='{.metadata.uid}')"
after_content="$(kubectl exec "${sandbox}" -n "${namespace}" -- /bin/cat /workspace/management-runner.txt)"
if [[ "${pod_uid_after}" == "${pod_uid_before}" || "${pvc_uid_after}" != "${pvc_uid_before}" || \
  "${after_content}" != "${before_content}" ]]; then
  printf 'Resume did not replace the Pod while preserving its workspace PVC and data\n' >&2
  exit 6
fi

kubectl delete sandbox "${sandbox}" -n "${namespace}" --wait=true --timeout=10m
kubectl wait --for=delete pvc/"${pvc}" -n "${namespace}" --timeout=5m
kubectl wait --for=delete pv/"${pv}" --timeout=5m
for _ in $(seq 1 60); do
  if ! gcloud compute disks describe "${disk}" --project "${GKE_PROJECT_ID}" \
      --zone "${zone}" --format='value(name)' >/dev/null 2>&1; then
    break
  fi
  sleep 5
done
if gcloud compute disks describe "${disk}" --project "${GKE_PROJECT_ID}" \
    --zone "${zone}" --format='value(name)' >/dev/null 2>&1; then
  printf 'Cloud PD %s still exists after Kubernetes PV deletion\n' "${disk}" >&2
  exit 7
fi
kubectl delete networkpolicy allow-sandboxd-smoke-runner -n "${namespace}" --ignore-not-found
printf 'suspend-resume-preserved-pvc pod_uid=%s->%s pvc_uid=%s data=preserved\n' \
  "${pod_uid_before}" "${pod_uid_after}" "${pvc_uid_before}"
printf 'delete-cleanup-removed-pvc-pv-and-cloud-disk pv=%s disk=%s\n' "${pv}" "${disk}"
