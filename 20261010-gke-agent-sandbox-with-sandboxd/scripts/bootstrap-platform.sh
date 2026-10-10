#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${GKE_CLUSTER_NAME:?Set GKE_CLUSTER_NAME explicitly}"

expected_context="gke_${GKE_PROJECT_ID}_${GKE_LOCATION}_${GKE_CLUSTER_NAME}"
current_context="$(kubectl config current-context)"
if [[ "${current_context}" != "${expected_context}" ]]; then
  printf 'Refusing platform bootstrap: current context %s, expected %s\n' \
    "${current_context}" "${expected_context}" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kubectl apply -f "${repo_root}/k8s/platform/base.yaml"
kubectl get runtimeclass gvisor >/dev/null
kubectl get storageclass standard-rwo >/dev/null
kubectl get storageclass session-workspace-rwo >/dev/null
kubectl get storageclass sandbox-code-rom >/dev/null
kubectl auth can-i create sandboxes.agents.x-k8s.io \
  --as=system:serviceaccount:session-sandbox-system:session-sandbox-worker \
  --namespace=session-sandboxes
kubectl auth can-i create leases.coordination.k8s.io \
  --as=system:serviceaccount:session-sandbox-system:session-sandbox-worker \
  --namespace=session-sandbox-system
