#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
REPOSITORY_ID="${REPOSITORY_ID:-agent-gateway-20260822}"
IMAGE_NAME="${IMAGE_NAME:-claude-agent-gateway}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URI="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

CERT_ARGS=()
if command -v terraform >/dev/null && command -v jq >/dev/null && [[ -d terraform ]]; then
  gateway_cert="$(terraform -chdir=terraform output -json agent_gateway_root_certificates 2>/dev/null | jq -r 'if type == "array" then .[] else .value[] end' 2>/dev/null || true)"
fi
if [[ -z "${gateway_cert:-}" ]] && command -v gcloud >/dev/null; then
  gateway_cert="$(gcloud network-services agent-gateways describe "${AGENT_GATEWAY_NAME:-agw-20260822-egress}" \
    --project="$PROJECT_ID" --location="$LOCATION" \
    --format='value[delimiter=\\n](agentGatewayCard.rootCertificates)' 2>/dev/null || true)"
fi
if [[ -n "${gateway_cert:-}" ]]; then
  CERT_ARGS+=(--build-arg "AGENT_GATEWAY_ROOT_CERTIFICATES=$gateway_cert")
fi

gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet
docker build "${CERT_ARGS[@]}" --tag "$IMAGE_URI" . >&2
docker push "$IMAGE_URI" >&2
printf '%s\n' "$IMAGE_URI"
