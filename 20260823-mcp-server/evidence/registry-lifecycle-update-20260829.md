# Registry interface update diagnostic: 2026-08-29

The consumer-owned Cloud Run Registry Service was updated in place from the
reviewed `/mcp` interface to the same reviewed host with the temporary query
component `/mcp?lifecycle=20260829`. The Runtime image, Runtime environment,
Service ID, Tool schema, IAM, and shared Gateway were not changed.

| Layer | Result |
| --- | --- |
| Registry update | PASS: `mcp-20260823-cloud-run` describe returned the updated interface |
| Runtime re-resolution | PASS: Gateway request URL was `https://mcp-20260823-mcp-server-run-4txy36isyq-uc.a.run.app/mcp?lifecycle=20260829` |
| Gateway policy | ALLOWED; TLS inspection remained enabled |
| Endpoint delivery | FAIL: Gateway returned HTTP 403 before a Cloud Run request log was observed |
| MCP / Tool execution | Not reached; no Cloud Run application execution log |
| Restore | PASS: consumer Terraform restored the exact `/mcp` interface and recreated the projected egress binding; after propagation, Runtime query `2026-08-29T08:35:11Z`–`08:35:19Z` returned HTTP 200 and Cloud Run executed correlation `mcp-030f16bb4f3642d79e57bb84` |

This proves that the next Runtime invocation reads the changed Registry
interface rather than a URL embedded in the image, but the temporary URL form
was not accepted for execution. It is not a lifecycle success or E2E PASS.
No credential value, token, key, or certificate body was stored.

The final restore probe is independently correlated: the Registry URL was
`/mcp`, Gateway recorded `initialize`, `tools/list`, and `tools/call` as
`ALLOWED`, and the Cloud Run application recorded the same correlation ID.
