#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
terraform_dir="${repo_dir}/terraform"

terraform -chdir="${terraform_dir}" fmt -check
terraform -chdir="${terraform_dir}" validate
"${repo_dir}/tests/test_terraform.sh"

if [[ "${RUN_TERRAFORM_PLAN:-0}" == "1" ]]; then
  plan_path="${TF_PLAN_PATH:-/tmp/common-agent-gateway.tfplan}"
  terraform -chdir="${terraform_dir}" plan -input=false -out="${plan_path}"
  plan_json="${plan_path}.json"
  terraform -chdir="${terraform_dir}" show -json "${plan_path}" > "${plan_json}"
  python3 "${repo_dir}/scripts/check_scope.py" "${plan_json}"
  jq -e '
      [.resource_changes[] | select(.change.actions != ["no-op"])] as $changes
      | if ($changes | length) == 0 then true
        else
          ([$changes[] | select(.change.actions == ["create"]) | .type]) as $types
          | ($types | index("google_compute_network") != null)
          and ($types | index("google_compute_subnetwork") != null)
          and ($types | index("google_compute_network_attachment") != null)
          and ($types | index("google_network_services_agent_gateway") != null)
          and ($types | index("google_vertex_ai_reasoning_engine") == null)
          and ($types | index("google_container_cluster") == null)
          and ($types | index("google_cloud_run_v2_service") == null)
          and ($types | index("google_artifact_registry_repository") == null)
        end
    ' "${plan_json}"
fi
