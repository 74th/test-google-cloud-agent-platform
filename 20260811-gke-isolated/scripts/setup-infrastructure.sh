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

for command in gcloud terraform kubectl python3; do
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

NETWORK_NAME="${NETWORK_NAME:-${TF_VAR_network_name:-$(terraform -chdir="${TF_DIR}" output -raw network_name 2>/dev/null || true)}}"
[[ -n "${NETWORK_NAME}" ]] || {
  echo "Terraform output network_name is required for the DNS Policy preflight." >&2
  exit 1
}
NETWORK_URL="$(gcloud compute networks describe "${NETWORK_NAME}" --project="${PROJECT_ID}" --format='value(selfLink)')" || {
  echo "Could not resolve target VPC ${NETWORK_NAME} in ${PROJECT_ID}." >&2
  exit 1
}

echo "Target VPC: ${NETWORK_NAME} (${NETWORK_URL})"

DNS_POLICY_STATE=0
if grep -qx 'google_dns_policy.gke_dns_logging' <<<"${STATE_ADDRESSES}"; then
  DNS_POLICY_STATE=1
  DNS_POLICY_STATE_JSON="$(terraform -chdir="${TF_DIR}" show -json | python3 -c '
import json
import sys

state = json.load(sys.stdin)
for resource in state.get("values", {}).get("root_module", {}).get("resources", []):
    if resource.get("address") == "google_dns_policy.gke_dns_logging":
        values = resource.get("values", {})
        print(json.dumps({
            "name": values.get("name"),
            "network_urls": [item.get("network_url") for item in values.get("networks", [])],
            "enable_logging": values.get("enable_logging"),
        }))
        break
')"
  if [[ -z "${DNS_POLICY_STATE_JSON}" ]]; then
    echo "Could not inspect google_dns_policy.gke_dns_logging in Terraform state." >&2
    exit 1
  fi
  DNS_POLICY_STATE_JSON="${DNS_POLICY_STATE_JSON}" NETWORK_URL="${NETWORK_URL}" python3 -c '
import json
import os
import sys

policy = json.loads(os.environ["DNS_POLICY_STATE_JSON"])
network_url = os.environ["NETWORK_URL"]
def canonical_network_url(value):
    marker = "/projects/"
    if marker in value:
        return value[value.index(marker) + 1:]
    return value.removeprefix("https://").removeprefix("http://")

target = canonical_network_url(network_url)
state_networks = {canonical_network_url(value) for value in policy.get("network_urls", [])}
if policy.get("name") != "gke-dns-logging" or target not in state_networks:
    print("Terraform state DNS Policy does not match the target VPC or expected name.", file=sys.stderr)
    sys.exit(1)
if policy.get("enable_logging") is not True:
    print("Terraform state DNS Policy does not have enable_logging=true.", file=sys.stderr)
    sys.exit(1)
'
fi

DNS_API_ENABLED=0
if gcloud services list --enabled --project="${PROJECT_ID}" \
  --filter='config.name:dns.googleapis.com' --format='value(config.name)' | grep -qx 'dns.googleapis.com'; then
  DNS_API_ENABLED=1
fi

if (( DNS_API_ENABLED == 1 )); then
  DNS_POLICIES_JSON="$(gcloud dns policies list --project="${PROJECT_ID}" --format=json)" || {
    echo "Could not list Cloud DNS Policies; refusing to continue without the ownership preflight." >&2
    exit 1
  }
else
  DNS_POLICIES_JSON='[]'
  echo "dns.googleapis.com is not enabled yet; no existing DNS Policy can be listed before the Terraform plan."
fi

DNS_POLICIES_JSON="${DNS_POLICIES_JSON}" NETWORK_URL="${NETWORK_URL}" DNS_POLICY_STATE="${DNS_POLICY_STATE}" python3 -c '
import json
import os
import sys

policies = json.loads(os.environ.get("DNS_POLICIES_JSON", "[]"))
network_url = os.environ["NETWORK_URL"]
state_owned = os.environ["DNS_POLICY_STATE"] == "1"

def canonical_network_url(value):
    marker = "/projects/"
    if marker in value:
        return value[value.index(marker) + 1:]
    return value.removeprefix("https://").removeprefix("http://")

target = canonical_network_url(network_url)

matches = []
for policy in policies:
    networks = policy.get("networks", []) or []
    urls = {canonical_network_url(item.get("networkUrl") or item.get("network_url")) for item in networks}
    if target in urls:
        matches.append(policy.get("name", "<unnamed>"))

if len(matches) > 1:
    joined = ", ".join(matches)
    print(f"Refusing to continue: multiple Cloud DNS Policies are associated with {network_url}: {joined}.", file=sys.stderr)
    sys.exit(1)
if matches and not state_owned:
    print(f"Refusing to continue: Cloud DNS Policy {matches[0]} exists outside Terraform state for {network_url}.", file=sys.stderr)
    print("Importing or deleting state-external DNS Policies is not permitted by this workflow.", file=sys.stderr)
    sys.exit(1)
if state_owned and not matches:
    print("Terraform state owns gke-dns-logging, but the policy is not present in the Cloud DNS API.", file=sys.stderr)
    sys.exit(1)
'

if (( DNS_POLICY_STATE == 1 )); then
  echo "Cloud DNS Policy ownership preflight passed: gke-dns-logging is the single policy for ${NETWORK_NAME}."
else
  echo "Cloud DNS Policy ownership preflight passed: no state-external policy is associated with ${NETWORK_NAME}."
fi
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
