#!/usr/bin/env bash
set -euo pipefail

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_command kubectl
kubectl rollout status deployment/test --timeout=5m
POD="$(kubectl get pods -l app=test,component=isolated-claude-agent \
  --field-selector=status.phase=Running --sort-by=.metadata.creationTimestamp \
  -o name | tail -n 1 | cut -d/ -f2)"
echo "Pod: ${POD}"
echo "Phase: before network policy"

echo "[1/3] GitHub public keys"
github_keys="$(kubectl exec deploy/test -- curl --fail --silent --show-error --location https://github.com/74th.keys)"
[[ -n "${github_keys}" ]] || { echo "GitHub keys response was empty" >&2; exit 1; }
printf '%s\n' "${github_keys}"

echo "[2/3] Claude Agent SDK via Vertex AI"
claude_output="$(kubectl exec deploy/test -- python claude_agent_sdk.py 'https://github.com/74th の要約して')"
[[ -n "${claude_output}" ]] || { echo "Claude response was empty" >&2; exit 1; }
printf '%s\n' "${claude_output}"

echo "[3/3] BigQuery public data"
bq_output="$(kubectl exec deploy/test -- python test_bq.py)"
[[ "${bq_output}" == ROWS:* || "${bq_output}" == *$'\n'NO_ROWS:* || "${bq_output}" == NO_ROWS:* ]] || {
  echo "BigQuery output did not report ROWS or NO_ROWS" >&2
  exit 1
}
printf '%s\n' "${bq_output}"

echo "Baseline succeeded: GitHub, Claude Agent SDK, and BigQuery."
