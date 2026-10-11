#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${GKE_CLUSTER_NAME:?Set GKE_CLUSTER_NAME explicitly}"
expected_context="gke_${GKE_PROJECT_ID}_${GKE_LOCATION}_${GKE_CLUSTER_NAME}"
current_context="$(kubectl config current-context)"
if [[ "${current_context}" != "${expected_context}" ]]; then
  printf 'Refusing storage validation: current context %s, expected %s\n' \
    "${current_context}" "${expected_context}" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
namespace=session-sandbox-fixtures
rom_phase="$(kubectl get pvc runtime-code-rom --namespace "${namespace}" \
  -o jsonpath='{.status.phase}' 2>/dev/null || true)"
if [[ "${rom_phase}" != "Bound" ]]; then
  kubectl apply -f "${repo_root}/k8s/fixtures/seed.yaml"
  kubectl wait --for=condition=complete job/runtime-code-seed \
    --namespace "${namespace}" --timeout=10m

  source_pv="$(kubectl get pvc runtime-code-seed --namespace "${namespace}" \
    -o jsonpath='{.spec.volumeName}')"
  volume_handle="$(kubectl get pv "${source_pv}" -o jsonpath='{.spec.csi.volumeHandle}')"
  fixture_zone="$(kubectl get pv "${source_pv}" -o=jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[?(@.key=="topology.gke.io/zone")].values[0]}')"
  storage_size="$(kubectl get pv "${source_pv}" -o jsonpath='{.spec.capacity.storage}')"
  if [[ -z "${volume_handle}" || -z "${fixture_zone}" || -z "${storage_size}" ]]; then
    printf 'Seed PV is missing its disk handle, zone, or capacity.\n' >&2
    exit 3
  fi

  kubectl patch pv "${source_pv}" --type=merge \
    -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
  kubectl delete job runtime-code-seed --namespace "${namespace}" --wait=true
  kubectl delete pvc runtime-code-seed --namespace "${namespace}" --wait=true
  kubectl wait --for=jsonpath='{.status.phase}'=Released \
    "pv/${source_pv}" --timeout=2m
  kubectl delete pv "${source_pv}" --wait=true

  fixture_manifest="$(mktemp)"
  trap 'rm -f "${fixture_manifest}"' EXIT
  cat >"${fixture_manifest}" <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: runtime-code-rom-pv
  labels:
    gke-session-sandbox/fixture: shared-code
spec:
  capacity:
    storage: ${storage_size}
  accessModes:
    - ReadOnlyMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: sandbox-code-rom
  volumeMode: Filesystem
  claimRef:
    namespace: ${namespace}
    name: runtime-code-rom
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: topology.gke.io/zone
              operator: In
              values: [${fixture_zone}]
  csi:
    driver: pd.csi.storage.gke.io
    volumeHandle: ${volume_handle}
    fsType: ext4
    readOnly: true
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: runtime-code-rom
  namespace: ${namespace}
  labels:
    app.kubernetes.io/part-of: gke-session-sandbox
    gke-session-sandbox/fixture: shared-code
spec:
  accessModes: [ReadOnlyMany]
  storageClassName: sandbox-code-rom
  volumeName: runtime-code-rom-pv
  resources:
    requests:
      storage: ${storage_size}
EOF
  kubectl apply -f "${fixture_manifest}"
  rm -f "${fixture_manifest}"
  trap - EXIT
fi

kubectl wait --for=jsonpath='{.status.phase}'=Bound \
  pvc/runtime-code-rom --namespace "${namespace}" --timeout=10m
kubectl apply -f "${repo_root}/k8s/fixtures/workspace-validation.yaml"

fixture_zone="$(kubectl get pv runtime-code-rom-pv \
  -o=jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[?(@.key=="topology.gke.io/zone")].values[0]}')"
rendered_readers="$(mktemp)"
trap 'rm -f "${rendered_readers}"' EXIT
sed "s/FIXTURE_ZONE/${fixture_zone}/g" \
  "${repo_root}/k8s/fixtures/readers.yaml" >"${rendered_readers}"
kubectl delete pod shared-code-reader-a shared-code-reader-b \
  --namespace "${namespace}" --ignore-not-found --wait=true
kubectl apply -f "${rendered_readers}"
for pod in shared-code-reader-a shared-code-reader-b; do
  kubectl wait --for=jsonpath='{.status.phase}'=Succeeded \
    "pod/${pod}" --namespace "${namespace}" --timeout=10m
  kubectl logs "${pod}" --namespace "${namespace}"
done

node_a="$(kubectl get pod shared-code-reader-a -n "${namespace}" -o jsonpath='{.spec.nodeName}')"
node_b="$(kubectl get pod shared-code-reader-b -n "${namespace}" -o jsonpath='{.spec.nodeName}')"
if [[ "${node_a}" == "${node_b}" ]]; then
  printf 'Readers were scheduled to the same node (%s); multi-node validation failed.\n' "${node_a}" >&2
  exit 4
fi
printf 'Shared ROM was read concurrently from distinct nodes: %s and %s\n' "${node_a}" "${node_b}"
kubectl get pvc runtime-code-rom workspace-validation --namespace "${namespace}" -o wide
