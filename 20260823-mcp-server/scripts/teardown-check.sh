#!/usr/bin/env bash
set -euo pipefail

plan_file="${1:-/tmp/mcp-20260823-destroy.tfplan}"
if [[ ! -f "$plan_file" ]]; then
  printf 'Destroy plan not found: %s\n' "$plan_file" >&2
  exit 2
fi

plan_text="$(terraform -chdir=terraform show -no-color "$plan_file")"
if grep -Eiq 'name\s*=\s*"autopilot"|network\s*=\s*"default"|subnetwork\s*=\s*"default"|common-egress|common-agent-gateway|agw-20260822|claude-agent|allUsers' <<<"$plan_text"; then
  printf '%s\n' 'Refusing: destroy plan contains an out-of-scope resource or public IAM binding.' >&2
  exit 1
fi
if ! grep -q 'mcp-20260823' <<<"$plan_text"; then
  printf '%s\n' 'Refusing: destroy plan has no experiment identifier.' >&2
  exit 1
fi
printf '%s\n' 'Destroy plan passed the experiment-scope guard.'
