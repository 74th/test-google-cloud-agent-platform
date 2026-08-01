#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
AGENT_NAME="${AGENT_NAME:-kanazawa-timetable-claude-agent}"
VERTEX_PROJECT_ID="${VERTEX_PROJECT_ID:-$PROJECT_ID}"
VERTEX_REGION="${VERTEX_REGION:-global}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

required=(LOCATION VERTEX_PROJECT_ID VERTEX_REGION)
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
ARTIFACT_REPOSITORY="$(terraform -chdir=terraform output -raw artifact_registry_repository_id 2>/dev/null)" \
  || { echo "Terraform output artifact_registry_repository_id を取得できません。先に terraform apply を実行してください。" >&2; exit 2; }
if [[ -z "$ARTIFACT_REPOSITORY" ]]; then
  echo "Terraform output artifact_registry_repository_id が空です。" >&2
  exit 2
fi
command -v gcloud >/dev/null || { echo "gcloud CLI が必要です。" >&2; exit 2; }
command -v docker >/dev/null || { echo "Docker CLI が必要です。" >&2; exit 2; }

IMAGE_URI="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPOSITORY}/kanazawa-timetable-agent:${IMAGE_TAG}"
gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet
docker build --tag "$IMAGE_URI" .
docker push "$IMAGE_URI"

deploy_args=(--project "$PROJECT_ID" --location "$LOCATION" --image-uri "$IMAGE_URI" --display-name "$AGENT_NAME" --vertex-project "$VERTEX_PROJECT_ID" --vertex-region "$VERTEX_REGION")
deploy_args+=(--service-account "$RUNTIME_SERVICE_ACCOUNT")
python scripts/deploy_agent.py "${deploy_args[@]}"
