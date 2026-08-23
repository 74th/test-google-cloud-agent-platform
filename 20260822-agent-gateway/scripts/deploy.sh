#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-$PROJECT_ID}"
VERTEX_REGION="${VERTEX_REGION:-global}"
AGENT_GATEWAY_NAME="${AGENT_GATEWAY_NAME:-agw-20260822-egress}"

command -v terraform >/dev/null || { echo "Terraform CLI が必要です。" >&2; exit 2; }
command -v gcloud >/dev/null || { echo "gcloud CLI が必要です。" >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker CLI が必要です。" >&2; exit 2; }

export REPOSITORY_ID="$(terraform -chdir=terraform output -raw artifact_registry_repository_id)"
export AGENT_GATEWAY_RESOURCE="$(terraform -chdir=terraform output -raw agent_gateway_id)"
export IMAGE_URI="$(PROJECT_ID="$PROJECT_ID" LOCATION="$LOCATION" REPOSITORY_ID="$REPOSITORY_ID" ./scripts/build_push.sh)"

terraform -chdir=terraform apply \
  -input=false -auto-approve \
  -var="project_id=${PROJECT_ID}" \
  -var="location=${LOCATION}" \
  -var="vertex_project_id=${VERTEX_PROJECT_ID}" \
  -var="vertex_region=${VERTEX_REGION}" \
  -var="runtime_image_uri=${IMAGE_URI}"

terraform -chdir=terraform output -raw runtime_name
