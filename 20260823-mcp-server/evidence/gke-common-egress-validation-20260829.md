# GKE common-egress validation: 2026-08-29

This is a sanitized consumer-side validation record. It contains no access
token, private key, certificate body, or credential value.

## Rebuild and ownership

| Item | Observed value | Result |
| --- | --- | --- |
| Terraform apply | `15 added, 1 changed, 0 destroyed` | PASS |
| GKE cluster | `mcp-20260823-mcp-server-gke` / `RUNNING` / `us-central1-a` | PASS |
| VPC | `common-agent-gateway-vpc` | PASS; common-owned VPC referenced by data source |
| GKE subnet | `mcp-20260823-mcp-server-subnet` / `10.240.0.0/20` | PASS; consumer-owned |
| Pod secondary range | `10.241.0.0/16` | PASS |
| Service secondary range | `10.242.0.0/20` | PASS |
| common Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` | unchanged |
| Post-apply Terraform plan | `No changes` | PASS |

The apply did not manage or change the common VPC, common subnet, Network
Attachment, Gateway, or the existing Autopilot cluster.

## ClusterIP baseline

The MCP Deployment reached `1/1 Ready` with immutable image digest
`sha256:95bd813c196cad3f005f66bd91739d5d726b835e59ffedcf4badc273ff8d4d75`.
The Service remained:

```text
type=ClusterIP
clusterIP=10.242.0.20
externalIP=<none>
port=80/TCP
```

The in-cluster validation Job completed successfully. This proves the
cluster-local MCP path only; it is not Agent Runtime E2E evidence.

## Internal HTTPS Load Balancer

| Layer | Observed value | Result |
| --- | --- | --- |
| Frontend | `INTERNAL_MANAGED` / `10.240.0.2` / `gce-internal` | PASS |
| Frontend protocol | HTTPS; HTTP disabled by Ingress annotation | PASS |
| Private DNS | `gke.mcp-20260823.internal -> 10.240.0.2` on `common-agent-gateway-vpc` | PASS |
| Proxy-only subnet | `10.244.0.0/23` / `REGIONAL_MANAGED_PROXY` / `ACTIVE` | PASS |
| Backend | MCP NEG `HEALTHY`, Pod `10.241.0.13:8080` | PASS |
| ClusterIP preservation | ILB backend is `mcp-20260823-mcp-server:80`; Service remains ClusterIP | PASS |

A temporary private root CA and leaf certificate were supplied out of band to
the Kubernetes TLS Secret. The root CA was mounted separately into the probe;
TLS 1.3 certificate verification succeeded without `-k` or another
verification bypass.

The correlated in-cluster MCP call returned HTTP 200 and the Pod emitted:

```text
correlationId=mcp-ilb-20260829-corr3
hostingTarget=gke
event=mcp_tool_execution
```

This proves the ILB-to-ClusterIP-to-Pod path from a GKE Pod. The TLS Secret and
root CA are test resources and their key/certificate contents are not stored
in this repository or evidence.

## Agent Runtime through common-egress

The bounded Runtime query used target `gke` and returned:

```text
HTTP 400 / FAILED_PRECONDITION
correlation_id=mcp-910b8e8797d24e9b9ff43c7a
stage=tool_execution
error=Claude returned without a remote Tool execution event
```

The same-window common-egress Gateway record contained:

```text
requestUrl=https://gke.mcp-20260823.internal/mcp
mcpInfo.method=initialize
authzPolicyInfo.result=ALLOWED
enforcedGatewaySecurityPolicy.matchedRules[0].action=ALLOWED
status=503
```

No GKE application execution record was observed for this Runtime
correlation. Therefore the result is:

| Layer | Result | Interpretation |
| --- | --- | --- |
| Registry discovery | PASS | Runtime resolved `mcp-20260823-gke` and the approved HTTPS host |
| common-egress authorization | PASS | Gateway policy and egress Authz returned `ALLOWED` |
| Gateway-to-ILB origin delivery | FAIL | Gateway returned HTTP 503 before MCP execution |
| GKE endpoint authorization | BLOCKED | No IAP or equivalent caller authorization is configured |
| Claude GKE Tool selection | FAIL | Runtime stopped without a remote Tool event |
| GKE Agent Runtime E2E | NOT PASS | No correlated Runtime-to-Pod execution evidence |

The 503 demonstrates that the in-cluster ILB path and the Gateway egress
authorization are separate from successful Gateway-to-origin delivery. The
follow-up read-only diagnosis found that the GKE frontend uses a self-managed
private test CA. Google's Agent Gateway troubleshooting guidance does not
support public or private destinations with self-signed certificate chains; a
publicly trusted origin certificate is required. The Runtime-side Gateway CA
is already installed and verified, so adding that CA again would not address
the origin hop. No anonymous or plain-HTTP fallback was used. Detailed
evidence is in
[`gke-gateway-origin-cert-blocker-20260829.md`](gke-gateway-origin-cert-blocker-20260829.md).

## Current next action

The consumer-side ILB/backend baseline is complete. The remaining blockers are
a publicly trusted certificate/authorized hostname for Gateway origin delivery
and an independent GKE endpoint authorization boundary. The common Gateway and
its policy remain outside this consumer Terraform state.
