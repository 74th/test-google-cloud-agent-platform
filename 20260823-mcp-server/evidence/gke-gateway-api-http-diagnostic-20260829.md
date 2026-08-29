# GKE Gateway API HTTP diagnostic evidence (2026-08-29)

This is a private-VPC routing diagnostic, not an authenticated Agent Runtime
E2E result. The HTTP listener intentionally has no IAP policy. No token,
private key, OAuth secret, or certificate body is recorded here.

## Configuration

| Layer | Observed value | Result |
| --- | --- | --- |
| GKE cluster | `mcp-20260823-mcp-server-gke`, Standard, `common-agent-gateway-vpc` | PASS |
| Gateway API | CRDs installed by `gateway_api_config.channel=CHANNEL_STANDARD` | PASS |
| GatewayClass | `gke-l7-rilb`, controller `networking.gke.io/gateway`, Accepted `True` | PASS |
| Gateway | `mcp-20260823-gke-gateway`, HTTP listener port 80, `Programmed=True`, `GatewayHealthy=True` | PASS |
| Gateway VIP | `10.240.0.6`, regional `INTERNAL_MANAGED`, TCP `80-80` | PASS |
| HTTPRoute | `gke-gateway-http.mcp-20260823.internal/mcp` to `mcp-20260823-gateway-backend:80`, Reconciled `True` | PASS |
| HealthCheckPolicy | HTTP `/healthz` on fixed port 8080, target `mcp-20260823-gateway-backend` | PASS |
| Backend health | NEG endpoint `10.241.0.13:8080`, `HEALTHY` | PASS |
| Kubernetes backend | Gateway-specific `ClusterIP` Service `10.242.7.20`; original MCP `ClusterIP 10.242.0.20` remains | PASS |
| Public exposure | No public forwarding rule; frontend is `INTERNAL_MANAGED` | PASS |

## Reconciliation finding

The first manifest used the standard Gateway API `IPAddress` address type.
GKE returned `GWCER106` and explicitly reported that this GatewayClass only
supports `NamedAddress`. The manifest was corrected to:

```yaml
addresses:
- type: NamedAddress
  value: mcp-20260823-mcp-server-gke-gateway-vip
```

The Gateway then reconciled successfully. The static address is reserved by
Terraform with purpose `SHARED_LOADBALANCER_VIP`.

## Terraform scope

The Gateway API infrastructure plan created one consumer VIP and enabled the
GKE Gateway API channel, with no destroy actions. The follow-up DNS plan added
the diagnostic hostname and restored the existing HTTPS hostname to the
legacy HTTPS VIP, also with no destroy actions. The final refreshed Terraform
plan returned `No changes`. No shared Gateway, common VPC, common subnet,
Network Attachment, or common policy was managed by these plans.

## MCP probe

A temporary non-host-network Pod in the same GKE cluster resolved
`gke-gateway-http.mcp-20260823.internal` and sent MCP requests to the HTTP listener. The
Pod was deleted after logs were collected.

| Request | Actual result |
| --- | --- |
| `initialize` | HTTP 200; server `mcp-server-20260823-mcp-server`, protocol `2025-06-18` |
| `tools/call validate_echo` | HTTP 200; `ok=true`, `hostingTarget=gke` |
| correlation | `mcp-gateway-http-final4-20260829` |
| server log | `mcp_tool_execution`, same correlation and `hostingTarget=gke` |

This proves the following path only:

```text
GKE Pod (10.241.0.33)
  -> private DNS gke-gateway-http.mcp-20260823.internal
  -> GKE Gateway API gke-l7-rilb / regional INTERNAL_MANAGED ALB (10.240.0.6:80)
  -> HTTPRoute
  -> gateway-backend ClusterIP (10.242.7.20:80)
  -> MCP Pod (10.241.0.13:8080)
```

It does not prove Agent Runtime routing, `common-egress` authorization,
endpoint IAM/IAP authorization, or a production-safe TLS configuration.
The existing HTTPS Ingress remains separate because GKE does not allow one
Service to be referenced by both a Gateway and an Ingress. A second
ClusterIP Service with the same Pod selector is therefore used for this
non-destructive comparison.
