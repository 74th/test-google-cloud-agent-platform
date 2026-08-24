# Access-control capability and inventory evidence

Date: 2026-08-23  
Project: `nnyn-dev`  
Operator account: redacted from repository evidence

This file contains sanitized read-only observations for OpenSpec tasks 1.1 and
1.2. Access tokens, private keys, gateway certificates, and full IAM policies
are intentionally excluded.

## Toolchain

| Surface | Observed version/status |
| --- | --- |
| Google Cloud SDK | 581.0.0; beta 2026.08.14 |
| Terraform | 1.13.1 |
| Node.js | v22.22.1 |
| kubectl | v1.35.3 client; GKE auth plugin 0.5.18 |
| Agent Registry API | enabled; gcloud `agent-registry` exposes `services`, `endpoints`, `bindings`, and `mcp-servers` |
| Network Services API | enabled; gcloud `network-services agent-gateways` exposes list/describe/export/import/delete |
| IAP API | enabled; gcloud `iap web` exposes IAM policy operations |
| Agent Runtime surface | no `gcloud agent-platform` group in this SDK; the installed provider/API surface is Terraform `google_vertex_ai_reasoning_engine` with `spec.identity_type = "AGENT_IDENTITY"` |
| Agent Gateway Terraform surface | adjacent capability inventory exposes `google_network_services_agent_gateway`, `google_network_services_authz_extension`, and `google_network_security_authz_policy` through `google-nightly` |

## Read-only project inventory

Enabled control-plane APIs relevant to this change include:

- `agentregistry.googleapis.com`
- `agentidentity.googleapis.com`
- `agentidentitycredentials.googleapis.com`
- `aiplatform.googleapis.com`
- `iap.googleapis.com`
- `networkservices.googleapis.com`
- `networksecurity.googleapis.com`
- `iam.googleapis.com`
- `iamcredentials.googleapis.com`
- `run.googleapis.com`
- `container.googleapis.com`
- `compute.googleapis.com`
- `dns.googleapis.com`
- `logging.googleapis.com`
- `artifactregistry.googleapis.com`

Existing resources observed before this change:

| Resource | Observation | Scope decision |
| --- | --- | --- |
| GKE `autopilot` in `asia-northeast1` | RUNNING, network `default` | Out of scope; do not modify or reuse |
| Agent Gateway `agw-20260822-egress` in `us-central1` | Existing `AGENT_TO_ANYWHERE`, MCP gateway | Out of scope; do not modify |
| Agent Gateway Registry endpoints with `20260822` names | Existing managed control-plane, runtime, logging, AI Platform, and GitHub endpoints | Out of scope; do not modify or bind from the new runtime |
| Agent Runtime from the prior experiment | Existing reasoning-engine resource observed in adjacent evidence | Out of scope; create a new runtime and state |
| Existing IAP audit records | `iap.googleapis.com` `AuthorizeUser` records exist | Out of scope; use only as capability evidence |
| Existing managed certificate | `temp20200801.74th.tech` | Out of scope; do not reuse without explicit hostname authorization |
| Existing service accounts and project IAM | Pre-existing accounts and broad bindings exist | Out of scope; new bindings must be target-specific and must not broaden them |

No existing Cloud Run service or dedicated GKE Standard cluster for this
experiment was observed in the configured `us-central1`/`us-central1-a` scope at
inventory time. The existing Autopilot cluster is not a substitute for the
dedicated isolated backend.

## Supported command/resource surfaces verified

The following read-only commands succeeded or returned their official help:

```text
gcloud agent-registry services {create,delete,describe,list,update}
gcloud agent-registry endpoints {list,describe}
gcloud agent-registry bindings {create,delete,describe,fetch-available,list,update}
gcloud agent-registry mcp-servers search
gcloud network-services agent-gateways {list,describe,export,import,delete}
gcloud network-security authz-policies {list,describe,export,import,delete}
gcloud iap web {add-iam-policy-binding,get-iam-policy,remove-iam-policy-binding,set-iam-policy}
```

The endpoint resource output includes a stable `endpointId`, interface URL, and
protocol binding. The existing adjacent implementation uses
`roles/iap.egressor` on `google_iap_agent_registry_endpoint_iam_member` with a
`principal://...reasoningEngines/...` member; this is recorded as a provider
surface to validate independently during implementation, not as proof that an
existing resource is reusable.

The installed provider schema was queried read-only after initialization. It
contains these relevant resources in `hashicorp/google` 7.45.0,
`hashicorp/google-beta` 7.45.0, and the pinned `hashicorp/google-nightly`
2026.4.8-7.27.0:

```text
google_vertex_ai_reasoning_engine
google_network_services_agent_gateway
google_network_services_authz_extension
google_network_security_authz_policy
google_agent_registry_service
google_agent_registry_binding
google_iap_agent_registry_endpoint_iam_member
```

The installed `claude-agent-sdk==0.1.9` type surface includes an HTTP MCP
configuration with `type`, `url`, and optional `headers`, and an SSE
configuration with the same header fields. The new implementation must create
this configuration from freshly resolved metadata and credentials for each
invocation; a user-provided URL is not a supported input.

IAP authorization evidence is available through Cloud Logging with
`protoPayload.serviceName="iap.googleapis.com"` and method
`AuthorizeUser`. Gateway evidence is collected separately from the
`network_services_agent_gateway` resource/log surface. These are distinct
evidence layers and are not treated as interchangeable.

## Live capability blocker discovered during apply

The isolated Cloud Run, Registry Service, and new Agent Gateway were created
successfully. A new `google_vertex_ai_reasoning_engine` with
`identity_type="AGENT_IDENTITY"` could not be created because the API returned:

```text
Another Agent Gateway is already active or being created for this project and direction.
```

The read-only gateway inventory shows both the pre-existing
`agw-20260822-egress` and the new `mcp-20260823-egress`, both
`AGENT_TO_ANYWHERE`/`MCP`. The existing gateway is explicitly out of scope and
will not be reused or modified. Agent Runtime E2E and Gateway allow/deny PASS
claims therefore remain blocked until Google project-level gateway exclusivity
is resolved in an isolated project or the prior experiment is no longer active.

The current project also rejected operator-side impersonation of the new caller
Service Account because the operator lacks `iam.serviceAccounts.getAccessToken`.
This is expected to keep operator test credentials separate from the workload
delegation; no key or broad operator binding was added. The runtime effective
identity was not created, so direct-vs-delegated token minting remains an
explicit pending verification rather than a PASS.

## Scope guard

Every pre-existing resource listed above is explicitly out of scope. The new
change must use the `20260823-mcp-server` prefix/labels and an independent
Terraform state. Any plan that changes or destroys an existing `20260822`,
Autopilot, default-VPC, or unrelated Registry resource fails the scope guard.
