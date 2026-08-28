#!/usr/bin/env bash
set -euo pipefail

image="${1:-}"
if [[ ! "$image" =~ @sha256:[0-9a-f]{64}$ ]]; then
  printf '%s\n' 'Usage: check_agent_runtime_image.sh IMAGE@sha256:<64 hex digits>' >&2
  exit 2
fi

docker run --rm "$image" sh -ceu '
  test -s /usr/local/share/ca-certificates/agent-gateway.crt
  openssl x509 -in /usr/local/share/ca-certificates/agent-gateway.crt -noout >/dev/null
  openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt /usr/local/share/ca-certificates/agent-gateway.crt
'
printf '%s\n' "container trust check: PASS image=$image"
