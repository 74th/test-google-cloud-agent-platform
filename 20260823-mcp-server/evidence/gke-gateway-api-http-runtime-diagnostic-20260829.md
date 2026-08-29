# Agent Runtime to GKE Gateway API HTTP diagnostic: 2026-08-29

This is an explicit private-HTTP routing diagnostic. It is not an authenticated
GKE E2E PASS and does not relax the normal HTTPS validation for Cloud Run or the
`gke` target. No token, key, certificate body, or credential value is recorded.

## Reviewed change and resources

| Item | Observed value |
| --- | --- |
| Agent Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/8548154799411953664` |
| Runtime image | `.../agent-runtime@sha256:de1396843280df69e216e79018196cff410e86bdfe7d4fb414d31dc859621b38` |
| Shared Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Diagnostic Registry Service | `mcp-20260823-gke-http-diagnostic` |
| Diagnostic MCP endpoint | `projects/nnyn-dev/locations/us-central1/mcpServers/agentregistry-00000000-0000-0000-2aa8-3970b3b6771e` |
| Registered interface | `http://gke-gateway-http.mcp-20260823.internal/mcp` |
| Gateway API VIP/listener | `10.240.0.6:80`, `gke-l7-rilb`, `HTTPRoute` to Gateway-specific `ClusterIP` |
| Terraform apply | `2 added, 1 changed, 0 destroyed` |
| Final Terraform plan | `No changes`; scope guard `PASS` |

The container was changed so only the explicit `gke-http-diagnostic` target
accepts an HTTP Registry scheme. `cloud-run` and `gke` continue to accept only
HTTPS. The MCP image was rebuilt and the GKE Deployment rolled out with the
immutable digest `sha256:00ec50e41fde15de8179d6f87c77c556367b7e664d5a61ec32cfa926f11277b1`.

## Independent results

| Layer | Result | Evidence |
| --- | --- | --- |
| Registry discovery | PASS | Runtime Gateway logs show `GET https://agentregistry.googleapis.com/.../mcp-20260829-gke-http-diagnostic` with status 200 and common-egress Authz `ALLOWED`. |
| Token generation/control-plane route | PASS | Runtime Gateway logs show IAM Credentials `generateIdToken` status 200 and Authz `ALLOWED`; token contents were not retained. |
| Runtime to common-egress HTTP request | PASS | Gateway log at `2026-08-29T07:30:00.862682Z` shows `POST http://gke-gateway-http.mcp-20260823.internal/mcp`, `mcpInfo.method=initialize`, policy `ALLOWED`, and HTTP status 400. |
| Gateway API origin delivery | FAIL | The same Gateway record has latency `0.006955s`, response size `212`, and no `serverIp`; the GKE MCP Pod has no log for Runtime correlation `mcp-50d4249945564832a9f31987`. |
| Runtime invocation | FAIL | Runtime returned HTTP 400 / `FAILED_PRECONDITION`, stage `tool_execution`, `Claude returned without a remote Tool execution event`. A second try after the MCP image rollout returned the same stage for `mcp-ad98ab26d4ae4184a83cbb34`, with no Pod execution log. |
| Gateway API to ClusterIP to Pod | PASS (Pod-side diagnostic) | From the GKE Pod, the same HTTP listener returned HTTP 200 for `tools/call`; `mcp-http-diagnostic-marker-20260829` was logged by the Pod with `hostingTarget=gke-http-diagnostic`. |

The Gateway-side HTTP request is therefore proven to leave the Runtime and be
seen by `common-egress`, but this Runtime attempt did not reach the GKE MCP
application. The HTTP `400` was not caused by the consumer's old HTTPS-only
Registry check; that check was explicitly changed and the HTTP request was
observed. This does not by itself prove a universal Agent Runtime HTTP ban,
but it demonstrates that HTTP is not a viable governed GKE E2E path in this
configuration.

## Conclusion

The private HTTP Gateway API route works from inside the VPC/GKE cluster, while
the managed Agent Runtime path reaches common-egress and stops before Pod
execution. The final GKE path remains the authenticated HTTPS front door; this
diagnostic target and its Registry entry must not be treated as its replacement.
