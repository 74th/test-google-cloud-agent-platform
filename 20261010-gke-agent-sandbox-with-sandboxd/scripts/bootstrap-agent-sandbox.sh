#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${GKE_CLUSTER_NAME:?Set GKE_CLUSTER_NAME explicitly}"

expected_context="gke_${GKE_PROJECT_ID}_${GKE_LOCATION}_${GKE_CLUSTER_NAME}"
current_context="$(kubectl config current-context)"
if [[ "${current_context}" != "${expected_context}" ]]; then
  printf 'Refusing to bootstrap: current kubectl context is %s, expected %s\n' \
    "${current_context}" "${expected_context}" >&2
  exit 2
fi

manifest="$(cd "$(dirname "${BASH_SOURCE[0]}")/../k8s" && pwd)/vendor/agent-sandbox-v1.0.6.yaml"
expected_sha="b995db5839f2bdca3a24b8bbefdec405df662d6dd223eec8f5dc74098c974231"
actual_sha="$(sha256sum "${manifest}" | cut -d ' ' -f 1)"
if [[ "${actual_sha}" != "${expected_sha}" ]]; then
  printf 'Pinned Agent Sandbox manifest checksum mismatch: %s\n' "${actual_sha}" >&2
  exit 3
fi

kubectl apply -f "${manifest}"
kubectl rollout status deployment/agent-sandbox-controller \
  --namespace agent-sandbox-system --timeout=5m
kubectl wait --for=condition=Established crd/sandboxes.agents.x-k8s.io --timeout=2m
