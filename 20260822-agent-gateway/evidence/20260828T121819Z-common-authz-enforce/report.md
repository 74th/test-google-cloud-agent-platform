# common Gateway IAP enforcement recheck (2026-08-28)

This non-secret evidence record was produced by the `20260822-agent-gateway`
consumer validation checkout. It did not create, update, import, or delete a
common-owned resource.

## Common-side change read-back

The common-owned Authz Extension was updated in place from `DRY_RUN` with
`failOpen=true` to `ENFORCE` with `failOpen=false`. The Gateway ID, etag,
protocol (`MCP`), Registry scope, and Network Attachment were unchanged.

## Bounded validation result

| Field | Value |
| --- | --- |
| Caller | `74th.pc@gmail.com` |
| Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552` |
| Effective identity | `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552` |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Validation ID | `20260828T121819Z-common-authz-enforce` |

Both the GitHub positive request and the Cabinet Office negative request
returned Runtime HTTP 400. Delayed Gateway logs show the first denied layer:
the Runtime's `aiplatform.googleapis.com` Model Garden requests received HTTP
403 with `authzPolicyInfo.result=DENIED` from
`common-egress-iap-policy`.

This proves ENFORCE is fail-closed, but GitHub cannot yet be used as a positive
regression case. The denied request identifies the existing Registry endpoint
`agentregistry-00000000-0000-0000-3f4a-774e0ee85e2a`, owned by the
`20260823-mcp-server` consumer. Its `roles/iap.egressor` binding currently
contains only Runtime `2332905838663958528`, not this validation Runtime.

## Blocker and required owner action

Agent Registry rejects a second service with the identical
`https://aiplatform.googleapis.com` interface URL, so this consumer cannot
create an independent endpoint for the observed host. Restoring the GitHub
positive path requires the owner of the existing endpoint to add exactly this
validation Runtime's effective identity to that endpoint's
`roles/iap.egressor` policy through the `20260823-mcp-server` consumer state.

No cross-consumer IAM change was made here. Once that owner-approved binding
exists, rerun GitHub and Cabinet Office tests: GitHub must be allowed and
Cabinet Office must remain denied. Agent Runtime MCP E2E is still unproven.
