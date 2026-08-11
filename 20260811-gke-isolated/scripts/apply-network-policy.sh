#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_DIR="${ROOT_DIR}/k8s"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_command kubectl

echo "Selector: app=test,component=isolated-claude-agent"
echo "Allowed FQDNs: github.com, aiplatform.googleapis.com, bigquery.googleapis.com"
echo "Allowed in-cluster egress: kube-dns UDP/TCP 53 and metadata 169.254.169.252:988"

echo "--- Client-side dry-run ---"
kubectl apply --dry-run=client -f "${POLICY_DIR}/network-policy.yaml"
kubectl apply --dry-run=client -f "${POLICY_DIR}/fqdn-network-policy.yaml"
echo "--- Server-side dry-run ---"
kubectl apply --dry-run=server -f "${POLICY_DIR}/network-policy.yaml"
kubectl apply --dry-run=server -f "${POLICY_DIR}/fqdn-network-policy.yaml"

kubectl apply -f "${POLICY_DIR}/network-policy.yaml"
kubectl apply -f "${POLICY_DIR}/fqdn-network-policy.yaml"

for attempt in $(seq 1 30); do
  if kubectl get networkpolicy/test-default-deny-egress >/dev/null 2>&1 \
    && kubectl get fqdnnetworkpolicy/test-allow-approved-fqdns >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == 30 ]]; then
    echo "Network policy resources did not become readable in time." >&2
    exit 1
  fi
  sleep 2
done

echo "--- Standard NetworkPolicy ---"
kubectl get networkpolicy/test-default-deny-egress -o yaml
echo "--- FQDNNetworkPolicy ---"
kubectl get fqdnnetworkpolicy/test-allow-approved-fqdns -o yaml
