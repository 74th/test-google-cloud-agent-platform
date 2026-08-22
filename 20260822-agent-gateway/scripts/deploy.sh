#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-$PROJECT_ID}"
VERTEX_REGION="${VERTEX_REGION:-global}"
AGENT_GATEWAY_NAME="${AGENT_GATEWAY_NAME:-agw-20260822-egress}"
AGENT_DISPLAY_NAME="${AGENT_DISPLAY_NAME:-20260822-agent-gateway-claude}"

command -v terraform >/dev/null || { echo "Terraform CLI が必要です。" >&2; exit 2; }
command -v gcloud >/dev/null || { echo "gcloud CLI が必要です。" >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker CLI が必要です。" >&2; exit 2; }

terraform -chdir=terraform output -raw runtime_service_account_email >/dev/null 2>&1 || {
  echo "先に terraform apply を実行してください。" >&2
  exit 2
}

export REPOSITORY_ID="$(terraform -chdir=terraform output -raw artifact_registry_repository_id)"
export SERVICE_ACCOUNT="$(terraform -chdir=terraform output -raw runtime_service_account_email)"
export AGENT_GATEWAY_RESOURCE="$(terraform -chdir=terraform output -raw agent_gateway_id)"
export IMAGE_URI="$(PROJECT_ID="$PROJECT_ID" LOCATION="$LOCATION" REPOSITORY_ID="$REPOSITORY_ID" ./scripts/build_push.sh)"

python_cmd="${PYTHON:-uv run python}"
$python_cmd scripts/deploy_agent.py \
  --project "$PROJECT_ID" --location "$LOCATION" --image-uri "$IMAGE_URI" \
  --display-name "$AGENT_DISPLAY_NAME" --vertex-project "$VERTEX_PROJECT_ID" \
  --vertex-region "$VERTEX_REGION" --service-account "$SERVICE_ACCOUNT" \
  --agent-gateway "$AGENT_GATEWAY_RESOURCE"
