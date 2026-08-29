# Support inquiry: Agent Engine query job fails with an Agent Gateway association

**Date:** 2026-08-29 UTC  
**Product area:** Vertex AI Agent Engine (custom container / BYOC), Agent Gateway, Agent Registry  
**Severity:** Development / validation blocker; no production impact

## Request

We need to run a long-running Agent Engine query job on a BYOC Runtime that is
associated with an Agent-to-Anywhere Agent Gateway. The query job does not
reach our application container. Please confirm whether this configuration is
supported and, if so, the supported configuration needed for the query job's
Cloud Storage input/output path.

In particular, please answer the questions in [Questions for Google](#questions-for-google).

## Environment

| Item | Value |
| --- | --- |
| Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/6890548661562900480` |
| Runtime location | `us-central1` |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Gateway mode | Google-managed `AGENT_TO_ANYWHERE` |
| Gateway network attachment | `common-agent-gateway-attachment` |
| Runtime identity mode | `AGENT_IDENTITY` |
| Runtime image | Immutable digest `sha256:1e5cf4c9837238147dee3c4bbfd4b71615a8a0e572be99c12bd62612cd2f93a4` |
| Agent Registry | `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1` |
| Test scope | Development project; no production workload |

The Gateway has one output root certificate and an mTLS endpoint in its live
Agent Gateway card. We have not disabled TLS verification.

## What works

After associating the Runtime with the Gateway, the following synchronous
Runtime operations complete successfully against the same Runtime and image:

- `query`
- `async_query`
- `stream_query`
- `async_stream_query`

These operations establish that the Runtime can be created with the Gateway
association and that our BYOC application is healthy. They do not require the
query-job Cloud Storage delivery path.

## Query-job setup

We invoke the Agent Platform SDK `run_query_job` with a short input. The SDK
returns an operation and an input GCS URI. The input and output use a
development bucket to which the required Runtime/caller permissions were
granted.

To authorize the GCS destinations through the Gateway, we created this
Agent Registry Service in the Registry referenced by the Gateway:

```text
projects/nnyn-dev/locations/us-central1/services/byoc-query-job-storage-20260828
```

It has exactly these interfaces:

```text
https://storage.googleapis.com
https://storage.mtls.googleapis.com
```

The projected Agent Registry Endpoint has an endpoint-scoped
`roles/iap.egressor` binding for only the Runtime effective identity. The
Service, Endpoint, and IAM binding were read back after apply. The Gateway,
VPC, subnet, and network attachment were not changed.

## Observed failure

The post-policy short query-job retry used:

| Item | Value |
| --- | --- |
| Operation | `projects/776113568960/locations/us-central1/operations/5133004909683146752` |
| Attempt ID | `query-job-7b30069d-6168-4514-9cef-d1d598a74843` |
| Input object | `gs://test-nnyn-20260802-byoc/query-jobs/common-egress-short-20260829_input.json` |
| Expected output object | `gs://test-nnyn-20260802-byoc/query-jobs/common-egress-short-20260829.json` |

Observed results:

1. The input object exists and caller-side GCS and Service Usage preflight
   checks succeed.
2. In the query-job execution logs, a container named `proxy-container` emits
   errors while attempting the GCS input download to
   `storage.mtls.googleapis.com:443`.
3. The error chain includes `SSLCertVerificationError` /
   `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`,
   followed by a retry timeout.
4. Our application container (`job-container`) has no corresponding `POST /`
   receive event, no processing event, and no output object is written.
5. The operation remained `RUNNING` during the finite observation window; an
   earlier equivalent attempt later completed with code 13, "The container
   exited with an error."

This document calls `proxy-container` an *observed query-job container name*.
We do **not** assume that it is a documented product component, a sidecar, or
that its exact implementation is customer-configurable.

## Related Gateway logs

In the same bounded query-job windows, Gateway request logs contain repeated:

```text
request method: CONNECT
hostname: 240.0.0.2:443
matched rule: default_denied
agentGatewayInfo: empty
```

An earlier window recorded HTTP 403 for these entries; a later window recorded
HTTP 200 while retaining `default_denied`. Therefore we do not interpret the
HTTP status alone as an allow decision, and we do not claim that
`240.0.0.2:443` is the public GCS destination. We need Google to explain the
mapping and enforcement semantics.

## Baseline without this Gateway association

On 2026-08-22, a Runtime deployed before the Gateway association work
completed the same query-job flow: GCS input, `POST /`, processing, `SUCCESS`,
and GCS output. That older deployment did not contain an Agent Gateway
configuration in its deployment script. This is evidence of a behavioral
difference, not proof of a particular internal cause.

## Questions for Google

1. Is Agent Engine BYOC `run_query_job` supported when the Runtime has an
   `AGENT_TO_ANYWHERE` Agent Gateway association?
2. Does the query-job Cloud Storage input/output path execute through the
   Agent Gateway, including the component that appears in our logs as
   `proxy-container`?
3. Is `storage.mtls.googleapis.com:443` an expected destination for that
   path? If yes, how should it be registered and authorized in Agent Registry
   and IAP endpoint IAM?
4. Does Agent Gateway TLS inspection apply to this managed query-job path? If
   yes, what is the supported way for the Google-managed component to trust
   the Gateway certificate chain?
5. Is there a supported destination-specific TLS-inspection bypass or an
   exemption for Google-managed Cloud Storage traffic? If so, please provide
   the API/Terraform/gcloud surface and the narrowest recommended policy.
6. What does `CONNECT 240.0.0.2:443` represent in Agent Gateway request logs
   for this path? How can it be correlated to the logical destination and
   Agent Registry Endpoint?
7. If this combination is not yet supported, what supported architecture is
   recommended for long-running query jobs while retaining governed egress for
   application-originated traffic?

## Evidence available on request

All evidence is sanitized and excludes tokens, request bodies, and certificate
private keys.

- `results/query-job-common-egress-short-20260829.jsonl` — short-job state,
  container/error presence, no application delivery, and GCS object metadata.
- `results/query-job-common-egress-short-20260828-followup.jsonl` — terminal
  operation failure and earlier Gateway decision summary.
- `results/registry-service-policy-20260828.md` — Agent Registry Service,
  Endpoint, and endpoint-scoped IAM read-back.
- `results/common-egress-validation-20260828.md` — comparison with the
  pre-Gateway baseline and bounded Gateway log observations.
- `results/query-job-long-running-960-20260822.jsonl` — successful pre-Gateway
  baseline for the 960-second query job.

We can provide sanitized Cloud Logging excerpts, exact timestamps, and the
Runtime/Gateway GET responses through an approved support channel.
