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
echo "Allowed in-cluster egress: kube-dns UDP/TCP 53 and GKE metadata endpoints 169.254.169.252:987/988, 169.254.169.254:80/8080"

echo "--- NetworkLogging client-side dry-run ---"
kubectl apply --dry-run=client -f "${POLICY_DIR}/network-logging.yaml"
echo "--- NetworkLogging server-side dry-run ---"
kubectl apply --dry-run=server -f "${POLICY_DIR}/network-logging.yaml"
kubectl apply -f "${POLICY_DIR}/network-logging.yaml"

for attempt in $(seq 1 30); do
  if kubectl get networklogging/default >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == 30 ]]; then
    echo "NetworkLogging/default did not become readable in time." >&2
    exit 1
  fi
  sleep 2
done

NETWORK_LOGGING_SPEC="$(kubectl get networklogging/default -o jsonpath='{.spec.cluster.deny.log}{" "}{.spec.cluster.deny.delegate}{" "}{.spec.cluster.allow.log}{" "}{.spec.cluster.allow.delegate}')"
if [[ "${NETWORK_LOGGING_SPEC}" != "true false false false" ]]; then
  echo "Unexpected NetworkLogging/default spec: ${NETWORK_LOGGING_SPEC}" >&2
  exit 1
fi
echo "--- NetworkLogging/default ---"
kubectl get networklogging/default -o yaml
NETWORK_LOGGING_DESCRIPTION="$(kubectl describe networklogging/default)"
printf '%s\n' "${NETWORK_LOGGING_DESCRIPTION}"
if grep -Eiq '(^|[[:space:]])(error|warning|failed)(:|[[:space:]]|$)' <<<"${NETWORK_LOGGING_DESCRIPTION}"; then
  echo "NetworkLogging/default reports a configuration error." >&2
  exit 1
fi

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
