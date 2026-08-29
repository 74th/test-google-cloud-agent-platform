# GKE Gateway API through common-egress: 2026-08-29

This is a bounded comparison of the consumer-owned GKE Gateway API path. It is
not an authenticated Agent Runtime E2E PASS. No access token, private key,
OAuth secret, or certificate body is recorded.

## Ownership and reversible switch

| Item | Owner / observed value | Result |
| --- | --- | --- |
| Shared Gateway | common: `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` | unchanged; not in consumer state |
| GKE Registry Service | consumer Terraform: `mcp-20260823-gke` | PASS |
| GKE MCP endpoint IAM | consumer Terraform: Runtime principal + `roles/iap.egressor` | PASS; endpoint-scoped |
| Common control-plane endpoint IAM | consumer Terraform data sources + Runtime-scoped bindings | PASS; common Service/Endpoint resources were not recreated |
| DNS probe switch | consumer Terraform `enable_gateway_api_https_probe=true` | one in-place record update, `0 added / 1 changed / 0 destroyed` |
| DNS restored | `gke.mcp-20260823.internal -> 10.240.0.2` | PASS; legacy HTTPS Ingress restored |
| Scope guard | consumer plan JSON | PASS; no common resource action |

The probe temporarily pointed the existing registered hostname at the Gateway
API VIP `10.240.0.6`, so the Runtime configuration, Registry Service ID, and
endpoint IAM remained unchanged. A second reviewed plan restored the hostname
to the existing Internal HTTPS Ingress VIP `10.240.0.2`; that plan also had no
destroy action.

## HTTP path result

The Agent Runtime -> common-egress -> Gateway API HTTP path was **not tested as
a network request**. The current custom Agent Runtime container's
`agent_service/registry.py` requires the resolved interface scheme to be
`https`; an HTTP interface would be rejected before credential generation and
before any Gateway request. This is a consumer-container guard, not proof that
the managed Agent Runtime platform or common-egress itself rejects HTTP. The
HTTP listener was therefore tested only from a GKE Pod as the separate routing
diagnostic recorded in [the HTTP evidence](gke-gateway-api-http-diagnostic-20260829.md).

| Path | Result | Evidence boundary |
| --- | --- | --- |
| GKE Pod -> Gateway API HTTP:80 | PASS | `initialize`/`tools/call` HTTP 200 and Pod log |
| Agent Runtime -> common-egress -> Gateway API HTTP:80 | NOT TESTED | Current custom-container HTTPS-only Registry validation; no HTTP Gateway request or server log |
| Agent Runtime -> common-egress -> Gateway API HTTPS:443 | FAIL before origin execution | Gateway `ALLOWED`, then HTTP 503; recorded below |

## Gateway API HTTPS route

| Layer | Observed value | Result |
| --- | --- | --- |
| GatewayClass | `gke-l7-rilb`, controller `networking.gke.io/gateway` | PASS |
| Gateway | `mcp-20260823-gke-gateway`, `HTTPS:443`, VIP `10.240.0.6` | `Programmed=True`, `GatewayHealthy=True` |
| HTTPRoute | `gke.mcp-20260823.internal/mcp` -> `mcp-20260823-gateway-backend:80` | `Reconciled=True` |
| Forwarding rule | regional `INTERNAL_MANAGED`, `10.240.0.6:443` | PASS |
| Backend | Gateway-specific `ClusterIP 10.242.7.20`, Pod `10.241.0.13:8080` | healthy |
| Certificate | out-of-band self-managed test certificate for `gke.mcp-20260823.internal` | private test CA; not suitable for common-egress origin TLS |

## Independent probes

The in-cluster HTTPS probe trusted the test certificate without disabling TLS
verification and returned HTTP 200 for `initialize`, `tools/list`, and
`tools/call`. The tool result and Pod log shared:

```text
correlationId=mcp-gateway-api-pod-20260829
hostingTarget=gke
event=mcp_tool_execution
```

This proves Gateway API HTTPS termination and routing to the MCP Pod from a
GKE Pod. It does not prove the common-egress origin hop.

The Agent Runtime query used target `gke` with the same Registry Service and
returned:

```text
HTTP 400 / FAILED_PRECONDITION
stage=tool_execution
error=Claude returned without a remote Tool execution event
```

The corresponding common-egress Gateway record at
`2026-08-29T06:51:56.599391Z` contained the following sanitized facts:

```text
agentRegistryResource=projects/776113568960/locations/us-central1/mcpServers/agentregistry-00000000-0000-0000-488d-bdd363d88393
mcpInfo.method=initialize
hostname=gke.mcp-20260823.internal
authzPolicyInfo.result=ALLOWED
matchedRules[0].action=ALLOWED
requestWasTlsIntercepted=true
status=503
```

Runtime correlation was `mcp-62651073b89b4539bdb362bc`. No GKE application
execution log for that correlation was observed. Therefore the result is:

| Layer | Result | Interpretation |
| --- | --- | --- |
| Registry discovery | PASS | Runtime resolved the consumer GKE Service and its endpoint |
| common-egress authorization | PASS | Registry MCP endpoint and Authz policy returned `ALLOWED` |
| Gateway API origin delivery | FAIL | common-egress returned HTTP 503 before GKE application execution |
| GKE endpoint authorization | NOT REACHED | no independent IAP/equivalent authorization result |
| Claude Tool selection | FAIL | Runtime reported no remote Tool execution event |
| Agent Runtime -> Gateway API -> GKE E2E | NOT PASS | no correlated server-side Tool execution |

The outcome is consistent with the earlier Internal HTTPS Load Balancer test:
the origin uses a private self-managed CA. The Runtime image's Agent Gateway
inspection CA covers the Runtime-to-Gateway hop; it does not make the GKE
origin certificate publicly trusted. The private HTTP listener remains a
routing diagnostic only. A future authenticated E2E requires a publicly
trusted certificate and an independent GKE endpoint authorization boundary.
