#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-$PROJECT_ID}"
VERTEX_REGION="${VERTEX_REGION:-global}"
AGENT_GATEWAY_ID="${AGENT_GATEWAY_ID:-${AGENT_GATEWAY_RESOURCE:-}}"

command -v terraform >/dev/null || { echo "Terraform CLI が必要です。" >&2; exit 2; }
command -v gcloud >/dev/null || { echo "gcloud CLI が必要です。" >&2; exit 2; }
if [[ -z "$AGENT_GATEWAY_ID" ]]; then
  echo "AGENT_GATEWAY_ID または AGENT_GATEWAY_RESOURCE に common の完全修飾 Gateway ID が必要です。" >&2
  exit 2
fi
IMAGE_URI="${IMAGE_URI:-}"
if [[ -z "$IMAGE_URI" ]]; then
  echo "IMAGE_URI に immutable @sha256 image reference が必要です。" >&2
  exit 2
fi

PLAN_FILE="${PLAN_FILE:-evidence/terraform-consumer-20260828.tfplan}"

terraform -chdir=terraform plan \
  -input=false \
  -out="../${PLAN_FILE}" \
  -var="project_id=${PROJECT_ID}" \
  -var="location=${LOCATION}" \
  -var="vertex_project_id=${VERTEX_PROJECT_ID}" \
  -var="vertex_region=${VERTEX_REGION}" \
  -var="agent_gateway_id=${AGENT_GATEWAY_ID}" \
  -var="runtime_image_uri=${IMAGE_URI}"

echo "Reviewed plan written to ${PLAN_FILE}. Apply only this saved plan after human approval: APPLY_APPROVED=1 terraform -chdir=terraform apply ../${PLAN_FILE}" >&2
if [[ "${APPLY_APPROVED:-0}" == "1" ]]; then
  terraform -chdir=terraform apply -input=false "../${PLAN_FILE}"
fi
