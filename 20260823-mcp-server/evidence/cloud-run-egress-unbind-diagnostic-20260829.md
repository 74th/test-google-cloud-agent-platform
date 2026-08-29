# Cloud Run egress-unbind diagnostic: 2026-08-29

This was a bounded consumer-side diagnostic for the unregistered or
Registry-unbound negative case. The shared `common-egress` Gateway and all
common-owned resources were left unchanged. The consumer-owned Cloud Run MCP
server `roles/iap.egressor` binding for the current Runtime principal was
removed with a one-resource saved Terraform plan and then restored with a
normal saved plan.

| Item | Result |
| --- | --- |
| Removal plan | PASS: exactly `google_iap_agent_registry_mcp_server_iam_member.cloud_run` destroy; scope guard PASS |
| Runtime probe | `2026-08-29T08:11:53Z`–`08:12:04Z`, target `cloud-run`, Runtime `8548154799411953664` |
| Expected | Gateway default-deny before Cloud Run application execution |
| Actual Runtime result | HTTP 200; Claude returned a successful `cloud-run` Tool result |
| Gateway result | Cloud Run MCP `initialize`, `tools/list`, `notifications/initialized`, and `tools/call` were HTTP 200/202 and `ALLOWED`; Gateway also allowed the required Vertex request |
| Cloud Run result | `mcp_tool_execution` was observed with correlation `mcp-7450553f9c224459a0d4db1a` |
| Restore | PASS: one-resource create plan, scope guard PASS, binding restored; no Runtime update in the final restore plan |

The removal therefore did not demonstrate a Gateway deny. It is retained as a
diagnostic FAIL/SKIP for task 5.3 rather than being promoted to a default-deny
PASS. Possible IAM propagation or effective-policy caching was not resolved in
this run. No token, key, certificate body, or credential value was stored.
