#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
ARTIFACT_REPOSITORY_ID="${ARTIFACT_REPOSITORY_ID:-${TF_VAR_artifact_repository_id:-test-gke-isolated}}"
ARTIFACT_REGISTRY_LOCATION="${ARTIFACT_REGISTRY_LOCATION:-${TF_VAR_artifact_registry_location:-us-central1}}"
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
echo "Artifact Registry target: ${PROJECT_ID}/${ARTIFACT_REGISTRY_LOCATION}/${ARTIFACT_REPOSITORY_ID}"

terraform -chdir="${TF_DIR}" init -input=false
mkdir -p "${ROOT_DIR}/.work"

STATE_ADDRESSES="$(terraform -chdir="${TF_DIR}" state list)"
if grep -qx 'google_artifact_registry_repository.agent' <<<"${STATE_ADDRESSES}"; then
  REPOSITORY_STATE="$(terraform -chdir="${TF_DIR}" state show google_artifact_registry_repository.agent)"
  grep -Eq "^[[:space:]]*project[[:space:]]*=[[:space:]]*\"${PROJECT_ID}\"$" <<<"${REPOSITORY_STATE}" || {
    echo "Terraform state repository project does not match ${PROJECT_ID}." >&2
    exit 1
  }
  grep -Eq "^[[:space:]]*location[[:space:]]*=[[:space:]]*\"${ARTIFACT_REGISTRY_LOCATION}\"$" <<<"${REPOSITORY_STATE}" || {
    echo "Terraform state repository location does not match ${ARTIFACT_REGISTRY_LOCATION}." >&2
    exit 1
  }
  grep -Eq "^[[:space:]]*repository_id[[:space:]]*=[[:space:]]*\"${ARTIFACT_REPOSITORY_ID}\"$" <<<"${REPOSITORY_STATE}" || {
    echo "Terraform state repository ID does not match ${ARTIFACT_REPOSITORY_ID}." >&2
    exit 1
  }
else
  if gcloud artifacts repositories describe "${ARTIFACT_REPOSITORY_ID}" \
    --project="${PROJECT_ID}" --location="${ARTIFACT_REGISTRY_LOCATION}" >/dev/null 2>&1; then
    echo "Refusing to continue: ${PROJECT_ID}/${ARTIFACT_REGISTRY_LOCATION}/${ARTIFACT_REPOSITORY_ID} exists outside Terraform state." >&2
    echo "Importing or deleting state-external repositories is not permitted by this workflow." >&2
    exit 1
  fi
fi

echo "Artifact Registry repositories currently present (read-only check):"
gcloud artifacts repositories list --project="${PROJECT_ID}" --location="${ARTIFACT_REGISTRY_LOCATION}" --format='table(name,format)'

if [[ "${APPLY:-0}" != "1" ]]; then
  terraform -chdir="${TF_DIR}" plan \
    -input=false \
    -var="project_id=${PROJECT_ID}" \
    -var="artifact_repository_id=${ARTIFACT_REPOSITORY_ID}" \
    -var="artifact_registry_location=${ARTIFACT_REGISTRY_LOCATION}" \
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
