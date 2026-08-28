#!/usr/bin/env bash
set -euo pipefail
hash -r 2>/dev/null || true

project_id="${PROJECT_ID:-nnyn-dev}"
region="${REGION:-us-central1}"
gateway_id="${AGENT_GATEWAY_ID:-}"
gcloud_bin="${GCLOUD_BIN:-gcloud}"
repository="${REPOSITORY_ID:-mcp-20260823-mcp-server-agent}"
image_name="${IMAGE_NAME:-agent-runtime}"
tag="${IMAGE_TAG:-20260823-r1}"

expected_gateway_id="projects/nnyn-dev/locations/us-central1/agentGateways/common-egress"
if [[ "$gateway_id" != "$expected_gateway_id" ]]; then
  printf '%s\n' 'AGENT_GATEWAY_ID must be the reviewed common-egress resource ID.' >&2
  exit 2
fi

registry="${region}-docker.pkg.dev/${project_id}/${repository}"
image="${registry}/${image_name}:${tag}"

gateway_cert="$("$gcloud_bin" network-services agent-gateways describe "$gateway_id" \
  --project="$project_id" --location="$region" \
  --format='value[delimiter=\\n](agentGatewayCard.rootCertificates)')"
if [[ -z "$gateway_cert" ]]; then
  printf '%s\n' 'Selected Gateway returned no TLS inspection root certificate.' >&2
  exit 1
fi
certificate_count="$(printf '%s\n' "$gateway_cert" | awk '/BEGIN CERTIFICATE/ {count++} END {print count+0}')"
if [[ "$certificate_count" -lt 1 ]] || ! printf '%s\n' "$gateway_cert" | openssl x509 -noout >/dev/null 2>&1; then
  printf '%s\n' 'Selected Gateway returned invalid TLS inspection root certificate data.' >&2
  exit 1
fi
certificate_fingerprint="$(printf '%s\n' "$gateway_cert" | openssl x509 -noout -fingerprint -sha256)"
printf 'gateway=%s root_certificate_count=%s %s\n' "$gateway_id" "$certificate_count" "$certificate_fingerprint" >&2

"$gcloud_bin" auth configure-docker "${region}-docker.pkg.dev" --quiet >/dev/null
AGENT_GATEWAY_ROOT_CERTIFICATES="$gateway_cert" docker build \
  --secret id=agent-gateway-ca,env=AGENT_GATEWAY_ROOT_CERTIFICATES \
  --file agent_runtime/Dockerfile --tag "${image}" .
docker push "${image}" >/dev/null
digest="$("$gcloud_bin" artifacts docker images describe "${image}" --format='value(image_summary.digest)' --project="${project_id}")"
test -n "${digest}"
printf '%s\n' "${registry}/${image_name}@${digest}"
