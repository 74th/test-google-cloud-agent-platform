# Additional verification: GCS destination authorization (2026-09-12)

Follow-up to `support/google-query-job-agent-gateway-inquiry-20260912.md`,
addressing item 1 ("最優先: GCS 宛先の認可と TLS を切り分ける") of a review
handoff. This tests the hypothesis that `run_query_job`'s GCS input download
fails because `storage.googleapis.com` / `storage.mtls.googleapis.com` were
never allow-listed in Agent Registry for the Gateway-associated Runtime.

**Result: the hypothesis is not supported.** Registering both hosts and
granting `roles/iap.egressor` made no observable difference to the failure,
and produced no Agent Gateway or IAP log evidence that the query-job's
traffic was ever evaluated by this Gateway's policy at all.

## What was done

1. Captured a fresh baseline `run_query_job` attempt against the
   Gateway-associated Runtime under the *unchanged* configuration
   (`results/query-job-before-authz.jsonl`), to compare against under the
   same conditions as the change below rather than relying only on the
   2026-09-12 run already in the main report.
2. Added two Agent Registry Services and their IAP `roles/iap.egressor`
   bindings for the Gateway-associated Runtime's identity:
   - `https://storage.googleapis.com` (`byoc20260912-storage-https`)
   - `https://storage.mtls.googleapis.com` (`byoc20260912-storage-mtls`)
   (`terraform/gcs-authz-diagnostic.tf`, applied and later reverted -- see
   below.)
3. Re-ran the identical `run_query_job` attempt
   (`results/query-job-after-authz.jsonl`).
4. Cross-referenced Cloud Logging for `proxy-container`/`job-container`
   (`resource.type="aiplatform.googleapis.com/ReasoningEngine"`) and for the
   Agent Gateway's own access log
   (`resource.type="networkservices.googleapis.com/Gateway"`,
   `resource.labels.gateway_name="byoc20260912-egress"`) across both runs.
5. Reverted the diagnostic Registry Services and IAM bindings (destroyed via
   Terraform) once the test showed no change, per the review handoff's
   instruction not to leave a no-effect diagnostic change in the permanent
   minimal-repro configuration.

## Findings

### 1. Identical failure before and after

Both before and after registering the GCS hosts, `proxy-container` fails
identically:

```
requests.exceptions.SSLError: HTTPSConnectionPool(host='storage.googleapis.com', port=443):
Max retries exceeded with url: /download/storage/v1/b/dev-74th-20260912-byoc-queryjobs/o/...
(Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
```

preceded by `google.api_core.exceptions.RetryError: Timeout of 120.0s
exceeded`, in both `results/query-job-before-authz.jsonl` (attempt
`query-job-e2637668-...`, retry observed at `2026-09-12T06:28:44Z`) and
`results/query-job-after-authz.jsonl` (attempt `query-job-b12268fd-...`,
retries observed at `2026-09-12T06:39:55Z` and `2026-09-12T06:43:05Z`).
`job-container` never received `POST /` in either run.

### 2. No Agent Gateway or IAP log evidence this traffic was ever evaluated

This is the more significant finding. A query bounded to the entire test
window (`2026-09-12T06:20:00Z`–`06:44:30Z`, and independently re-checked
with a 1-hour freshness window) against
`resource.type="networkservices.googleapis.com/Gateway"` returns **zero**
entries for this Gateway, for any hostname, during either query-job attempt.

For comparison, the same Gateway logged both outcomes of the ordinary
`query` WebFetch test from the main report within the same session:

| | `github.com` (WebFetch, `query`) | `storage.googleapis.com` (query-job) |
| --- | --- | --- |
| Gateway access log entries | present | **none** |
| `authzPolicyInfo.result` | `ALLOWED` | -- |
| `enforcedGatewaySecurityPolicy.requestWasTlsIntercepted` | `true` | -- |

The two IAP audit log entries found in this window are our own Terraform
`SetIamPolicy` calls creating the diagnostic bindings, not a runtime
authorization decision.

This means we cannot show that adding the Registry Service and IAP grant
had any effect on enforcement, because there is no evidence the
Gateway-managed policy plane ever saw this connection attempt in the first
place -- consistent with the SSL failure occurring at or before the TLS
handshake (`ssl.SSLEOFError` at `do_handshake()`), before whatever mechanism
produces Agent Gateway's access log entries would have a hostname/SNI to
evaluate and log.

### 3. Operation terminal state (new evidence, not in the main report)

Independent of the authorization test, a delayed `GET` on the *original*
2026-09-12 failing job's operation (referenced in the main report,
`results/query-job-gateway.jsonl`) now shows a definite terminal failure,
not just an unobserved `RUNNING` state at our monitoring deadline:

```json
{
  "name": "projects/854555400134/locations/us-central1/operations/6033194252077367296",
  "done": true,
  "error": {
    "code": 13,
    "message": "Task reasoning-engine-246973951098486784-job-msm2h-task0 failed with exit code: 1 and message: The container exited with an error."
  }
}
```

(`results/additional-verification-20260912/operation-gateway-6033194252077367296.json`)

This exactly matches the exit-code-13 failure symptom recorded in the prior
2026-08-29 report against `nnyn-dev`. The baseline (no-Gateway) job's
operation, by contrast, terminated successfully:

```json
{
  "name": "projects/854555400134/locations/us-central1/operations/5351346409763241984",
  "done": true,
  "response": {
    "outputGcsUri": "gs://dev-74th-20260912-byoc-queryjobs/query-jobs/no-gateway-20260912T051246Z.json"
  }
}
```

The two 2026-09-12 authorization-test operations
(`6194303491872129024` before, `3888460482658435072` after) had not yet
reached `done=true` as of this report; given the pattern above, a later
`GET` is expected to show the same `error.code=13` termination. Whoever
files or updates the Google Support case should re-fetch these before
closing out, using:

```
GET https://us-central1-aiplatform.googleapis.com/v1beta1/projects/854555400134/locations/us-central1/operations/<id>
```

## Judgment (per the review handoff's criteria)

- Input delivery did **not** start succeeding after the allow-list change,
  so destination authorization is not shown to be a/the cause.
- We cannot even confirm the traffic reached an authorization decision (no
  Gateway/IAP log evidence either way), so per the handoff's guidance this
  is recorded as "failed identically after adding the allow-list entries,"
  not as "authorization passed but TLS still failed."
- This points investigation toward the TLS/network layer (handoff items 2
  and 3: authenticated GCS fetch comparison from the application container,
  and Private Google Access / actual network path) rather than toward Agent
  Registry configuration. Those items were not run in this pass and remain
  open if further isolation is wanted.

## Evidence

All under `results/additional-verification-20260912/`:

- `query-job-before-authz.jsonl`, `query-job-before-authz.trace.jsonl`
- `query-job-after-authz.jsonl`, `query-job-after-authz.trace.jsonl`
- `operation-gateway-6033194252077367296.json`,
  `operation-no-gateway-5351346409763241984.json` -- newly-fetched terminal
  states for the main report's two operations
- `operation-before-authz-6194303491872129024.json`,
  `operation-status-3888460482658435072-20260912T064620Z.json`,
  `operation-status-6194303491872129024-20260912T064619Z.json` -- non-terminal
  as of check time
- `gateway-logs-during-authz-test-empty.json` -- the empty Gateway
  access-log query result for the full test window
- `proxy-storage-errors-after-authz.json` -- raw `proxy-container` error log
  entries mentioning `storage.googleapis.com` across both runs
- `readback/registry-services.json` -- Registry Services present at the
  time of the diagnostic change (including the two since-removed diagnostic
  entries)

## Configuration state after this pass

The diagnostic Registry Services and IAP bindings
(`byoc20260912-storage-https`, `byoc20260912-storage-mtls`, and their
`roles/iap.egressor` grants) were destroyed via Terraform. The environment
is back to the same configuration documented in the main `README.md` and
`support/google-query-job-agent-gateway-inquiry-20260912.md`: only
`https://github.com` is registered. No other diagnostic changes from the
handoff (items 2-5) were applied. No jobs are pending cleanup beyond the two
non-terminal operations noted above, which need no action (they are
observation-only, not resources).
