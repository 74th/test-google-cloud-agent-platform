# Cloud Run through common-egress: 2026-08-29 validation

This is the post-migration positive validation for the consumer Runtime. The
older `cloud-run-common-egress-validation-20260828.md` remains as historical
blocker evidence and is not overwritten.

## Reviewed resources

| Item | Observed value |
| --- | --- |
| Agent Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/8548154799411953664` |
| Runtime effective identity | `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/8548154799411953664` |
| Agent Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Registry Service | `mcp-20260823-cloud-run` |
| Registry MCP endpoint | `projects/776113568960/locations/us-central1/mcpServers/agentregistry-00000000-0000-0000-7e79-b986b2742326` |
| Resolved host | `mcp-20260823-mcp-server-run-4txy36isyq-uc.a.run.app` |
| Tool | `mcp__cloud-run__validate_echo` |
| Correlation ID | `mcp-2af5cd7c240946acbdbb4694` |

## Layered evidence

| Layer | Result | Evidence |
| --- | --- | --- |
| Runtime invocation | PASS | Vertex AI Runtime `:query` returned HTTP 200 and a validation result with the correlation ID. |
| Registry discovery and metadata | PASS | Runtime log resolved Service ID `mcp-20260823-cloud-run`, the MCP endpoint, and the expected Cloud Run host. |
| Claude Agent SDK Tool selection | PASS | Runtime log event `runtime_mcp_invocation` contains `ToolUseBlock` for `mcp__cloud-run__validate_echo`. |
| Agent Gateway egress | PASS | Gateway log at `2026-08-28T16:17:38.138450Z` recorded the resolved Cloud Run host, Registry MCP resource, method `tools/list`, and Authz result `ALLOWED`; TLS inspection was enabled. |
| Cloud Run endpoint authorization / request delivery | PASS | Cloud Run request log at `2026-08-28T16:17:40.329530Z` recorded `POST /mcp` with HTTP 200. |
| MCP Tool execution | PASS | Cloud Run application log at `2026-08-28T16:17:40.341195Z` recorded `mcp_tool_execution` with the same correlation ID and `hostingTarget=cloud-run`. |
| Direct Tool result | PASS | Runtime response returned `ok=true`, `hostingTarget=cloud-run`, and the same correlation ID. |

The Gateway log exposes the MCP discovery operation as `tools/list`; the
independent Claude Tool-selection, Cloud Run HTTP 200, and server-side
`mcp_tool_execution` records establish the subsequent Tool execution. No
credential value, token, key, or certificate body is included here.
