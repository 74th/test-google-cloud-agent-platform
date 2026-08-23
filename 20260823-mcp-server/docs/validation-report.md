# 20260823-mcp-server validation report

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
