#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
PLAN_FILE="${ROOT_DIR}/.work/gke-isolated-destroy.tfplan"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
EXPECTED_REPOSITORY_ID="${ARTIFACT_REPOSITORY_ID:-test-gke-isolated}"
EXPECTED_LOCATION="${ARTIFACT_REGISTRY_LOCATION:-us-central1}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

for command in gcloud terraform; do
  require_command "${command}"
done
[[ -n "${PROJECT_ID}" && "${PROJECT_ID}" != "(unset)" ]] || {
  echo "Set PROJECT_ID or configure gcloud's active project." >&2
  exit 1
}

STATE_ADDRESSES="$(terraform -chdir="${TF_DIR}" state list)"
grep -qx 'google_artifact_registry_repository.agent' <<<"${STATE_ADDRESSES}" || {
  echo "Refusing cleanup: google_artifact_registry_repository.agent is not in Terraform state." >&2
  echo "State-owned resources:" >&2
  printf '%s\n' "${STATE_ADDRESSES}" >&2
  exit 1
}
REPOSITORY_STATE="$(terraform -chdir="${TF_DIR}" state show google_artifact_registry_repository.agent)"
grep -Eq "^[[:space:]]*project[[:space:]]*=[[:space:]]*\"${PROJECT_ID}\"$" <<<"${REPOSITORY_STATE}" || {
  echo "Refusing cleanup: repository project does not match ${PROJECT_ID}." >&2
  exit 1
}
grep -Eq "^[[:space:]]*location[[:space:]]*=[[:space:]]*\"${EXPECTED_LOCATION}\"$" <<<"${REPOSITORY_STATE}" || {
  echo "Refusing cleanup: repository location does not match ${EXPECTED_LOCATION}." >&2
  exit 1
}
grep -Eq "^[[:space:]]*repository_id[[:space:]]*=[[:space:]]*\"${EXPECTED_REPOSITORY_ID}\"$" <<<"${REPOSITORY_STATE}" || {
  echo "Refusing cleanup: repository ID does not match ${EXPECTED_REPOSITORY_ID}." >&2
  exit 1
}

mkdir -p "${ROOT_DIR}/.work"
echo "Artifact Registry repositories before cleanup:"
gcloud artifacts repositories list --project="${PROJECT_ID}" --location="${EXPECTED_LOCATION}" --format='table(name,format)'
terraform -chdir="${TF_DIR}" plan -destroy -input=false \
  -var="project_id=${PROJECT_ID}" \
  -var="artifact_repository_id=${EXPECTED_REPOSITORY_ID}" \
  -var="artifact_registry_location=${EXPECTED_LOCATION}" \
  -out="${PLAN_FILE}"

DESTROY_PLAN="$(terraform -chdir="${TF_DIR}" show -no-color "${PLAN_FILE}")"
UNEXPECTED_REPOSITORIES="$(grep -E '^  # google_artifact_registry_repository\.' <<<"${DESTROY_PLAN}" | grep -v '^  # google_artifact_registry_repository\.agent ' || true)"
if [[ -n "${UNEXPECTED_REPOSITORIES}" ]]; then
  echo "Refusing cleanup: destroy plan contains another Artifact Registry repository:" >&2
  printf '%s\n' "${UNEXPECTED_REPOSITORIES}" >&2
  exit 1
fi
grep -q 'google_artifact_registry_repository.agent' <<<"${DESTROY_PLAN}" || {
  echo "Refusing cleanup: destroy plan does not contain the state-owned repository." >&2
  exit 1
}

if [[ "${APPLY:-0}" != "1" ]]; then
  echo "Destroy plan saved to ${PLAN_FILE}. Review it, then rerun with APPLY=1."
  exit 0
fi

terraform -chdir="${TF_DIR}" apply -input=false "${PLAN_FILE}"
if [[ -n "$(terraform -chdir="${TF_DIR}" state list)" ]]; then
  echo "Terraform state is not empty after cleanup." >&2
  terraform -chdir="${TF_DIR}" state list >&2
  exit 1
fi
echo "Artifact Registry repositories after cleanup:"
gcloud artifacts repositories list --project="${PROJECT_ID}" --location="${EXPECTED_LOCATION}" --format='table(name,format)'
echo "Cleanup complete; the pre-existing repositories were not targeted."
