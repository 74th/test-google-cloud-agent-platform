#!/usr/bin/env bash
set -euo pipefail

project_id="${PROJECT_ID:-nnyn-dev}"
region="${REGION:-us-central1}"
repository="${REPOSITORY_ID:-mcp-20260823-mcp-server-agent}"
image_name="${IMAGE_NAME:-agent-runtime}"
tag="${IMAGE_TAG:-20260823-r1}"

registry="${region}-docker.pkg.dev/${project_id}/${repository}"
image="${registry}/${image_name}:${tag}"

cert_args=()
gateway_cert=""
if command -v gcloud >/dev/null; then
  gateway_cert="$(gcloud network-services agent-gateways describe "${AGENT_GATEWAY_NAME:-agw-20260822-egress}" \
    --project="${project_id}" --location="${region}" \
    --format='value[delimiter=\\n](agentGatewayCard.rootCertificates)' 2>/dev/null || true)"
fi
if [[ -n "${gateway_cert}" ]]; then
  cert_args+=(--build-arg "AGENT_GATEWAY_ROOT_CERTIFICATES=${gateway_cert}")
fi

gcloud auth configure-docker "${region}-docker.pkg.dev" --quiet >/dev/null
docker build "${cert_args[@]}" --file agent_runtime/Dockerfile --tag "${image}" .
docker push "${image}" >/dev/null
digest="$(gcloud artifacts docker images describe "${image}" --format='value(image_summary.digest)' --project="${project_id}")"
test -n "${digest}"
printf '%s\n' "${registry}/${image_name}@${digest}"
