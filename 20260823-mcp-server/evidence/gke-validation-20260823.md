# GKE Standard validation evidence

Terraform created `mcp-20260823-mcp-server-gke` in `us-central1-a`, using VPC `mcp-20260823-mcp-server-vpc`, subnet `mcp-20260823-mcp-server-subnet`, Pod range `10.241.0.0/16`, Service range `10.242.0.0/20`, one `e2-small` node, and dedicated node service account `mcp-20260823-gke-node@nnyn-dev.iam.gserviceaccount.com`. The existing `autopilot` cluster was not modified.

Rendered manifests showed the same immutable image digest in the Deployment and validation Job, a non-root UID 1000 container, an internal `ClusterIP` Service, and Workload Identity annotation for `mcp-20260823-gke-workload@nnyn-dev.iam.gserviceaccount.com`.

`kubectl rollout status deployment/mcp-20260823-mcp-server` succeeded. The disposable `mcp-20260823-validation` Job and a separate registry-discovered URL validation Pod both completed with:

```text
Local MCP smoke test passed: initialize, tools/list, valid call, invalid input.
```
