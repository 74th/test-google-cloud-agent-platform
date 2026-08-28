#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
terraform_dir="${repo_dir}/terraform"

rg -q 'auto_create_subnetworks = false' "${terraform_dir}/main.tf"
rg -q 'default[[:space:]]*= "10\.243\.0\.0/28"' "${terraform_dir}/variables.tf"
rg -q 'resource "google_compute_network_attachment" "agent_gateway"' "${terraform_dir}/main.tf"
rg -q 'connection_preference = "ACCEPT_AUTOMATIC"' "${terraform_dir}/main.tf"
rg -q 'network_attachment = google_compute_network_attachment\.agent_gateway\.self_link' "${terraform_dir}/main.tf"
rg -q 'governed_access_path = "AGENT_TO_ANYWHERE"' "${terraform_dir}/main.tf"
rg -q 'output "agent_gateway_id"' "${terraform_dir}/outputs.tf"
rg -q 'output "network_id"' "${terraform_dir}/outputs.tf"
rg -q 'output "subnetwork_id"' "${terraform_dir}/outputs.tf"

if rg -q 'google_vertex_ai_reasoning_engine|google_container_cluster|google_cloud_run_v2_service|google_artifact_registry_repository' "${terraform_dir}" --glob '*.tf'; then
  echo "common Terraform contains a consumer-specific resource" >&2
  exit 1
fi
