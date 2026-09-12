# Support inquiry: Agent Engine query job fails with an Agent Gateway association (minimal, standalone repro)

**Date:** 2026-09-12 UTC
**Product area:** Vertex AI Agent Engine (custom container / BYOC), Agent Gateway, Agent Registry
**Severity:** Development / validation blocker; no production impact
**Relation to prior report:** This independently reproduces
`20260802-BYOC/support/google-query-job-agent-gateway-inquiry-20260829.md`
(filed 2026-08-29 against project `nnyn-dev`'s shared `common-egress`
Gateway) from a brand-new, single-purpose project with no shared state, to
rule out anything specific to that project's configuration history.

## Request

We need to run a long-running Agent Engine query job (`run_query_job`) on a
BYOC Runtime that is associated with an Agent-to-Anywhere Agent Gateway. The
query job's Cloud Storage input never reaches our application container.
Please confirm whether this configuration is supported and, if so, the
supported way to let query-job GCS traffic through an Agent
Gateway-associated Runtime.

## Environment

| Item | Value |
| --- | --- |
| Project | `dev-74th-20260912` (project number `854555400134`) -- created solely for this repro |
| Region | `us-central1` |
| Runtime (Gateway-associated) | `projects/854555400134/locations/us-central1/reasoningEngines/246973951098486784` |
| Runtime (no Gateway, baseline) | `projects/854555400134/locations/us-central1/reasoningEngines/8002172509430480896` |
| Both Runtimes | identical container image digest, identical `class_methods`, `identity_type=AGENT_IDENTITY` |
| Gateway | `projects/dev-74th-20260912/locations/us-central1/agentGateways/byoc20260912-egress` |
| Gateway mode | Google-managed `AGENT_TO_ANYWHERE` |
| Gateway network attachment | `byoc20260912-agent-gateway-attachment` (dedicated `/28`, dedicated VPC) |
| Agent Registry | `//agentregistry.googleapis.com/projects/dev-74th-20260912/locations/us-central1`, one Service allow-listing only `https://github.com` |
| GCS bucket | `dev-74th-20260912-byoc-queryjobs` (query-job input/output only) |
| Terraform / provider | Terraform `1.13.1`, `hashicorp/google` `7.46.1`, `hashicorp/google-nightly` `2026.4.8-7.27.0` |

The entire environment (VPC, Gateway, Registry, Runtimes) is owned by this
one project and was built from scratch on 2026-09-12; it has no history and
no dependency on any other project or prior experiment.

## What works

The Gateway-associated Runtime's synchronous contract is not exercised in
this report (see [Known gap](#known-gap-not-part-of-this-report)), but the
**identically-configured, non-Gateway Runtime's `run_query_job`** was
verified end to end on 2026-09-12 as the control:

1. GCS input object written and downloaded (`gcs_input`: success).
2. Application container (`job-container`) received `POST /`
   (`http_delivery`: success, two deliveries observed including a platform
   retry).
3. Processing completed (`query_completed` matched to the request's
   verification marker).
4. GCS output object written (`gcs_output`: success,
   `content_type=application/x-ndjson`, `size=15`).

Evidence: `results/query-job-no-gateway-2.jsonl`,
`results/evaluation-case1-no-gateway.json`.

## Observed failure

Same container image, same `class_methods`, same GCS bucket, only
difference: the Runtime's `deployment_spec.agent_gateway_config` points at
this project's own Agent Gateway.

| Item | Value |
| --- | --- |
| Job | `projects/854555400134/locations/us-central1/operations/6033194252077367296` |
| Input object | `gs://dev-74th-20260912-byoc-queryjobs/query-jobs/gateway-20260912T051707Z_input.json` |
| Expected output object | `gs://dev-74th-20260912-byoc-queryjobs/query-jobs/gateway-20260912T051707Z.json` |

Observed results:

1. The input object was written by the SDK and is independently readable by
   our own credentials (`gcs_input` preflight succeeds).
2. In the query-job execution window, `proxy-container` (a platform-internal
   component; we do not assume it is customer-configurable) logs a Python
   traceback failing to download that same input object over a plain HTTPS
   connection to `storage.googleapis.com`:

   ```
   requests.exceptions.SSLError: HTTPSConnectionPool(host='storage.googleapis.com', port=443):
   Max retries exceeded with url: /download/storage/v1/b/dev-74th-20260912-byoc-queryjobs/o/query-jobs%2Fgateway-20260912T051707Z_input.json?alt=media
   (Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
   ```

   preceded by `google.api_core.exceptions.RetryError: Timeout of 120.0s
   exceeded`.
3. `job-container` (our application) never logs a `POST /` for this attempt
   at all -- confirmed by a Cloud Logging query bounded to the attempt's
   time window and this Runtime's resource ID (see
   `scripts/query_job.py::collect_log_evidence`).
4. No GCS output object was ever written.
5. The job operation remained `RUNNING` through our observation window
   (7 minutes); we did not force-cancel it.

Full raw log entries (including the complete traceback) are attached as
`results/case3-proxy-container-traceback.json`; the structured evaluation is
`results/evaluation-case3-gateway.json`.

### Relationship to the 2026-08-29 report

This is the same class of failure as the earlier report against `nnyn-dev`,
reproduced independently:

| | 2026-08-29 report (`nnyn-dev`) | This report (`dev-74th-20260912`) |
| --- | --- | --- |
| Failing host | `storage.mtls.googleapis.com:443` | `storage.googleapis.com:443` |
| Low-level error | `SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain` | `SSLEOFError: UNEXPECTED_EOF_WHILE_READING` |
| Failing component | `proxy-container` | `proxy-container` |
| Application container reached | No | No |
| Baseline (no Gateway) | Succeeded | Succeeded |

The differing low-level TLS symptom (certificate verification failure vs. an
unexpected connection close) across two independent projects suggests the
interception/inspection this Gateway association introduces on the
query-job's own GCS delivery path fails in more than one way, rather than
hitting one fixed, deterministic error.

## Questions for Google

1. Is Agent Engine BYOC `run_query_job` supported at all when the Runtime
   has an `AGENT_TO_ANYWHERE` Agent Gateway association?
2. Does the query-job Cloud Storage input/output path execute through the
   Agent Gateway, including the component that appears in our logs as
   `proxy-container`?
3. If Gateway TLS inspection applies to this Google-managed, platform-internal
   path, what is the supported way for that platform component to trust or
   bypass the Gateway's certificate handling for its own GCS calls?
4. If this combination is not currently supported, what is the recommended
   architecture for a workload that needs both long-running query jobs and
   governed egress on the same Runtime?

## Evidence available on request (this project)

All evidence is sanitized and excludes tokens, request bodies, and
certificate private keys.

- `results/query-job-no-gateway-2.jsonl` -- baseline success trace (no Gateway).
- `results/evaluation-case1-no-gateway.json` -- baseline structured evaluation.
- `results/query-job-gateway.jsonl` -- failing attempt trace (Gateway-associated).
- `results/evaluation-case3-gateway.json` -- failing attempt structured evaluation.
- `results/case3-proxy-container-traceback.json` -- full raw Cloud Logging
  entries for `proxy-container`/`job-container` during the failing attempt,
  including the complete Python traceback.
- `terraform/` -- the complete, minimal Terraform configuration that
  reproduces this environment from an empty project (no external module
  dependencies).

## The same Gateway works correctly for ordinary application traffic

To confirm this Gateway is otherwise functioning correctly (i.e. the
failure above is specific to the query-job path, not a broken Gateway
configuration), the same Gateway-associated Runtime answered an ordinary
synchronous `query` call that fetches a URL directly from the application
container (no model involved -- see `byoc_runtime/adapter.py`):

- `https://github.com/74th` (registered in Agent Registry) -- fetched
  successfully, HTTP 200.
- `https://www.tohoho-web.com/index.htm` (not registered) -- HTTP 403.

The Gateway's own access log confirms both requests were TLS-intercepted and
evaluated by IAP authorization, with opposite outcomes:

| Field | `github.com` | `www.tohoho-web.com` |
| --- | --- | --- |
| `authzPolicyInfo.result` | `ALLOWED` | `DENIED` |
| `agentGatewayInfo.agentRegistryResource` | matched our registered endpoint | absent |
| `enforcedGatewaySecurityPolicy.requestWasTlsIntercepted` | `true` | `true` |

Evidence: `results/sync-query-gateway.txt`,
`results/default-deny-check.txt`, `results/gateway-default-deny-logs.json`.

This isolates the defect to the query-job GCS delivery path specifically:
the same Gateway, same Runtime, same Agent Registry configuration correctly
allow/deny ordinary application egress, but cannot deliver the platform's
own query-job input.
