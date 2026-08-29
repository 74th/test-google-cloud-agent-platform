# GKE common-egress origin TLS blocker: 2026-08-29

This is a sanitized diagnosis. No access token, private key, certificate body,
or credential value is recorded.

## Observed configuration

| Item | Observation | Result |
| --- | --- | --- |
| Agent Runtime image trust | The selected `common-egress` Gateway inspection root CA is installed and verified in the Runtime image | PASS for Runtime-to-Gateway TLS trust |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`, Network Attachment accepted, `AGENT_TO_ANYWHERE` / `MCP` | PASS |
| Gateway decision | `gke.mcp-20260823.internal` / Registry MCP server / `initialize` / Authz `ALLOWED` | PASS |
| GKE origin certificate | Self-managed certificate for `gke.mcp-20260823.internal`, issued by the experiment's private test root | Not supported by Agent Gateway |
| Gateway response | HTTP 503, `status=503`, `latency=0.098141s`, no origin `serverIp` in the Gateway record | FAIL before origin delivery |
| ILB backend window | No `internal_http_lb_rule` request in `2026-08-29T03:42:40Z`--`03:43:10Z`; the latest matching backend records are validation Pod traffic with HTTP 200 | No Runtime-origin request observed |
| GKE in-cluster path | TLS verification enabled, ILB `10.240.0.2`, healthy NEG, MCP HTTP 200 | PASS for Pod-to-ILB-to-Pod only |

The Runtime query correlation was `mcp-147a24d168a2462bb8d2b4e5`. The Gateway
record at `2026-08-29T03:42:49.533886Z` had the same MCP `initialize` attempt,
egress and Authz `ALLOWED`, and HTTP 503. No GKE application execution log for
that correlation exists.

## Cause and required change

Google's [Agent Gateway troubleshooting guidance](https://cloud.google.com/gemini-enterprise-agent-platform/troubleshooting/troubleshoot-agent-gateway)
states that public or private destinations with self-signed certificate chains
are not supported and requires a publicly trusted CA. Therefore adding the
Agent Gateway Root CA to the Runtime image cannot fix this failure: that CA
authenticates the Runtime-to-Gateway TLS inspection hop, not the GKE
Gateway-to-origin certificate.

The current `.internal` hostname cannot obtain a public CA certificate. To
continue the private-LB E2E, an operator-authorized hostname under a domain with
public CA/DNS control is required, with split-horizon/private DNS resolving it
to `10.240.0.2` in `common-agent-gateway-vpc`. The certificate must be
publicly trusted and include the exact hostname. This requires updating the
consumer Registry interface, GKE Ingress certificate, Runtime audience/host
allowlist, and private DNS together; it does not require changing the shared
Gateway, VPC, subnet, Network Attachment, or common policy.

Endpoint authorization is a separate blocker: the current Ingress has no IAP
or equivalent caller-authorization configuration. No GKE E2E PASS is claimed.
