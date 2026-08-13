#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/terraform"
NAMESPACE="${NAMESPACE:-default}"
TEST_FQDN="${TEST_FQDN:-checkip.amazonaws.com}"
TEST_PORT="${TEST_PORT:-80}"
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

[[ "${TEST_FQDN}" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "TEST_FQDN must contain only DNS name characters." >&2
  exit 1
}
[[ "${TEST_PORT}" =~ ^[0-9]+$ ]] || { echo "TEST_PORT must be numeric." >&2; exit 1; }
(( LOG_TIMEOUT_SECONDS > 0 && POLL_INTERVAL_SECONDS > 0 )) || {
  echo "LOG_TIMEOUT_SECONDS and POLL_INTERVAL_SECONDS must be positive." >&2
  exit 1
}

PROJECT_ID="${PROJECT_ID:-$(terraform -chdir="${TF_DIR}" output -raw project_id)}"
CLUSTER_NAME="$(terraform -chdir="${TF_DIR}" output -raw cluster_name)"
CLUSTER_LOCATION="$(terraform -chdir="${TF_DIR}" output -raw cluster_location)"
DNS_POLICY_NAME="$(terraform -chdir="${TF_DIR}" output -raw dns_policy_name)"
DNS_POLICY_LOGGING="$(terraform -chdir="${TF_DIR}" output -raw dns_policy_enable_logging)"
[[ -n "${PROJECT_ID}" && -n "${CLUSTER_NAME}" && -n "${CLUSTER_LOCATION}" ]] || {
  echo "Terraform outputs project_id, cluster_name, and cluster_location are required." >&2
  exit 1
}
[[ "${DNS_POLICY_LOGGING}" == "true" ]] || {
  echo "Terraform output dns_policy_enable_logging is not true." >&2
  exit 1
}

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n 1)"
[[ -n "${ACTIVE_ACCOUNT}" ]] || { echo "No active gcloud account." >&2; exit 1; }
for service in dns.googleapis.com logging.googleapis.com; do
  gcloud services list --enabled --project="${PROJECT_ID}" \
    --filter="config.name:${service}" --format='value(config.name)' | grep -qx "${service}" || {
    echo "${service} is not enabled in ${PROJECT_ID}." >&2
    exit 1
  }
done

kubectl get --raw=/version >/dev/null
kubectl rollout status deployment/test --timeout=5m
POD="${POD:-$(kubectl get pods -l app=test,component=isolated-claude-agent \
  --field-selector=status.phase=Running --sort-by=.metadata.creationTimestamp \
  -o name | tail -n 1 | cut -d/ -f2)}"
[[ -n "${POD}" ]] || { echo "No running test Pod found." >&2; exit 1; }
kubectl get pod "${POD}" -n "${NAMESPACE}" >/dev/null
START_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

DNS_OUTPUT="$(kubectl exec -n "${NAMESPACE}" "${POD}" -- getent ahostsv4 "${TEST_FQDN}")" || {
  echo "Pod ${POD} could not resolve ${TEST_FQDN}." >&2
  exit 5
}
mapfile -t DEST_IPS < <(awk '{print $1}' <<<"${DNS_OUTPUT}" | grep -E '^[0-9]+(\.[0-9]+){3}$' | sort -u)
[[ "${#DEST_IPS[@]}" -gt 0 ]] || {
  echo "Could not resolve an IPv4 address for ${TEST_FQDN} in Pod ${POD}." >&2
  exit 5
}

echo "Project: ${PROJECT_ID}"
echo "Cluster: ${CLUSTER_NAME} (${CLUSTER_LOCATION})"
echo "DNS Policy: ${DNS_POLICY_NAME} (enable_logging=${DNS_POLICY_LOGGING})"
echo "Source Pod: ${NAMESPACE}/${POD}"
echo "Start time (UTC): ${START_TIME}"
echo "Query: ${TEST_FQDN} (IPv4: ${DEST_IPS[*]})"

echo "Generating a denied connection to correlate DNS and policy-action logs..."
if kubectl exec -n "${NAMESPACE}" "${POD}" -- \
  curl --connect-timeout 3 --max-time "${CURL_TIMEOUT_SECONDS}" \
  --fail --silent --show-error "http://${TEST_FQDN}:${TEST_PORT}"; then
  echo "Unexpected success from expected-deny host ${TEST_FQDN}." >&2
  exit 6
fi

DNS_QUERY="resource.type=\"dns_query\" AND timestamp>=\"${START_TIME}\" AND jsonPayload.queryName:\"${TEST_FQDN}\""
DENY_QUERY="resource.type=\"k8s_node\" AND resource.labels.project_id=\"${PROJECT_ID}\" AND resource.labels.location=\"${CLUSTER_LOCATION}\" AND resource.labels.cluster_name=\"${CLUSTER_NAME}\" AND logName=\"projects/${PROJECT_ID}/logs/policy-action\" AND timestamp>=\"${START_TIME}\" AND jsonPayload.disposition=\"deny\" AND (jsonPayload.direction=\"egress\" OR jsonPayload.connection.direction=\"egress\") AND (jsonPayload.src_pod_name=\"${POD}\" OR jsonPayload.src.pod_name=\"${POD}\") AND (jsonPayload.dest_port=${TEST_PORT} OR jsonPayload.connection.dest_port=${TEST_PORT} OR jsonPayload.dest.port=${TEST_PORT})"
ERROR_FILE="$(mktemp)"
trap 'rm -f "${ERROR_FILE}"' EXIT
DEADLINE=$((SECONDS + LOG_TIMEOUT_SECONDS))

while (( SECONDS < DEADLINE )); do
  DNS_JSON=""
  if ! DNS_JSON="$(gcloud logging read "${DNS_QUERY}" --project="${PROJECT_ID}" --limit=50 --format=json 2>"${ERROR_FILE}")"; then
    if grep -Eiq 'permission denied|permission_denied|PERMISSION_DENIED|unauthorized|authentication' "${ERROR_FILE}"; then
      echo "Cloud Logging query permission/authentication error:" >&2
      cat "${ERROR_FILE}" >&2
      exit 2
    fi
    echo "Cloud Logging DNS query failed:" >&2
    cat "${ERROR_FILE}" >&2
    exit 3
  fi

  DENY_JSON=""
  if ! DENY_JSON="$(gcloud logging read "${DENY_QUERY}" --project="${PROJECT_ID}" --limit=50 --format=json 2>"${ERROR_FILE}")"; then
    if grep -Eiq 'permission denied|permission_denied|PERMISSION_DENIED|unauthorized|authentication' "${ERROR_FILE}"; then
      echo "Cloud Logging deny query permission/authentication error:" >&2
      cat "${ERROR_FILE}" >&2
      exit 2
    fi
    echo "Cloud Logging deny query failed:" >&2
    cat "${ERROR_FILE}" >&2
    exit 3
  fi

  MATCH="$(DNS_JSON="${DNS_JSON}" DENY_JSON="${DENY_JSON}" TEST_FQDN="${TEST_FQDN}" DEST_IPS="$(IFS=,; echo "${DEST_IPS[*]}")" POD="${POD}" TEST_PORT="${TEST_PORT}" python3 - <<'PY'
import ipaddress
import json
import os
import re

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

def as_text(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)

def ip_values(value):
    values = []
    for candidate in re.findall(r"[0-9A-Fa-f:.]+", as_text(value)):
        try:
            values.append(str(ipaddress.ip_address(candidate)))
        except ValueError:
            pass
    return sorted(set(values))

try:
    dns_entries = json.loads(os.environ.get("DNS_JSON", "[]"))
    deny_entries = json.loads(os.environ.get("DENY_JSON", "[]"))
except json.JSONDecodeError:
    raise SystemExit(0)

fqdn = os.environ["TEST_FQDN"].rstrip(".").casefold()
pod = os.environ["POD"]
port = int(os.environ["TEST_PORT"])
dns_matches = []
for entry in dns_entries:
    payload = entry.get("jsonPayload", {})
    query_name = as_text(nested(payload, ("queryName",), ("query_name",))).rstrip(".").casefold()
    source_ip = as_text(nested(payload, ("sourceIP",), ("sourceIp",), ("source_ip",)))
    rdata = nested(payload, ("rdata",), ("rData",))
    response_code = as_text(nested(payload, ("responseCode",), ("response_code",)))
    response_ips = set(ip_values(rdata))
    if query_name == fqdn and source_ip and rdata not in (None, "", [], {}) and response_ips:
        dns_matches.append({
            "timestamp": entry.get("timestamp"),
            "queryName": nested(payload, ("queryName",), ("query_name",)),
            "sourceIP": source_ip,
            "responseCode": response_code or "<missing>",
            "rdata": rdata,
            "rdata_ips": sorted(response_ips),
            "insertId": entry.get("insertId"),
        })

deny_matches = []
for entry in deny_entries:
    payload = entry.get("jsonPayload", {})
    source_pod = nested(payload, ("src_pod_name",), ("src", "pod_name"))
    dest_ip = nested(payload, ("dest_ip",), ("destIp",), ("connection", "dest_ip"), ("connection", "destIp"), ("dest", "ip"))
    dest_port = nested(payload, ("dest_port",), ("connection", "dest_port"), ("dest", "port"))
    direction = nested(payload, ("direction",), ("connection", "direction"))
    disposition = payload.get("disposition")
    try:
        port_ok = int(dest_port) == port
    except (TypeError, ValueError):
        port_ok = False
    if source_pod == pod and port_ok and direction == "egress" and disposition == "deny" and dest_ip:
        deny_matches.append({
            "timestamp": entry.get("timestamp"),
            "destinationIP": str(dest_ip),
            "port": dest_port,
            "protocol": nested(payload, ("protocol",), ("connection", "protocol")),
            "count": payload.get("count"),
            "insertId": entry.get("insertId"),
        })

for dns in dns_matches:
    for deny in deny_matches:
        if deny["destinationIP"] in dns["rdata_ips"]:
            print(json.dumps({"dns": dns, "deny": deny}, ensure_ascii=False))
            raise SystemExit(0)
raise SystemExit(0)
PY
  )"
  if [[ -n "${MATCH}" ]]; then
    echo "DNS query and policy-action deny correlation:"
    MATCH="${MATCH}" POD="${POD}" NAMESPACE="${NAMESPACE}" python3 - <<'PY'
import json
import os

result = json.loads(os.environ["MATCH"])
print(json.dumps({
    "pod": f"{os.environ['NAMESPACE']}/{os.environ['POD']}",
    "dns": result["dns"],
    "deny": result["deny"],
    "correlation": "dns.rdata IP matches policy-action destinationIP",
}, ensure_ascii=False, indent=2))
PY
    exit 0
  fi

  remaining=$((DEADLINE - SECONDS))
  (( remaining > 0 )) || break
  sleep "$(( remaining < POLL_INTERVAL_SECONDS ? remaining : POLL_INTERVAL_SECONDS ))"
done

echo "No matching DNS query and policy-action deny correlation found within ${LOG_TIMEOUT_SECONDS}s." >&2
echo "DNS query used: ${DNS_QUERY}" >&2
echo "Deny query used: ${DENY_QUERY}" >&2
echo "Resolved IPv4 addresses: ${DEST_IPS[*]}" >&2
exit 4
