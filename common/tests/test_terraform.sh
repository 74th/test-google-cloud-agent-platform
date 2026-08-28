#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
terraform_dir="${repo_dir}/terraform"

PYTHONPATH="${repo_dir}/scripts" python3 -m unittest discover -s "${repo_dir}/tests" -p 'test_*.py' -q

scope_guard="${repo_dir}/scripts/check_scope.py"
python3 "${scope_guard}" "${repo_dir}/tests/fixtures/plan-safe.json"
python3 "${scope_guard}" "${repo_dir}/tests/fixtures/plan-safe-authz.json"
if python3 "${scope_guard}" "${repo_dir}/tests/fixtures/plan-unsafe-delete.json"; then
  echo "scope guard accepted protected deletion" >&2
  exit 1
fi
if python3 "${scope_guard}" "${repo_dir}/tests/fixtures/plan-unsafe-consumer.json"; then
  echo "scope guard accepted consumer resource" >&2
  exit 1
fi
if python3 "${scope_guard}" "${repo_dir}/tests/fixtures/plan-unsafe-broad.json"; then
  echo "scope guard accepted broad authorization" >&2
  exit 1
fi

rg -q 'auto_create_subnetworks = false' "${terraform_dir}/main.tf"
rg -q 'default[[:space:]]*= "10\.243\.0\.0/28"' "${terraform_dir}/variables.tf"
rg -q 'resource "google_compute_network_attachment" "agent_gateway"' "${terraform_dir}/main.tf"
rg -q 'connection_preference = "ACCEPT_AUTOMATIC"' "${terraform_dir}/main.tf"
rg -q 'network_attachment = google_compute_network_attachment\.agent_gateway\.self_link' "${terraform_dir}/main.tf"
rg -q 'governed_access_path = "AGENT_TO_ANYWHERE"' "${terraform_dir}/main.tf"
rg -q 'resource "google_network_services_authz_extension" "iap"' "${terraform_dir}/main.tf"
rg -q 'iamEnforcementMode = "ENFORCE"' "${terraform_dir}/main.tf"
rg -q 'resource "google_network_security_authz_policy" "iap"' "${terraform_dir}/main.tf"
rg -q 'resources = \[google_network_services_agent_gateway\.shared\.id\]' "${terraform_dir}/main.tf"
rg -q 'output "iap_authz_extension_id"' "${terraform_dir}/outputs.tf"
rg -q 'output "iap_authz_policy_id"' "${terraform_dir}/outputs.tf"
rg -q 'resource "google_agent_registry_service" "github"' "${terraform_dir}/registry.tf"
rg -q 'https://agentregistry.googleapis.com' "${terraform_dir}/registry.tf"
rg -q 'https://aiplatform.googleapis.com' "${terraform_dir}/registry.tf"
rg -q 'https://us-central1-aiplatform.googleapis.com' "${terraform_dir}/registry.tf"
rg -q 'https://iamcredentials.googleapis.com' "${terraform_dir}/registry.tf"
rg -q 'output "agent_gateway_id"' "${terraform_dir}/outputs.tf"
rg -q 'output "network_id"' "${terraform_dir}/outputs.tf"
rg -q 'output "subnetwork_id"' "${terraform_dir}/outputs.tf"

if rg -q 'google_vertex_ai_reasoning_engine|google_container_cluster|google_cloud_run_v2_service|google_artifact_registry_repository' "${terraform_dir}" --glob '*.tf'; then
  echo "common Terraform contains a consumer-specific resource" >&2
  exit 1
fi

if rg -n 'terraform[[:space:]]+destroy|--allow-insecure|curl[^\n]*-k|http://|allUsers|roles/(owner|editor)' \
  "${repo_dir}/scripts/validate.sh" "${repo_dir}/docs" "${repo_dir}/terraform" --glob '*.sh' --glob '*.py' --glob '*.md' --glob '*.tf'; then
  echo "unsafe operation or fallback found in common implementation" >&2
  exit 1
fi
