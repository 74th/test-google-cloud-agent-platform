#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
HOST="checkip.amazonaws.com"
PORT=80
LOG_TIMEOUT_SECONDS="${LOG_TIMEOUT_SECONDS:-300}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-10}"
CURL_TIMEOUT_SECONDS="${CURL_TIMEOUT_SECONDS:-10}"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

for command in gcloud kubectl terraform python3; do
  require_command "${command}"
done

PROJECT_ID="${PROJECT_ID:-$(terraform -chdir="${TF_DIR}" output -raw project_id)}"
CLUSTER_NAME="$(terraform -chdir="${TF_DIR}" output -raw cluster_name)"
CLUSTER_LOCATION="$(terraform -chdir="${TF_DIR}" output -raw cluster_location)"
[[ -n "${PROJECT_ID}" && -n "${CLUSTER_NAME}" && -n "${CLUSTER_LOCATION}" ]] || {
  echo "Terraform outputs project_id, cluster_name, and cluster_location are required." >&2
  exit 1
}

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
[[ -n "${ACTIVE_ACCOUNT}" ]] || { echo "No active gcloud account." >&2; exit 1; }
gcloud services list --enabled --project="${PROJECT_ID}" \
  --filter='config.name:logging.googleapis.com' --format='value(config.name)' | grep -qx 'logging.googleapis.com' || {
  echo "logging.googleapis.com is not enabled in ${PROJECT_ID}." >&2
  exit 1
}

CURRENT_CONTEXT="$(kubectl config current-context)"
kubectl get --raw=/version >/dev/null
kubectl rollout status deployment/test --timeout=5m
POD="$(kubectl get pods -l app=test,component=isolated-claude-agent \
  --field-selector=status.phase=Running --sort-by=.metadata.creationTimestamp \
  -o name | tail -n 1 | cut -d/ -f2)"
[[ -n "${POD}" ]] || { echo "No running test Pod found." >&2; exit 1; }
NAMESPACE="default"
START_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

DNS_OUTPUT="$(kubectl exec -n "${NAMESPACE}" "${POD}" -- getent ahostsv4 "${HOST}")"
mapfile -t DEST_IPS < <(awk '{print $1}' <<<"${DNS_OUTPUT}" | sort -u)
[[ "${#DEST_IPS[@]}" -gt 0 ]] || {
  echo "Could not resolve an IPv4 address for ${HOST} in Pod ${POD}." >&2
  exit 1
}

echo "Project: ${PROJECT_ID}"
echo "Cluster: ${CLUSTER_NAME} (${CLUSTER_LOCATION})"
echo "kubectl context: ${CURRENT_CONTEXT}"
echo "Source Pod: ${NAMESPACE}/${POD}"
echo "Start time (UTC): ${START_TIME}"
echo "Destination: ${HOST}:${PORT} (IPv4: ${DEST_IPS[*]})"
echo "Protocol: tcp; direction: egress; expected disposition: deny"

echo "Generating a denied connection with a finite timeout..."
if kubectl exec -n "${NAMESPACE}" "${POD}" -- \
  curl --connect-timeout 3 --max-time "${CURL_TIMEOUT_SECONDS}" \
  --fail --silent --show-error "http://${HOST}:${PORT}"; then
  echo "Unexpected success from unapproved host ${HOST}." >&2
  exit 1
fi
echo "Unapproved connection failed as expected. Polling policy-action logs..."

QUERY="resource.type=\"k8s_node\" AND resource.labels.project_id=\"${PROJECT_ID}\" AND resource.labels.location=\"${CLUSTER_LOCATION}\" AND resource.labels.cluster_name=\"${CLUSTER_NAME}\" AND logName=\"projects/${PROJECT_ID}/logs/policy-action\" AND timestamp>=\"${START_TIME}\" AND jsonPayload.disposition=\"deny\" AND (jsonPayload.direction=\"egress\" OR jsonPayload.connection.direction=\"egress\") AND (jsonPayload.src_pod_name=\"${POD}\" OR jsonPayload.src.pod_name=\"${POD}\") AND (jsonPayload.dest_port=80 OR jsonPayload.connection.dest_port=80 OR jsonPayload.dest.port=80) AND (jsonPayload.protocol=\"tcp\" OR jsonPayload.protocol=\"TCP\" OR jsonPayload.connection.protocol=\"tcp\" OR jsonPayload.connection.protocol=\"TCP\" OR jsonPayload.connection.protocol=6)"
ERROR_FILE="$(mktemp)"
trap 'rm -f "${ERROR_FILE}"' EXIT
DEADLINE=$((SECONDS + LOG_TIMEOUT_SECONDS))

while (( SECONDS < DEADLINE )); do
  LOG_JSON=""
  if ! LOG_JSON="$(gcloud logging read "${QUERY}" --project="${PROJECT_ID}" --limit=50 --format=json 2>"${ERROR_FILE}")"; then
    if grep -Eiq 'permission denied|permission_denied|PERMISSION_DENIED|unauthorized|authentication' "${ERROR_FILE}"; then
      echo "Cloud Logging query permission/authentication error:" >&2
      cat "${ERROR_FILE}" >&2
      exit 2
    fi
    echo "Cloud Logging query failed:" >&2
    cat "${ERROR_FILE}" >&2
    exit 3
  fi

  MATCH="$(LOG_JSON="${LOG_JSON}" POD="${POD}" DEST_IPS="$(IFS=,; echo "${DEST_IPS[*]}")" \
    python3 - <<'PY'
import json
import os
import sys

def nested(payload, *paths):
    for path in paths:
        value = payload
        try:
            for part in path:
                value = value[part]
        except (KeyError, TypeError):
            continue
        if value is not None:
            return value
    return None

try:
    entries = json.loads(os.environ.get("LOG_JSON", "[]"))
except json.JSONDecodeError:
    sys.exit(0)

pod = os.environ["POD"]
allowed_ips = set(os.environ["DEST_IPS"].split(","))
for entry in entries:
    payload = entry.get("jsonPayload", {})
    source_pod = nested(payload, ("src_pod_name",), ("src", "pod_name"))
    dest_ip = nested(payload, ("dest_ip",), ("connection", "dest_ip"), ("dest", "ip"))
    dest_port = nested(payload, ("dest_port",), ("connection", "dest_port"), ("dest", "port"))
    protocol = nested(payload, ("protocol",), ("connection", "protocol"))
    connection = payload.get("connection", {})
    direction = nested(payload, ("direction",), ("connection", "direction"))
    disposition = payload.get("disposition")
    count = payload.get("count")
    protocol_ok = str(protocol).lower() in {"tcp", "6"}
    try:
        port_ok = int(dest_port) == 80
    except (TypeError, ValueError):
        port_ok = False
    if (source_pod == pod and dest_ip in allowed_ips and port_ok and protocol_ok
            and direction == "egress" and disposition == "deny" and count is not None):
        print(json.dumps({
            "src.pod_name": source_pod,
            "dest_ip": dest_ip,
            "dest_port": dest_port,
            "protocol": protocol,
            "direction": direction,
            "disposition": disposition,
            "count": count,
            "insertId": entry.get("insertId"),
            "timestamp": entry.get("timestamp"),
        }, ensure_ascii=False))
        break
PY
  )"
  if [[ -n "${MATCH}" ]]; then
    echo "Matching policy-action deny log:"
    printf '%s\n' "${MATCH}"
    exit 0
  fi

  remaining=$((DEADLINE - SECONDS))
  (( remaining > 0 )) || break
  sleep "$(( remaining < POLL_INTERVAL_SECONDS ? remaining : POLL_INTERVAL_SECONDS ))"
done

echo "No matching policy-action deny log found within ${LOG_TIMEOUT_SECONDS}s." >&2
echo "Query used: ${QUERY}" >&2
exit 4
