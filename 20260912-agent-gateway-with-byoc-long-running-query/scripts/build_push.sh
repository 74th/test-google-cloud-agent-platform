#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-dev-74th-20260912}"
LOCATION="${LOCATION:-us-central1}"
REPOSITORY_ID="${REPOSITORY_ID:-byoc20260912-images}"
IMAGE_NAME="${IMAGE_NAME:-byoc-gateway-longrunning}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
AGENT_GATEWAY_NAME="${AGENT_GATEWAY_NAME:-byoc20260912-egress}"
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
  gcloud network-services agent-gateways describe "$AGENT_GATEWAY_NAME" \
    --project="$PROJECT_ID" --location="$LOCATION" \
    --format='value[delimiter=\\n](agentGatewayCard.rootCertificates)' >"$CERT_FILE" 2>/dev/null || true
fi
if [[ -s "${CERT_FILE:-}" ]]; then
  CERT_ARGS+=(--secret "id=agent_gateway_roots,src=$CERT_FILE")
fi

gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet
docker build "${CERT_ARGS[@]}" --tag "$IMAGE_URI" . >&2
docker push "$IMAGE_URI" >&2
digest="$(gcloud artifacts docker images describe "$IMAGE_URI" --format='value(image_summary.digest)')"
printf '%s\n' "${IMAGE_URI%%:*}@${digest}"
