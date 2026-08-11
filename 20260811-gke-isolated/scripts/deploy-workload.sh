#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
RENDER_DIR="$(mktemp -d)"
trap 'rm -rf "${RENDER_DIR}"' EXIT

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

for command in docker gcloud kubectl terraform; do
  require_command "${command}"
done

PROJECT_ID="${PROJECT_ID:-$(terraform -chdir="${TF_DIR}" output -raw project_id)}"
REGISTRY="$(terraform -chdir="${TF_DIR}" output -raw image_repository)"
IMAGE_URI="${REGISTRY}/test:${IMAGE_TAG:-latest}"
WORKLOAD_PRINCIPAL="$(terraform -chdir="${TF_DIR}" output -raw workload_iam_principal)"

echo "Project: ${PROJECT_ID}"
echo "Image: ${IMAGE_URI}"
echo "Workload IAM principal: ${WORKLOAD_PRINCIPAL}"

gcloud auth configure-docker "${REGISTRY%%/*}" --quiet
docker build --tag "${IMAGE_URI}" "${ROOT_DIR}/container"
docker push "${IMAGE_URI}"

cp "${ROOT_DIR}/k8s/service-account.yaml" "${RENDER_DIR}/service-account.yaml"
sed \
  -e "s|__PROJECT_ID__|${PROJECT_ID}|g" \
  -e "s|__IMAGE_URI__|${IMAGE_URI}|g" \
  "${ROOT_DIR}/k8s/deployment.yaml" > "${RENDER_DIR}/deployment.yaml"

echo "--- Client-side dry-run (normal workload resources) ---"
kubectl apply --dry-run=client -f "${RENDER_DIR}/service-account.yaml"
kubectl apply --dry-run=client -f "${RENDER_DIR}/deployment.yaml"
echo "--- Server-side dry-run (normal workload resources) ---"
kubectl apply --dry-run=server -f "${RENDER_DIR}/service-account.yaml"
kubectl apply --dry-run=server -f "${RENDER_DIR}/deployment.yaml"

# Policies are deliberately not included here; baseline tests run first.
kubectl apply -f "${RENDER_DIR}/service-account.yaml"
kubectl apply -f "${RENDER_DIR}/deployment.yaml"
kubectl rollout status deployment/test --timeout=10m
kubectl get deployment/test -o wide
kubectl get pods -l app=test,component=isolated-claude-agent -o wide

if kubectl get secrets -l app=test -o name 2>/dev/null | grep -q .; then
  echo "Unexpected application Secret found for test workload." >&2
  exit 1
fi

echo "Workload deployed without a long-lived service-account key Secret."
