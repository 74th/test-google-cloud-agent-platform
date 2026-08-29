# Registry entry deletion lifecycle: 2026-08-29

The disposable consumer-owned Registry Service
`mcp-20260823-gke-http-diagnostic` and its Runtime-specific
`roles/iap.egressor` binding were removed with a saved two-resource Terraform
plan. The shared Gateway, common Registry endpoints, GKE resources, Runtime,
and Cloud Run Service were not changed.

| Layer | Result |
| --- | --- |
| Delete plan | PASS: exactly the disposable Registry Service and its consumer IAM binding; scope guard PASS |
| Runtime invocation | `2026-08-29T08:36:45Z`–`08:36:47Z`, target `gke-http-diagnostic` |
| Expected | Registry discovery fails with no stale interface fallback |
| Actual | Runtime HTTP 400, `stage=registry_discovery`, `Registry service lookup failed (HTTP 404)`; correlation `mcp-17e9d1e216ad4f0abea5642d` |
| Gateway / endpoint / MCP logs | No Gateway entries; no endpoint credential generation or MCP execution was observed |
| Restore | PASS: Terraform recreated the Service and binding; final refresh-only plan returned no changes |

This satisfies the deletion-side lifecycle check without treating the private
HTTP diagnostic as a governed GKE result. No token, key, certificate body, or
credential value was stored.
