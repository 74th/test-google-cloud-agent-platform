#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
AR_REPOSITORY="${AR_REPOSITORY:-}"
AGENT_NAME="${AGENT_NAME:-kanazawa-timetable-claude-agent}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-$PROJECT_ID}"
VERTEX_REGION="${VERTEX_REGION:-global}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

required=(LOCATION AR_REPOSITORY VERTEX_PROJECT_ID VERTEX_REGION)
for name in "${required[@]}"; do
  if [[ -z "${!name}" ]]; then
    echo "必須設定 $name がありません。例: $name=<値> ./scripts/deploy.sh" >&2
    exit 2
  fi
done
command -v terraform >/dev/null || { echo "Terraform CLI が必要です。先に terraform apply を実行してください。" >&2; exit 2; }
RUNTIME_SERVICE_ACCOUNT="$(terraform -chdir=terraform output -raw runtime_service_account_email 2>/dev/null)" \
  || { echo "Terraform output runtime_service_account_email を取得できません。先に terraform apply を実行してください。" >&2; exit 2; }
if [[ -z "$RUNTIME_SERVICE_ACCOUNT" ]]; then
  echo "Terraform output runtime_service_account_email が空です。" >&2
  exit 2
fi
command -v gcloud >/dev/null || { echo "gcloud CLI が必要です。" >&2; exit 2; }

IMAGE_URI="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/kanazawa-timetable-agent:${IMAGE_TAG}"
gcloud builds submit --project "$PROJECT_ID" --tag "$IMAGE_URI" .

deploy_args=(--project "$PROJECT_ID" --location "$LOCATION" --image-uri "$IMAGE_URI" --display-name "$AGENT_NAME" --vertex-project "$VERTEX_PROJECT_ID" --vertex-region "$VERTEX_REGION")
deploy_args+=(--service-account "$RUNTIME_SERVICE_ACCOUNT")
python scripts/deploy_agent.py "${deploy_args[@]}"
