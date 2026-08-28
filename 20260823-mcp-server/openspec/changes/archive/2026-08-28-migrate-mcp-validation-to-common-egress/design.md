## Context

See [proposal.md](proposal.md) for motivation. The consumer already accepts an `agent_gateway_id`, but its docs and Registry data sources still contain references to the retired `agw-20260822-egress` experiment. The successful 2026-08-24 Cloud Run run proved an Agent Runtime-to-Gateway-to-MCP path using that old Gateway, not the new shared resource.

The 2026-08-28 read-only inventory established:

- `common/terraform` outputs `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`.
- The live Gateway is `AGENT_TO_ANYWHERE`, supports `MCP`, registers `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1`, and has a root CA for TLS inspection.
- Its egress Network Attachment is `common-agent-gateway-attachment`; the accepted managed producer endpoint is attached to `common-agent-gateway-vpc` through `common-agent-gateway-subnet`.
- The common Terraform state owns only the Gateway, VPC, subnet, Network Attachment, and API enablement. It does not own consumer Registry Services, IAM, Runtime, MCP server, or authz policy/extension.
- No separate live network-security authz policy or service-extension authz extension was returned for `us-central1`. This does not prove egress authorization succeeds; endpoint-scoped `roles/iap.egressor` behavior must be validated using the deployed Runtime.

The platform error previously observed was `Another Agent Gateway is already active or being created for this project and direction.` during Runtime association. The design therefore treats the practical constraint as active Gateway association per project/direction, not as proof that only one Gateway resource or authz extension can exist.

## Goals / Non-Goals

**Goals:**

- Make the shared Gateway an explicit, preflight-validated, non-owned dependency.
- Remove all runtime dependencies on retired `20260822` Gateway and Registry endpoint resources.
- Rebuild the Runtime image with the selected Gateway's TLS inspection CA and deploy by immutable digest.
- Reproduce the previously successful governed Cloud Run MCP E2E and complete its negative cases with layered evidence.
- Prepare and, when prerequisites are ready, validate a private GKE path using the common VPC attachment.

**Non-Goals:**

- Managing, importing, updating, replacing, or deleting resources in `common/terraform`.
- Claiming that Registry discovery alone provides network reachability or endpoint authorization.
- Treating an operator-side Cloud Run request or in-cluster GKE smoke test as Agent Runtime E2E.
- Automatically destroying resources after validation.

## Decisions

### 1. Consume the owner output and verify it against the live API

The consumer keeps `agent_gateway_id` as a required fully qualified input. A preflight compares the owner Terraform output with a live Gateway description and validates the exact project, location, name, direction, protocol, Registry, and Network Attachment before plan/apply.

This is preferred over hard-coding only `common-egress`, because a matching short name does not prove location, ownership, or runtime-compatible configuration. Duplicating the Gateway resource in the consumer state was rejected because it would create competing ownership and destructive cleanup risk.

### 2. Keep common infrastructure and consumer governance resources in separate states

`common/terraform` remains the sole owner of Gateway/VPC resources. This repository owns its Runtime, Registry Services/endpoints, endpoint-scoped egress IAM, Cloud Run/GKE front doors, and workload IAM. Static tests and plan inspection will reject any common resource block or action.

The current data sources for `20260822 managed ...` control-plane endpoints will be replaced with consumer-owned, collision-resistant Registry Services/interfaces for Agent Registry, regional/global Vertex AI, and IAM Credentials. The MCP Server entries remain consumer-owned. Reusing deleted legacy entries was rejected because rebuild success would depend on another experiment's lifecycle.

### 3. Bind egress to the Runtime effective identity after Runtime creation

The Runtime is deployed with `identity_type=AGENT_IDENTITY` and the reviewed Gateway ID. Its returned effective identity is then bound with `roles/iap.egressor` at each required Registry endpoint or MCP Server resource, never at project scope. Endpoint IAM remains a separate layer: Cloud Run Invoker or the GKE front-door authorization mechanism is not replaced by Gateway egress permission.

Because common currently has no separately inventoried authz policy/extension, the implementation will not recreate the old extension speculatively. Positive and negative Runtime requests, Gateway/IAP audit data, and absence/presence of application logs determine whether the managed egress control works. If Google requires an additional shared-Gateway policy resource, work stops at that evidenced blocker so ownership can be decided before changing `common`.

### 4. Build trust from the selected Gateway, without persisting certificate material

The build script receives the fully qualified Gateway identity or exact project/location/name derived from preflight, requires non-empty root certificates, and fails closed if retrieval or installation fails. The image is tested for trust-store inclusion and pushed by immutable digest. Command logs retain only Gateway identity, certificate fingerprint/count, image digest, and test outcome; PEM bodies are excluded.

Allowing the build to continue without a Gateway CA was rejected because it can produce a successfully deployed Runtime that fails only when TLS interception occurs. Reusing the old CA was rejected because Gateway replacement can rotate the root.

### 5. Migrate in phases with scope guards

The first cloud plan uses the current feature settings and reviewed immutable images, with explicit checks for no common-resource action and no unintended GKE deletion. Consumer-owned Registry/control-plane resources and Runtime are then created or reconciled. Runtime association and effective identity are read back from the live API before IAM binding or E2E is considered valid.

Cloud Run is the required regression gate because it has a prior successful baseline. GKE remains a subsequent gated phase: only an internal HTTPS Load Balancer/private DNS/trusted TLS route reachable through the common Network Attachment may qualify. A `ClusterIP` remains the backend and is not itself a Gateway-reachable frontend. An external public fallback is rejected.

### 6. Require one correlation chain per E2E result

For every positive run, evidence links the Runtime invocation, fixed Registry Service ID, resolved host, Runtime effective identity, `common-egress`, Gateway decision, endpoint authorization, Claude Tool event, and MCP server log with one correlation ID. Negative runs distinguish Gateway denial from Cloud Run/GKE denial and verify no server-side Tool execution occurred.

This is preferred over a single HTTP success or model answer because those signals cannot establish which route, identity, or authorization boundary executed the Tool.

## Risks / Trade-offs

- [Shared Gateway changes outside this state] → Compare owner output, live etag/config, and Network Attachment before apply; stop on drift and never auto-reconcile common resources.
- [Runtime association remains exclusive] → Inventory active Runtime/Gateway relationships before replacement, perform a targeted migration, and preserve rollback inputs for the previous Runtime revision where technically possible.
- [Missing old control-plane Registry entries break planning] → Replace legacy data sources with consumer-owned resources before Runtime apply and test plan from an environment where old entries are absent.
- [CA value is leaked through build output] → Suppress PEM output, record only fingerprint/count, redact command traces, and run a secret/certificate-body scan over repository evidence.
- [Egress permission semantics differ without the old authz extension] → Run bounded allow/deny probes and inspect managed logs; do not infer success from Terraform apply. Escalate any required shared policy change rather than silently taking ownership.
- [VPC attachment does not imply GKE reachability] → Validate private DNS, ILB frontend, firewall/backend health, TLS, and endpoint authorization independently; mark GKE SKIP/FAIL until the complete Runtime route is proven.
- [A full Terraform plan proposes unrelated GKE deletion] → Use phase-specific inputs/targets only as a temporary safety mechanism, review saved plans, and reject any unexpected change/destroy action.

## Migration Plan

1. Inventory `common/terraform` outputs, live Gateway/Network Attachment, active Runtime associations, Registry Services/endpoints, endpoint IAM, and current Terraform state; save sanitized Japanese preflight evidence.
2. Update input validation, preflight tooling, tests, runbook, and examples to require the exact common output and reject retired Gateway names or configuration drift.
3. Replace legacy `20260822` control-plane Registry data sources with consumer-owned resources and bounded Runtime-effective-identity egress bindings.
4. Fetch the selected Gateway CA, build/test/push an immutable Agent Runtime image, and record only the CA fingerprint/count and image digest.
5. Generate and review a scoped Terraform plan. Apply consumer-owned changes only after proving common resources and unrelated environments are no-op.
6. Read back Runtime Gateway association/effective identity and reconcile endpoint-scoped egress plus endpoint invocation IAM.
7. Run local regression, Cloud Run positive E2E, then negative tests. Update Japanese evidence, README, runbook, and validation matrix with actual PASS/FAIL/SKIP.
8. If private GKE prerequisites are approved and ready, construct/validate the internal route as a separate plan and run its E2E. Otherwise record an evidenced SKIP without weakening exposure or authentication.
9. Run a final drift plan and retain resources for operator review. Do not run destroy.

Rollback uses a reviewed consumer-only plan to restore the last known consumer Runtime/image/Registry/IAM configuration. It does not restore the retired old Gateway or mutate `common-egress`; if shared Gateway behavior is the cause, stop consumer rollout and coordinate with the common owner.
