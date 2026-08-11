#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
PLAN_FILE="${ROOT_DIR}/.work/gke-isolated.tfplan"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

for command in gcloud terraform kubectl; do
  require_command "${command}"
done

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Set PROJECT_ID or configure gcloud's active project." >&2
  exit 1
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  echo "No active gcloud account. Run gcloud auth login first." >&2
  exit 1
fi

echo "Project: ${PROJECT_ID}"
echo "Account: ${ACTIVE_ACCOUNT}"
echo "Terraform directory: ${TF_DIR}"

terraform -chdir="${TF_DIR}" init -input=false
mkdir -p "${ROOT_DIR}/.work"

if [[ "${APPLY:-0}" != "1" ]]; then
  terraform -chdir="${TF_DIR}" plan \
    -input=false \
    -var="project_id=${PROJECT_ID}" \
    -out="${PLAN_FILE}"
  echo
  echo "Plan saved to ${PLAN_FILE}"
  echo "Review the plan above. Terraform apply is intentionally disabled by default."
  echo "After review, apply this saved plan with: APPLY=1 PROJECT_ID=${PROJECT_ID} $0"
  exit 0
fi

if [[ ! -f "${PLAN_FILE}" ]]; then
  echo "No saved plan found at ${PLAN_FILE}. Run this script once without APPLY=1 first." >&2
  exit 1
fi

echo "Applying the previously reviewed plan: ${PLAN_FILE}"
terraform -chdir="${TF_DIR}" apply -input=false "${PLAN_FILE}"

CLUSTER_NAME="$(terraform -chdir="${TF_DIR}" output -raw cluster_name)"
ZONE="$(terraform -chdir="${TF_DIR}" output -raw zone)"
gcloud container clusters get-credentials "${CLUSTER_NAME}" --zone "${ZONE}" --project "${PROJECT_ID}"

echo "--- Cluster configuration ---"
gcloud container clusters describe "${CLUSTER_NAME}" \
  --zone "${ZONE}" \
  --project "${PROJECT_ID}" \
  --format='yaml(name,location,network,subnetwork,datapathProvider,networkConfig,workloadIdentityConfig)' \
  | tee "${ROOT_DIR}/.work/cluster-description.yaml"
echo "--- Nodes ---"
kubectl get nodes -o wide
