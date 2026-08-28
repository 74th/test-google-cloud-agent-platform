# common Gateway Authz negative recheck (2026-08-28)

This is a non-secret Gateway-validation record. It was run from the
`20260822-agent-gateway` consumer checkout and did not create, update, import,
or delete a common-owned resource.

## Invocation

| Field | Value |
| --- | --- |
| Verification ID | `20260828T121114Z-common-authz-recheck` |
| Caller | `74th.pc@gmail.com` |
| Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552` |
| Runtime effective identity | `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552` |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Authz policy | `common-egress-iap-policy`, IAP `DRY_RUN` |

The validation runner invoked both the GitHub positive case and the Cabinet
Office negative case. The runner's first log collection occurred before Cloud
Logging delivery, so `gateway_decision` is empty in `summary.json`.
`gateway-logs-delayed.json` contains the delayed read-back for the same UTC
window and is the decision evidence below.

## Result

| Case | Runtime/application result | Delayed Gateway decision | Verdict |
| --- | --- | --- | --- |
| `github.com` | page-derived Japanese summary returned | allow evidence was observed in the bounded run | PASS (positive path) |
| `www8.cao.go.jp` | page was fetched and the 2027 holiday list was returned | `2026-08-28T12:11:28.870709Z`: HTTP 200, `authzPolicyInfo.result=ALLOWED`, `default_denied` rule action `ALLOWED` | FAIL (negative path) |

The Cabinet Office host is not listed in this consumer's egress-policy source,
but it was not denied by the shared Gateway. The rule name `default_denied` is
therefore not evidence of a default-deny outcome; its observed action is
`ALLOWED` for this Runtime identity.

## Conclusion and boundary

The current common IAP Authz Extension is configured with
`iamEnforcementMode=DRY_RUN`. This recheck proves that it does not provide the
required default-deny behavior for this identity/destination combination.
No switch to `ENFORCE`, policy update, or Gateway mutation was made here.
Such a change belongs to the common owner and requires a separate reviewed
plan and approval. Agent Runtime MCP E2E remains unproven.
