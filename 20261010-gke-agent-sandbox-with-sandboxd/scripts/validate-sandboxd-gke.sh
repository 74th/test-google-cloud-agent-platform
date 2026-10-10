#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${GKE_CLUSTER_NAME:?Set GKE_CLUSTER_NAME explicitly}"
: "${SANDBOXD_IMAGE:?Set SANDBOXD_IMAGE to an immutable image digest}"
: "${RUNTIME_SMOKE_IMAGE:?Set RUNTIME_SMOKE_IMAGE to an immutable image digest}"

expected_context="gke_${GKE_PROJECT_ID}_${GKE_LOCATION}_${GKE_CLUSTER_NAME}"
current_context="$(kubectl config current-context)"
if [[ "${current_context}" != "${expected_context}" ]]; then
  printf 'Refusing runtime smoke test: current context %s, expected %s\n' \
    "${current_context}" "${expected_context}" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SANDBOXD_IMAGE
sed "s|\${SANDBOXD_IMAGE}|${SANDBOXD_IMAGE}|g" \
  "${repo_root}/k8s/fixtures/sandboxd-smoke.yaml" | kubectl apply -f -
kubectl apply -f "${repo_root}/k8s/fixtures/sandboxd-smoke-networkpolicy.yaml"
kubectl wait --for=condition=Ready sandbox/sandboxd-smoke -n session-sandboxes --timeout=10m
pod_ip="$(kubectl get pod sandboxd-smoke -n session-sandboxes -o jsonpath='{.status.podIP}')"
if [[ -z "${pod_ip}" ]]; then
  printf 'Sandbox pod has no IP after Ready\n' >&2
  exit 5
fi

kubectl delete job sandboxd-smoke-runner -n session-sandbox-system --ignore-not-found
export RUNTIME_SMOKE_IMAGE SANDBOXD_POD_IP="${pod_ip}"
sed -e "s|\${RUNTIME_SMOKE_IMAGE}|${RUNTIME_SMOKE_IMAGE}|g" \
  -e "s|\${SANDBOXD_POD_IP}|${SANDBOXD_POD_IP}|g" \
  "${repo_root}/k8s/fixtures/sandboxd-smoke-runner.yaml" | kubectl apply -f -
kubectl wait --for=condition=complete job/sandboxd-smoke-runner \
  -n session-sandbox-system --timeout=5m
kubectl logs job/sandboxd-smoke-runner -n session-sandbox-system
