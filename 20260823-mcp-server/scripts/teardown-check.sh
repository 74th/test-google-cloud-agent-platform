#!/usr/bin/env bash
set -euo pipefail

plan_file="${1:-/tmp/mcp-20260823-destroy.tfplan}"
if [[ ! -f "$plan_file" ]]; then
  printf 'Destroy plan not found: %s\n' "$plan_file" >&2
  exit 2
fi

plan_json="$(mktemp)"
cleanup() {
  rm -f "$plan_json"
}
trap cleanup EXIT
terraform -chdir=terraform show -json "$plan_file" >"$plan_json"

# Validate resource actions and scope from structured plan data. Do not scan
# the human-readable plan for words such as "default" or "autopilot": a
# Standard GKE plan legitimately contains fields named default_* and
# autopilot_* while still being an experiment-owned resource. The shared VPC
# and Gateway may also appear as references of consumer resources, but they
# must not appear as managed destroy addresses.
python3 "$(dirname "$0")/check_scope.py" "$plan_json"

if ! jq -e '
  [ .resource_changes[]
    | select((.address | startswith("data.")) | not)
    | select(.change.actions != ["no-op"])
  ] as $changes
  | ($changes | length > 0)
  and ($changes | all(.change.actions == ["delete"]))
  and ($changes | all((.address | test("common-egress|common-agent-gateway|agw-20260822|claude-agent"; "i")) | not))
  and ($changes | all((.change.before | tostring | test("allUsers"; "i")) | not))
' "$plan_json" >/dev/null; then
  printf '%s\n' 'Refusing: destroy plan contains an out-of-scope action or public IAM binding.' >&2
  exit 1
fi

if ! jq -e '[.resource_changes[] | select((.address | startswith("data.")) | not) | select(.change.actions != ["no-op"])] | any((.address + " " + (.change.before | tostring)) | test("mcp-20260823|google_project_service\\.required"))' "$plan_json" >/dev/null; then
  printf '%s\n' 'Refusing: destroy plan has no experiment-owned resource.' >&2
  exit 1
fi

printf '%s\n' 'Destroy plan passed the experiment-scope guard.'
