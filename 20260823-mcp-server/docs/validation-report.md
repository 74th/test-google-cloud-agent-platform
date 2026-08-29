# 20260823-mcp-server validation report

## 2026-08-29 common-egress migration matrix

The consumer-only GKE rebuild plan was applied with `15 added, 1 changed, 0 destroyed`.
The post-apply plan returned `No changes`. The common VPC and Gateway remained
outside the consumer state.
The following current results supersede any old-Gateway E2E claim:

| Validation item | Status | Caller / identity / source / Gateway / destination / authorization layer / correlation / expected vs actual / log |
| --- | --- | --- | --- |
| Shared Gateway preflight | PASS | operator; consumer Terraform and live API; `common-egress`; exact project/location/direction/protocol/Registry/attachment; expected match, actual match; sanitized inventory evidence |
| Consumer plan/apply scope | PASS | Terraform consumer state; Runtime association is the only shared value; expected no common action, actual `0/0/0`; apply/read-back evidence |
| Runtime identity and association | PASS | Runtime `AGENT_IDENTITY`; effective identity is the Runtime principal; source Runtime API; `common-egress`; expected exact digest/association, actual exact match; migration read-back evidence |
| Registry/control-plane/IAM read-back | PASS | Runtime principal and separate caller/service-agent identities; consumer Registry resources and scoped bindings; expected Terraform/live match, actual match; IAM and migration evidence |
| Runtime Registry discovery through `common-egress` | PASS | Runtime effective identity resolved `mcp-20260823-cloud-run` and the GKE Service; Gateway allowed the current Registry requests |
| Cloud Run governed Agent Runtime / Claude E2E | PASS | Gateway `ALLOWED`, Claude Tool-selection event, Cloud Run HTTP 200, and server-side MCP execution share correlation `mcp-2af5cd7c240946acbdbb4694` [Evidence](../evidence/cloud-run-common-egress-validation-20260829.md) |
| Cloud Run negative cases after migration | PARTIAL | no-token and unauthorized operator credential were rejected before execution; wrong-audience and separate unauthorized ID-token cases remain SKIP [Evidence](../evidence/cloud-run-common-egress-negative-20260829.md) |
| Cloud Run Registry-unbound egress diagnostic | FAIL / unresolved | Consumer binding was removed and restored using scoped plans, but Runtime still received HTTP 200, Gateway logged Cloud Run MCP `ALLOWED`, and Cloud Run executed the Tool. No default-deny PASS is claimed [Evidence](../evidence/cloud-run-egress-unbind-diagnostic-20260829.md) |
| GKE private network/TLS/backend route | PASS | consumer-owned private DNS, `gce-internal` `INTERNAL_MANAGED` frontend `10.240.0.2`, proxy-only subnet, trusted TLS from a validation Pod, healthy NEG, and ClusterIP `10.242.0.20` backend [Evidence](../evidence/gke-common-egress-validation-20260829.md) |
| GKE Agent Runtime egress through common-egress | PASS | Registry discovery and Gateway/Authz were `ALLOWED`; the request reached the GKE hostname path but returned HTTP 503 before MCP execution |
| GKE Agent Runtime / Claude E2E through common-egress | FAIL | Runtime correlation `mcp-147a24d168a2462bb8d2b4e5` reached Gateway `ALLOWED` but received HTTP 503 before ILB origin delivery; the ILB uses an unsupported self-managed private CA and no GKE application execution exists [Evidence](../evidence/gke-gateway-origin-cert-blocker-20260829.md) |
| GKE Gateway API private HTTP routing diagnostic | PASS (diagnostic only) | `gke-l7-rilb` Gateway `Programmed/Healthy=True`, static VIP `10.240.0.6`, HTTPRoute and NEG healthy; GKE Pod `initialize` and `tools/call` returned HTTP 200 with server correlation [Evidence](../evidence/gke-gateway-api-http-diagnostic-20260829.md) |
| Agent Runtime -> common-egress -> Gateway API HTTP | FAIL (routing diagnostic) | After adding the explicit `gke-http-diagnostic` target and rebuilding the container, Gateway logged the HTTP `POST` with Authz `ALLOWED` but returned HTTP 400 before origin delivery; Runtime stopped at `tool_execution` and no GKE Pod execution log exists [Evidence](../evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md) |
| GKE Gateway API through common-egress | FAIL before origin execution | Gateway API HTTPS listener `10.240.0.6:443` was `Programmed=True`; common-egress Registry/Authz was `ALLOWED` but returned HTTP 503 for the private self-managed origin certificate. In-cluster Gateway API probe was HTTP 200, while Runtime correlation `mcp-62651073b89b4539bdb362bc` had no GKE execution log [Evidence](../evidence/gke-gateway-api-common-egress-20260829.md) |
| GKE Gateway API authenticated HTTPS/IAP E2E | SKIP | HTTP diagnostic has no IAP policy; OAuth client/secret, trusted HTTPS origin, endpoint authorization, and Agent Runtime image support for the HTTP diagnostic are not an authenticated E2E result |

The old-Gateway rows below are retained only as `HISTORICAL BASELINE`. They are
not migration results; their PASS evidence includes the required old-run Tool
selection and server-side execution logs, but it must not be reused for the
`common-egress` migration.

## Historical baseline (old Gateway, 2026-08-23/24)

Collected 2026-08-23 in `nnyn-dev`. PASS entries below reference sanitized summaries in `evidence/`; no result is inferred from configuration alone.

| Validation item | Status | Expected / actual / evidence |
| --- | --- | --- |
| Local initialization, `tools/list`, valid call, invalid input | PASS | Expected all four protocol paths; `npm test` and local smoke passed. [Evidence](../evidence/cloud-run-validation-20260823.md) |
| Tool specification consistency | PASS | Expected no difference in name, description, or schema; `npm run check:tool-spec` and container URL check passed. |
| GKE-disabled Terraform plan | PASS | Expected create-only experiment scope; 15 add, 0 change, 0 destroy. [Plan summary](../evidence/terraform-plan-gke-disabled-20260823.md) |
| Cloud Run authenticated MCP | PASS | Expected IAM-authorized execution; initialize, list, and call returned HTTP 200. [Evidence](../evidence/cloud-run-validation-20260823.md) |
| Cloud Run unauthenticated rejection | PASS | Expected pre-MCP rejection; request returned HTTP 403 and no Tool response. [Evidence](../evidence/cloud-run-validation-20260823.md) |
| Cloud Run Agent Registry registration/search | PASS | Expected projected Server and Tool; service create and search returned the Cloud Run interface and `validate_echo`. [Evidence](../evidence/registry-validation-20260823.md) |
| Cloud Run idle instance observation | PASS | Expected an available metric and zero active instances; Monitoring API returned `run.googleapis.com/container/instance_count` with active `0`. [Evidence](../evidence/cloud-run-validation-20260823.md) |
| Cloud Run post-idle vs warm latency | SKIP | The operator-only ID-token mint prerequisite was intermittently denied during the dedicated timing attempt. No latency PASS is claimed; repeat after stable token-mint permission. |
| GKE Standard plan/apply | PASS | Expected dedicated VPC/ranges and no existing-cluster changes; cluster and node pool reached Ready. [Evidence](../evidence/gke-validation-20260823.md) |
| GKE MCP execution | PASS | Expected cluster-local execution; rollout, Job, and registry-discovered Pod check passed. [Evidence](../evidence/gke-validation-20260823.md) |
| GKE Agent Registry registration/search | PASS | Expected separate entry and Tool metadata; `mcp-20260823-gke` projected and search returned `validate_echo`. [Evidence](../evidence/registry-validation-20260823.md) |

## Comparison and conclusion

Cloud Run was the preferred host for this stateless MCP server. Its deployment path was a small Terraform phase plus one immutable image, IAM-only invocation worked without an external load balancer, and minimum instances were configured at zero. GKE required a dedicated VPC, secondary ranges, Standard control plane, node pool, Kubernetes workload, and in-cluster validation; its control plane took about 10 minutes to provision and continues to incur infrastructure cost while enabled.

GKE is justified when cluster-local reachability, Kubernetes scheduling/network policy, shared platform services, or other resident workloads are requirements. It is not justified here solely to host one stateless MCP endpoint. Limitations include a single-zone/e2-small comparison, no production HA/upgrade test, and the skipped cold-vs-warm latency measurement. Before production, repeat the timing test with stable operator IAM, use regional capacity, define SLOs, test rollout/rollback, and review Registry networking/authentication for the intended consumers.

## Remaining and teardown matrix

| Required item | Status | Evidence / limitation |
| --- | --- | --- |
| Runtime direct ID-token mint vs dedicated caller chain | PARTIAL | Direct mint cannot be independently exercised because the managed Runtime principal is not an operator impersonation target. The fallback dedicated caller chain, Runtime-only OpenID Token Creator, exact-audience Cloud Run success, no-key operation, and denied mint for a separate Service Account are evidenced |
| Create-only Terraform plan for all phases | PASS | Fresh temporary-state plan: 49 add, 0 change, 0 destroy; scope guard PASS; existing consumer state unchanged. [Evidence](../evidence/create-only-plan-20260829.md) |
| Cloud Run no-token / wrong-audience / unauthorized identity | PARTIAL | No-token and operator OAuth rejection are PASS; wrong-audience and separate unauthorized ID-token cases are SKIP because no approved operator mint path exists |
| Registry-unbound Cloud Run egress deny | FAIL / unresolved | Binding removal did not change the observed `ALLOWED`/execution path; restored immediately. [Evidence](../evidence/cloud-run-egress-unbind-diagnostic-20260829.md) |
| Registry interface update | PARTIAL | Runtime re-resolved the updated `/mcp?lifecycle=20260829` URL, but Gateway returned HTTP 403 before Cloud Run execution; the exact `/mcp` interface was restored and a later positive probe succeeded. [Evidence](../evidence/registry-lifecycle-update-20260829.md) |
| Registry entry deletion | PASS | Disposable diagnostic Service deletion produced Runtime `registry_discovery / HTTP 404`, zero Gateway entries, and no stale execution; Service and binding were restored with a no-change final plan. [Evidence](../evidence/registry-lifecycle-delete-20260829.md) |
| Registry mutation with Runtime identity | SKIP | No Runtime-identity mutation attempt was performed; local per-invocation cache tests are PASS |
| Teardown inventory and saved plan | PASS | 49 consumer-owned delete actions; shared Gateway/common endpoints, existing Autopilot, and default VPC excluded; applied after operator request. [Evidence](../evidence/teardown-apply-20260829.md) |

No GKE HTTP diagnostic is counted as a governed authorization or Agent Runtime
E2E PASS. No Claude E2E result is PASS without both SDK Tool-selection and
server-side execution evidence.
