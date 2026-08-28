# common-egress live validation (2026-08-29)

## Scope and ownership

This validation used the externally owned common Gateway
`projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`.
The consumer did not create, update, import, or destroy the Gateway, VPC,
subnet, Network Attachment, Authz Extension, or AuthzPolicy. No destroy was
run during the validation window; the consumer-only cleanup was performed
afterward under the separate saved plan documented below.

The current common Registry read-back includes the shared `github.com`,
`agentregistry.googleapis.com`, `aiplatform.googleapis.com`,
`us-central1-aiplatform.googleapis.com`, and `iamcredentials.googleapis.com`
interfaces. The BYOC-specific Storage endpoint remains consumer-owned.

## Verification window

- Verification ID: `20260829T150541Z-common-authz-live`
- Runtime: `projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552`
- Runtime effective identity:
  `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552`
- Authenticated caller: `74th.pc@gmail.com`
- Gateway: `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`

The runner invoked both prompts through the deployed Runtime, then collected
Runtime application logs and delayed Gateway/IAP logs for the same bounded
window. The raw and derived evidence is in
[`evidence/20260829T150541Z-common-authz-live`](20260829T150541Z-common-authz-live).

## Results

| Case | Result | Independent evidence |
| --- | --- | --- |
| GitHub `https://github.com/74th` | PASS | Japanese page-derived response; Runtime application fetch status 200; Gateway destination `github.com`, Authz `ALLOWED`, HTTP 200; caller, effective identity, Gateway ID and timestamps |
| Cabinet Office `https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html` | PASS | Runtime application fetch status 403 and no holiday-list fabrication; delayed IAP `AuthorizeUser` with `Permission Denied`; `granted=false`; hostname absent from the reviewable allow policy; caller, effective identity, Gateway ID and timestamps |

## TLS inspection

The Gateway read-back reports an mTLS endpoint and one root certificate; only
the SHA-256 fingerprint is retained in
[`tls-inspection.json`](20260829T150541Z-common-authz-live/tls-inspection.json).
For the GitHub request, the Gateway log records
`requestWasTlsIntercepted=true`, SNI `github.com`, Authz `ALLOWED`, and HTTP
200, while the Runtime application log records the HTTPS fetch success. This
is consistent with the image's `AGENT_GATEWAY_ROOT_CERTIFICATES` trust-bundle
contract; TLS verification was not disabled.

The live Authz Extension read-back is `iamEnforcementMode=ENFORCE`, and the
AuthzPolicy is `REQUEST_AUTHZ`/`CUSTOM` targeting only `common-egress`.

## MCP boundary

Agent Runtime MCP E2E remains `unproven`. This run proves the web-fetch
allow/deny and TLS path only; it does not provide every required Registry
service/interface resolution, selected-tool, endpoint-authorization, and
server-side MCP execution record.

## Post-validation consumer cleanup

After the live validation, the explicitly requested consumer-only destroy was
applied from the saved plan
[`20260829-consumer-destroy-plan.txt`](20260829-consumer-destroy-plan.txt).
Terraform reported `0 added, 0 changed, 12 destroyed`. This removed the
consumer Runtime, Artifact Registry repository and its repository IAM,
Runtime service account and IAM bindings. The six API service resources were
also removed from this Terraform state, but all six APIs remained enabled
because their configuration has `disable_on_destroy=false`.

Post-destroy checks found an empty consumer Terraform state, Runtime GET
HTTP 404, and the Artifact Registry repository NOT_FOUND. The common Gateway
still exists and reports `AGENT_TO_ANYWHERE`. The active account lacked
permission to independently describe the deleted service account; Terraform
apply and the empty state are the deletion evidence for that resource.
