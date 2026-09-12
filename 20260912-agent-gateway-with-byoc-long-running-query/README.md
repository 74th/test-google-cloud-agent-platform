# 20260912: Agent Gateway + BYOC long-running query minimal repro

This is a self-contained, minimal reproduction for a report to Google:
**Vertex AI Agent Engine's `run_query_job` (BYOC long-running query) fails
when the Runtime is associated with an Agent Gateway (`AGENT_TO_ANYWHERE`),
while ordinary synchronous `query` calls on the same Gateway-associated
Runtime succeed.**

It builds its own project-scoped Agent Gateway, VPC, Agent Registry, and two
BYOC Runtimes -- it does not depend on any other directory in this
repository or on the shared `common/` Gateway.

## Background

`20260802-BYOC/support/google-query-job-agent-gateway-inquiry-20260829.md`
documents the same failure observed against the shared `common-egress`
Gateway in project `nnyn-dev`: the query-job's internal `proxy-container`
fails to download the GCS input object over `storage.mtls.googleapis.com`
with `SSLCertVerificationError: CERTIFICATE_VERIFY_FAILED: self-signed
certificate in certificate chain`, and the application container never
receives the request. This directory reproduces the same failure from a
clean project so it can be handed to Google as a minimal, independently
buildable repro.

## Layout

- `terraform/` -- VPC, subnet, PSC network attachment, this repro's own
  Agent Gateway (`AGENT_TO_ANYWHERE`), an Agent Registry Service that
  allow-lists only `https://github.com`, Artifact Registry, a GCS bucket for
  query-job I/O, and two Agent Engine Runtimes (with and without the Gateway
  association).
- `byoc_runtime/` -- the BYOC container. It answers the synchronous
  `query`/`stream_query` Agent Platform contract with a plain WebFetch
  handler (`byoc_runtime/adapter.py`): no LLM is involved -- it pulls every
  `http(s)://` URL out of the request message and fetches each one directly
  from this container, so the Runtime's own egress path (and therefore
  Agent Gateway) sees the real destination, and reports per-URL
  success/failure. It also answers the root `POST /` long-running
  query-job delivery contract (GCS input -> processing -> GCS output).
- `scripts/` -- build/push, and the three verification runs.
- `results/` -- raw evidence captured while running the verification
  (JSON Lines API traces, Cloud Logging summaries, terraform outputs).
- `support/google-query-job-agent-gateway-inquiry-20260912.md` -- the
  report ready to send to Google, built from this directory's evidence.

## Project

- Project: `dev-74th-20260912`
- Region: `us-central1`
- No cross-project dependency: this repro's Agent Gateway, VPC, and Agent
  Registry are all owned inside `dev-74th-20260912`.

## Test cases

| # | Runtime | Call | Expected | Purpose |
|---|---------|------|----------|---------|
| 1 | no Gateway | `run_query_job` (long-running) | succeeds | baseline: query jobs work with no Gateway |
| 2 | Gateway-associated | `query` (synchronous) | succeeds | Gateway egress itself works for ordinary calls |
| 3 | Gateway-associated | `run_query_job` (long-running) | **fails** | reproduces the reported defect |

A fourth run demonstrates the Gateway's default-deny behavior on the
Gateway-associated Runtime using an ordinary `query` call with both
`https://github.com/74th` (registered in Agent Registry, allowed) and
`https://www.tohoho-web.com/index.htm` (not registered in Agent Registry at
all, so denied by default) in the message. Because there is no model in the
loop, the report is a direct, unambiguous per-URL fetch result rather than a
generated summary: `[取得成功]`/`[取得失敗]` for each URL.

## Build and deploy

```bash
cd terraform
terraform init
# First apply: everything except the two Runtimes (image digest not known yet).
terraform apply \
  -target=google_project_service.required \
  -target=google_compute_network.agent_gateway \
  -target=google_compute_subnetwork.agent_gateway \
  -target=google_compute_network_attachment.agent_gateway \
  -target=google_network_services_agent_gateway.repro \
  -target=google_network_services_authz_extension.iap \
  -target=google_network_security_authz_policy.iap \
  -target=google_agent_registry_service.github \
  -target=data.google_agent_registry_endpoint.github \
  -target=google_artifact_registry_repository.agent_images \
  -target=google_storage_bucket.query_jobs

cd ..
IMAGE_URI="$(./scripts/build_push.sh)"   # prints an immutable name@sha256:... reference
cd terraform
terraform apply -var="runtime_image_uri=${IMAGE_URI}" \
  -target=google_vertex_ai_reasoning_engine.no_gateway \
  -target=google_vertex_ai_reasoning_engine.gateway

# The Reasoning Engine service agent (service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com)
# is only provisioned by Google after the first Runtime create call above,
# so the Artifact Registry reader binding in main.tf fails on a truly first
# apply. Grant it manually once, import it into state, then finish the plan
# (query-job bucket read/write for both Runtimes' own AGENT_IDENTITY
# principals -- the query-job GCS download runs as the Runtime's identity,
# not the aiplatform-re agent -- plus the github Registry Service IAM
# binding for the Gateway Runtime):
gcloud artifacts repositories add-iam-policy-binding byoc20260912-images \
  --project=dev-74th-20260912 --location=us-central1 \
  --member="serviceAccount:service-$(gcloud projects describe dev-74th-20260912 --format='value(projectNumber)')@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
terraform -chdir=terraform import google_artifact_registry_repository_iam_member.agent_runtime_reader \
  "projects/dev-74th-20260912/locations/us-central1/repositories/byoc20260912-images roles/artifactregistry.reader serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
terraform apply -var="runtime_image_uri=${IMAGE_URI}"
```

## Run the verification

```bash
export PROJECT=dev-74th-20260912 LOCATION=us-central1
NO_GATEWAY_RUNTIME="$(terraform -chdir=terraform output -raw no_gateway_runtime_name)"
GATEWAY_RUNTIME="$(terraform -chdir=terraform output -raw gateway_runtime_name)"
BUCKET="$(terraform -chdir=terraform output -raw query_job_bucket)"

# Test case 1: no Gateway, long-running query job -- expect success.
python3 -m scripts.query_job \
  --project="$PROJECT" --location="$LOCATION" \
  --agent-resource="$NO_GATEWAY_RUNTIME" \
  --output-gcs-uri="gs://${BUCKET}/query-jobs/no-gateway-$(date -u +%Y%m%dT%H%M%SZ).json" \
  --delay-seconds=10 \
  --result=results/query-job-no-gateway.jsonl

# Test case 2: Gateway, synchronous query -- expect success.
python3 -m scripts.invoke_agent \
  --location="$LOCATION" --agent-resource="$GATEWAY_RUNTIME" \
  "https://github.com/74th を取得して" | tee results/sync-query-gateway.txt

# Default-deny demonstration on the same Gateway Runtime.
python3 -m scripts.invoke_agent \
  --location="$LOCATION" --agent-resource="$GATEWAY_RUNTIME" \
  --default-deny-check | tee results/default-deny-check.txt

# Test case 3: Gateway, long-running query job -- expect failure.
python3 -m scripts.query_job \
  --project="$PROJECT" --location="$LOCATION" \
  --agent-resource="$GATEWAY_RUNTIME" \
  --output-gcs-uri="gs://${BUCKET}/query-jobs/gateway-$(date -u +%Y%m%dT%H%M%SZ).json" \
  --delay-seconds=10 \
  --result=results/query-job-gateway.jsonl
```

`scripts/query_job.py` polls the job, then collects a bounded Cloud Logging
window for the Runtime and writes an `evaluation` record classifying whether
the GCS input was fetched, whether the application container's `POST /` was
received, whether processing completed, the job's terminal state, and
whether the GCS output exists. See `results/*.jsonl` for the captured run.

## Results (2026-09-12, project `dev-74th-20260912`)

| # | Runtime | Call | Result | Evidence |
|---|---------|------|--------|----------|
| 1 | no Gateway (`reasoningEngines/8002172509430480896`) | `run_query_job`, `delay_seconds=10` | **succeeded** -- GCS input downloaded, `POST /` received by `job-container`, processed, GCS output written | `results/query-job-no-gateway-2.jsonl`, `results/evaluation-case1-no-gateway.json` |
| 2 | Gateway (`reasoningEngines/246973951098486784`) | `query` (sync, WebFetch `https://github.com/74th`) | **succeeded** -- HTTP 200, page fetched through the Gateway | `results/sync-query-gateway.txt` |
| 3 | Gateway (`reasoningEngines/246973951098486784`) | `run_query_job`, `delay_seconds=10` | **failed as reported** -- GCS input never delivered; `job-container` never received `POST /`; no GCS output | `results/query-job-gateway.jsonl`, `results/evaluation-case3-gateway.json`, `results/case3-proxy-container-traceback.json` |

### Default-deny demonstration

Same Gateway Runtime, one `query` call with both URLs in the message:

```
[取得成功] https://github.com/74th (HTTP 200, 120000 バイト)
[取得失敗] https://www.tohoho-web.com/index.htm -- HTTPError: HTTP 403
```

Corroborated at the Gateway itself (`results/gateway-default-deny-logs.json`):

| Field | `github.com` | `www.tohoho-web.com` |
|---|---|---|
| `authzPolicyInfo.result` | `ALLOWED` | `DENIED` |
| `agentGatewayInfo.agentRegistryResource` | matched our registered endpoint | absent (never registered) |
| `enforcedGatewaySecurityPolicy.requestWasTlsIntercepted` | `true` | `true` |

Both requests were TLS-intercepted by the Gateway; only the one matching a
registered Agent Registry Service was authorized. This confirms the Gateway
enforcement works correctly for ordinary application traffic -- the test
case 3 failure is specific to the platform's own query-job delivery path,
not a general problem with this Gateway configuration.

### Test case 3 failure detail

The Gateway-associated Runtime's `proxy-container` (the platform's own
query-job delivery component, not application code) fails downloading the
GCS input over a plain HTTPS connection to `storage.googleapis.com`:

```
requests.exceptions.SSLError: HTTPSConnectionPool(host='storage.googleapis.com', port=443):
Max retries exceeded with url: /download/storage/v1/b/.../o/...?alt=media
(Caused by SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1082)')))
```

after a 120s internal retry budget (`google.api_core.exceptions.RetryError:
Timeout of 120.0s exceeded`). `job-container` (the application) never logs a
`POST /` for this attempt at all -- confirmed by Cloud Logging query in
`scripts/query_job.py`'s `collect_log_evidence`.

This is the same class of failure as
`20260802-BYOC/support/google-query-job-agent-gateway-inquiry-20260829.md`
(query-job GCS delivery breaks specifically when the Runtime has an
`AGENT_TO_ANYWHERE` Agent Gateway association) reproduced independently in a
brand-new, single-purpose project. The exact low-level TLS error differs
(`SSLEOFError` here vs. `CERTIFICATE_VERIFY_FAILED: self-signed certificate`
in the original report, and a plain `storage.googleapis.com` host here vs.
`storage.mtls.googleapis.com` there) -- itself useful signal that the
underlying interception is non-deterministic in how it fails, not a single
fixed error string.

Test case 1 against the identically-built, identically-configured Runtime
minus the Gateway association succeeded cleanly, isolating the Gateway
association as the variable that causes the failure.

## Notes for whoever files the Google Support case

- Nothing in `byoc_runtime` calls a model. `query`/`stream_query` are a
  plain WebFetch handler (`byoc_runtime/adapter.py`), and the long-running
  path never calls it either. The test case 3 failure happens in the
  platform's own query-job delivery path (GCS input download through the
  Gateway-associated Runtime's egress), before any request reaches the
  application container. This isolates the defect from anything
  agent/model-specific, and avoids any dependency on Vertex Model Garden
  quota for a partner model.
- The Gateway allow-lists only `https://github.com` in Agent Registry. Any
  Gateway log entries for `storage.mtls.googleapis.com` (or another Google
  API host) during the query-job run are the platform's own traffic, not
  application traffic, and are not expected to be allow-listed by this
  repro's Registry.
- Everything in `terraform/` is destroyable independently of `nnyn-dev` and
  the `common/` shared Gateway; nothing here mutates shared state.
