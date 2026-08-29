#!/usr/bin/env bash
set -euo pipefail

project_id="${PROJECT_ID:-nnyn-dev}"
location="${REGISTRY_LOCATION:-us-central1}"
tool_spec="${TOOL_SPEC_PATH:-toolspec.json}"
cloud_run_service="${CLOUD_RUN_REGISTRY_SERVICE:-mcp-20260823-cloud-run}"
gke_service="${GKE_REGISTRY_SERVICE:-mcp-20260823-gke}"
cloud_run_url="${CLOUD_RUN_INTERFACE_URL:-}"
gke_url="${GKE_INTERFACE_URL:-https://gke.mcp-20260823.internal/mcp}"

usage() {
  printf '%s\n' "Usage: $0 <apply|search|describe|delete> [cloud-run|gke]"
}

if [[ ! -f "$tool_spec" ]]; then
  printf 'Tool specification not found: %s\n' "$tool_spec" >&2
  exit 2
fi

tool_spec_content="$(tr -d '\n' < "$tool_spec")"

registry_args=(--project="$project_id" --location="$location")
service_name=""
interface_url=""
case "${2:-cloud-run}" in
  cloud-run)
    service_name="$cloud_run_service"
    interface_url="$cloud_run_url"
    ;;
  gke)
    service_name="$gke_service"
    interface_url="$gke_url"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

case "${1:-}" in
  apply)
    [[ -n "$interface_url" ]] || { printf '%s\n' 'An interface URL is required for registry apply.' >&2; exit 2; }
    create_args=("$service_name" "${registry_args[@]}" \
      --display-name="20260823-mcp-server ${2:-cloud-run}" \
      --description="20260823-mcp-server MCP validation entry" \
      --interfaces="protocolBinding=jsonrpc,url=${interface_url}" \
      --mcp-server-spec-type=tool-spec \
      --mcp-server-spec-content="$tool_spec_content")
    if gcloud agent-registry services describe "$service_name" "${registry_args[@]}" --format='value(name)' >/dev/null 2>&1; then
      exec gcloud agent-registry services update "${create_args[@]}"
    fi
    exec gcloud agent-registry services create "${create_args[@]}"
    ;;
  search)
    exec gcloud agent-registry mcp-servers search "${registry_args[@]}" \
      --search-string="${SEARCH_STRING:-displayName:20260823*}" --format=json
    ;;
  describe)
    exec gcloud agent-registry services describe "$service_name" "${registry_args[@]}" --format=json
    ;;
  delete)
    [[ "$service_name" == mcp-20260823-* ]] || { printf '%s\n' 'Refusing to delete a non-experiment service.' >&2; exit 2; }
    exec gcloud agent-registry services delete "$service_name" "${registry_args[@]}" --quiet
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
