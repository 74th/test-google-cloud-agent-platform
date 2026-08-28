#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-nnyn-dev}"
LOCATION="${LOCATION:-us-central1}"
REPOSITORY_ID="${REPOSITORY_ID:-agent-gateway-20260828}"
IMAGE_NAME="${IMAGE_NAME:-claude-agent-gateway}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URI="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_ID}/${IMAGE_NAME}:${IMAGE_TAG}"

CERT_ARGS=()
CERT_FILE=""
cleanup() {
  if [[ -n "$CERT_FILE" ]]; then
    rm -f -- "$CERT_FILE"
  fi
}
trap cleanup EXIT
if command -v gcloud >/dev/null; then
  CERT_FILE="$(mktemp)"
  gcloud network-services agent-gateways describe "${AGENT_GATEWAY_NAME:-common-egress}" \
    --project="$PROJECT_ID" --location="$LOCATION" \
    --format='value[delimiter=\\n](agentGatewayCard.rootCertificates)' >"$CERT_FILE" 2>/dev/null || true
fi
if [[ -s "${CERT_FILE:-}" ]]; then
  CERT_ARGS+=(--secret "id=agent_gateway_roots,src=$CERT_FILE")
fi

gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet
docker build "${CERT_ARGS[@]}" --tag "$IMAGE_URI" . >&2
docker push "$IMAGE_URI" >&2
printf '%s\n' "$IMAGE_URI"
