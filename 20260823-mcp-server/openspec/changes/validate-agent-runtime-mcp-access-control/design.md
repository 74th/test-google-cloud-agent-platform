## Context

See [proposal.md](proposal.md) for motivation. The archived validation established that the same stateless MCP image works on IAM-protected Cloud Run and on a GKE `ClusterIP`, and that manually registered Agent Registry entries can be searched. Cloud Run was invoked by a local operator; GKE was invoked by an in-cluster Node.js client. Neither path used Agent Runtime or Claude Agent SDK.

An adjacent completed experiment demonstrates a custom-container Agent Runtime using `identity_type=AGENT_IDENTITY`, a managed Agent Gateway with `AGENT_TO_ANYWHERE`, Agent Registry endpoints, an IAP authorization extension, and endpoint-scoped `roles/iap.egressor` bindings for the runtime effective identity. Google permits only one active Agent Gateway per project and direction, so this change reuses the existing `agw-20260822-egress` by reference, does not manage its resource or policy, and keeps its own Terraform state for all experiment-owned resources. Agent Registry remains a discovery and governed-egress control plane, not an MCP execution proxy.

The managed Agent Runtime has no proven route to a GKE `ClusterIP`. A GKE E2E test therefore needs an Agent Runtime-reachable HTTPS front door. It must not fall back to an unauthenticated public endpoint. A DNS name and trusted TLS certificate are prerequisites for that path.

## Goals / Non-Goals

**Goals:**

- Make Agent Registry Service IDs, rather than embedded URLs, the logical MCP connection configuration consumed by Agent Runtime.
- Enforce an outbound default-deny boundary with the approved existing Agent Gateway, Registry endpoints, and endpoint-scoped IAP egress authorization.
- Enforce inbound authorization independently at Cloud Run and the GKE HTTPS front door.
- Exercise the remote MCP Tools through Claude Agent SDK inside Agent Runtime and prove which backend executed each call.
- Capture positive and negative evidence at discovery, Gateway, endpoint authorization, MCP, and Claude Tool-selection layers.

**Non-Goals:**

- Treat Agent Registry or Agent Gateway as an MCP request proxy that replaces endpoint authentication.
- Reuse or modify the existing `20260822-agent-gateway` runtime, Registry entries, or Terraform state. The existing Gateway is an explicit external dependency and is referenced but not managed by this change.
- Provide production GKE HA, a general-purpose multi-tenant MCP authorization service, or arbitrary user-supplied MCP URLs.
- Store long-lived bearer tokens, Service Account keys, OAuth client secrets, or Anthropic API keys in source or evidence.
- Claim private Agent Runtime-to-GKE connectivity; the selected GKE path is authenticated public HTTPS.

## Decisions

### 1. Use three independent control layers

The integration is split into three observable layers:

1. Agent Registry stores the approved logical Services, interfaces, protocol binding, and Tool metadata.
2. Agent Gateway governs Agent Runtime egress. The runtime effective identity receives `roles/iap.egressor` only on the projected Registry endpoints required for Cloud Run and GKE; unregistered or unbound endpoints are default-denied.
3. Each hosting endpoint authenticates the request again before forwarding it to the MCP process.

The runtime resolves Registry entries by stable Service ID on every invocation or through a bounded cache that is invalidated before lifecycle tests. It validates project, location, Service ID, HTTPS scheme, allowed host, `JSONRPC` binding, and Tool schema before creating the Claude SDK remote MCP configuration. URLs are never accepted from prompts.

This separation makes it possible to prove that Registry read permission, Gateway egress permission, and endpoint invocation permission do not imply one another. A single application allowlist without Agent Gateway was rejected because it would not establish a platform-enforced egress boundary. Gateway-only host control was rejected because it would not supply Tool metadata or lifecycle management.

### 2. Deploy a dedicated Agent Runtime using Claude Agent SDK remote MCP support

The new custom container follows the established Agent Platform `query` and `stream_query` contract, uses `AGENT_IDENTITY`, and invokes Claude through Vertex AI. The implementation pins a current Claude Agent SDK version only after a local capability test confirms its remote Streamable HTTP MCP configuration and dynamic authorization-header behavior.

The agent exposes deterministic test prompts or request fields that select the Cloud Run or GKE validation objective without accepting a URL. Claude must still select and call the advertised Tool; the adapter records sanitized MCP lifecycle events and a generated correlation ID. A model response alone is not accepted as Tool-execution evidence.

A bespoke HTTP call from the adapter was considered but rejected as the primary E2E path because it would prove Agent Runtime networking without proving Claude Agent SDK Tool integration. It remains useful only as a diagnostic stage before the Claude test.

### 3. Use short-lived audience-bound credentials for endpoint authorization

The implementation first checks whether the Agent Runtime effective identity can mint the required audience-bound ID token directly. If the platform identity cannot be used directly by the token API, a dedicated MCP caller Service Account is introduced. The runtime effective identity may impersonate only that account for `generateIdToken`; the caller account receives only Cloud Run Invoker and the GKE front-door access role. No key is created.

Cloud Run receives an ID token whose audience is the exact Cloud Run service URL. GKE receives a token for its configured authentication audience. Tokens are generated per request or short-lived cache period and are never logged. Missing tokens, wrong audiences, and a separate unauthorized identity are tested explicitly.

Making either endpoint unauthenticated and relying only on Agent Gateway was rejected because any caller outside the governed runtime path could then invoke the MCP Server directly.

### 4. Expose GKE through an HTTPS load balancer with IAP while preserving ClusterIP

The MCP Deployment and `ClusterIP` Service remain the backend. A GKE-supported Gateway or Ingress creates an external HTTPS Application Load Balancer with a dedicated hostname, trusted certificate, and IAP-protected backend. Only the load balancer reaches the Kubernetes backend; the Pod and `ClusterIP` are not directly Internet-addressable. The Agent Runtime caller identity is granted access, while unauthenticated and unauthorized identities are denied before MCP execution.

The exact Gateway-versus-Ingress API is selected during capability detection based on the installed GKE and provider surfaces, but the security contract is fixed: trusted HTTPS, fail-closed identity enforcement, no public bypass, and server-side authorization logs. `gke_mcp_hostname` and its DNS/certificate authorization are explicit apply prerequisites. Implementation must stop rather than downgrade to plain HTTP or anonymous access when those prerequisites are absent.

An Internal Load Balancer was rejected for this change because no private route from the managed Agent Runtime has been established. A public `LoadBalancer` Service without application-layer authentication was rejected because network reachability would become the only access control.

### 5. Keep Registry lifecycle changes separate from runtime deployment

Cloud Run and GKE retain distinct stable Service IDs. Registry create/update/delete automation also resolves the projected endpoint IDs used by Gateway/IAP IAM. Updating an interface within the approved host policy must not require rebuilding the Agent Runtime image. A host change requires updating both the Registry entry and the reviewed Gateway/host allowlist; the deployment workflow verifies they agree before enabling traffic.

Lifecycle tests use a disposable duplicate or controlled update: establish success, update the registered interface and observe re-resolution, then remove or disable the entry and verify no stale-URL fallback. The test restores the desired entry before later validation or teardown.

### 6. Require correlation across all evidence layers

Each E2E invocation receives a non-secret correlation ID propagated in MCP input or an allowed request header. Evidence records the Agent Runtime invocation, Registry Service and endpoint IDs, metadata validation result, Gateway/IAP allow or deny log, endpoint authorization result, MCP Tool call, hosting-side application log, and final Claude response.

Negative cases must demonstrate where processing stopped. In particular, an Agent Gateway deny must have no corresponding endpoint or Tool log, and an endpoint authorization deny must have a Gateway allow but no Tool execution. Tokens and credential payloads are redacted at collection time.

## Risks / Trade-offs

- [Claude Agent SDK remote MCP or dynamic headers differ from the assumed API] → Pin after capability tests, add adapter-level contract tests, and stop before cloud deployment if the SDK cannot send refreshed credentials.
- [Agent Runtime effective identity cannot mint an ID token directly] → Use one dedicated keyless caller Service Account with narrowly scoped token-creator delegation and record the complete identity chain.
- [Agent Gateway requires additional Google control-plane endpoints] → Inventory actual deny logs, register only required managed endpoints, and keep them separate from MCP destination approvals.
- [GKE IAP/Gateway integration or trusted DNS is unavailable] → Treat trusted hostname and certificate authorization as prerequisites; do not create an unauthenticated fallback and mark live GKE E2E incomplete rather than PASS.
- [Registry projection or IAM propagation is eventually consistent] → Use bounded retries keyed to exact Service/endpoint IDs and record propagation time separately from request latency.
- [Registry metadata is changed to an allowed but unintended endpoint] → Validate immutable project/location/Service ID plus reviewed host and Tool schema, and require a matching Gateway policy update for host changes.
- [Two authorization layers obscure failures] → Emit stage-specific errors and correlate Gateway, endpoint, and MCP logs instead of using the final Claude response alone.
- [External GKE HTTPS resources add cost and attack surface] → Use a single small test backend, enforce IAP, inventory the public surface, and delete load-balancing resources immediately after evidence review.

## Migration Plan

1. Verify current Agent Registry, Agent Gateway, IAP, Agent Runtime identity, Claude Agent SDK remote MCP, GKE HTTPS/IAP, DNS, and Terraform provider capabilities; freeze concrete command/resource surfaces in evidence.
2. Add local contract tests for Registry resolution, metadata allowlisting, token refresh, Claude Tool configuration, failure staging, and evidence sanitization.
3. Recreate the existing Cloud Run and GKE MCP backends with immutable image digest and complete their previous runtime-only regression tests.
4. Reuse the approved existing Agent Gateway, create the dedicated Agent Runtime, required Google control-plane Registry endpoints, runtime identity bindings, and MCP Registry entries. Review a create-only plan before apply.
5. Bind only the Cloud Run endpoint in Gateway and endpoint IAM; run allowed, missing-token, wrong-audience, unauthorized-identity, and unregistered-destination tests.
6. Provision the GKE HTTPS/IAP front door using the supplied hostname and certificate, bind its Registry endpoint and endpoint authorization, then repeat the positive and negative tests.
7. Invoke Agent Runtime with separate Cloud Run and GKE objectives; require Claude Tool-selection evidence and correlated Gateway, endpoint, and MCP logs for each PASS.
8. Exercise Registry update and removal without rebuilding the runtime image, verify re-resolution and stale fallback rejection, then restore desired state.
9. Update README, runbook, validation matrix, measured comparison, and sanitized evidence. Review teardown targets before deleting only change-owned resources.

Rollback proceeds in reverse order: remove Agent Runtime endpoint permissions, delete the runtime, remove Registry entries, delete GKE HTTPS resources and workloads, then destroy the isolated Terraform resources. The reused existing Gateway and its policy remain outside this state and are not deleted by this change. APIs remain enabled and existing Agent Platform/GKE resources remain untouched.
