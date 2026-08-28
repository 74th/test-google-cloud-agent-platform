# Shared Gateway consumer validation report (2026-08-28)

## Scope

This run used the common-owned Gateway
`projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`.
No common Gateway, VPC, subnet, Network Attachment, Authz Extension, or
AuthzPolicy resource was created, changed, imported, or destroyed by this
consumer checkout. No destroy was run.

## Handoff and plan

- Common output/live read-back: [20260828-common-gateway-handoff.json](20260828-common-gateway-handoff.json)
- Provider/API contract: [20260828-provider-runtime-schema.md](20260828-provider-runtime-schema.md)
- Consumer plan: [20260828-consumer-plan.md](20260828-consumer-plan.md)
- Local checks: [20260828-local-validation.md](20260828-local-validation.md)

The reviewed consumer plan applied with 12 added, 0 changed, and 0 destroyed.
The follow-up endpoint-scoped IAM plan applied with 1 added, 0 changed, and
0 destroyed. The resulting resources are consumer-side Artifact Registry,
runtime identity/IAM, API state, GitHub Registry service, and its
Runtime-effective-identity binding. The reconciled Terraform plan now also
manages the consumer Runtime and reports 0 added, 0 changed, and 0 destroyed
after importing the already-deployed Runtime.

The Runtime was initially created atomically through the v1 REST create
payload. The stable provider still lacks the Gateway field, but the pinned
`google-nightly` provider exposes it, so the Runtime is now consumer-owned in
Terraform with the same atomic Gateway association:

- Runtime: `projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552`
- effective identity:
  `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552`
- Gateway read-back:
  `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
- image digest:
  `sha256:88b7f45bed4c6656c784b96c404a658978211ead1b4bf7ffecdff73ee91fbc9a`
- model: Claude Haiku 4.5, `claude-haiku-4-5@20251001`

The Runtime resource was imported into the consumer state by its full resource
name. Its reconciled plan has no Runtime replacement/update and no common-owned
resource action.

## Live evidence

Run directory: [20260828T091500Z-recheck](20260828T091500Z-recheck)

Caller was `74th.pc@gmail.com`. The runner saved exact prompts, Runtime
responses, Runtime application logs, Gateway logs, IAP logs, timestamps, and
correlation fields in one non-secret directory.

| Case | Result | Evidence |
| --- | --- | --- |
| GitHub `https://github.com/74th` | PASS | Japanese page-derived summary, application fetch status 200, Gateway `github.com` / `ALLOWED`, IAP allow evidence, caller/effective identity/Gateway correlation |
| Cabinet Office `www8.cao.go.jp` | FAIL | Application fetch status 200 and holiday list returned; Gateway/IAP path was `ALLOWED`/DRY_RUN, not default-deny |

The failed Cabinet Office result is retained as a fail-closed outcome. The
common Authz Extension read-back is `failOpen=true` with
`iamEnforcementMode=DRY_RUN`; the test therefore cannot claim the required
negative enforcement result until the common owner supplies an approved
enforced policy change. The unlisted host is not converted into a
host-specific deny rule in this consumer.

Agent Runtime MCP E2E remains `unproven`: Registry discovery, tool selection,
Gateway decision, endpoint authorization, and server-side MCP evidence are
not all present for this web-fetch run.

## Cleanup

No consumer or common resource was destroyed. Any later cleanup requires a
separate human review of a consumer-owned plan and must not target the common
Gateway.
