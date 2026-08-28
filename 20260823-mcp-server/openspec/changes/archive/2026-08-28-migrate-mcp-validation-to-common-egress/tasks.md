## 1. Live inventory and migration guardrails

- [x] 1.1 Inventory `common/terraform` outputs and live `common-egress`/Network Attachment without printing root certificate bodies; verify project, location, full ID, `AGENT_TO_ANYWHERE`, `MCP`, Registry path, VPC attachment, accepted producer connection, etag, and active state agree in sanitized Japanese evidence.
- [x] 1.2 Inventory every active Agent Runtime and its Gateway association in `nnyn-dev`; verify the migration target is identified and document the observed project/direction exclusivity without attributing it to an authz extension unless live evidence supports that conclusion.
- [x] 1.3 Inventory consumer Terraform state, Registry Services/MCP Servers/endpoints, Runtime effective identity, `roles/iap.egressor`, endpoint IAM, Cloud Run, GKE, and shared-Gateway consumers; verify ownership and migration actions are classified as consumer-owned, common-owned, unrelated, or stale.
- [x] 1.4 Add a scope guard that rejects any plan action against `common-egress`, `common-agent-gateway-vpc`, its subnet/Network Attachment, unrelated Runtime/Registry/GKE resources, or the default VPC; verify guard fixtures cover add/change/replace/destroy and accepted consumer-only plans.

## 2. Shared Gateway consumer configuration

- [x] 2.1 Implement a fail-closed Gateway preflight that compares the required fully qualified `agent_gateway_id` with owner output and live API attributes; verify tests reject the retired Gateway name, mismatched project/location/direction/protocol/Registry/attachment, missing resource, and non-active operation.
- [x] 2.2 Update Terraform inputs, locals, examples, outputs, and static tests to select `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` without declaring or importing shared resources; verify `terraform fmt -check`, `terraform validate`, and tests pass.
- [x] 2.3 Remove all executable defaults, data dependencies, and operator commands that select `agw-20260822-egress`; verify repository search leaves the old name only in clearly labeled historical evidence or migration explanation.
- [x] 2.4 Update the Runtime image build to derive the selected Gateway identity from reviewed input, require non-empty TLS inspection CA data, install it into the OS trust store, and record only certificate fingerprint/count; verify build tests fail closed for missing/invalid CA and repository scans find no PEM body.
- [x] 2.5 Add a container-level trust test and immutable image digest check; verify the built Runtime image trusts the selected Gateway CA and deployment inputs reject mutable tags.

## 3. Consumer-owned Registry and bounded IAM

- [x] 3.1 Replace `20260822` control-plane Registry endpoint data sources with collision-resistant consumer-owned Agent Registry, regional/global Vertex AI, and IAM Credentials Service/interface resources; verify a Terraform plan succeeds when the retired entries are absent.
- [x] 3.2 Keep Cloud Run and optional GKE MCP Server registrations consumer-owned and validate their Service IDs, HTTPS hosts, protocol bindings, and Tool specifications; verify Terraform/data lookups resolve only the intended entries.
- [x] 3.3 Bind `roles/iap.egressor` for the Runtime effective identity only on the required control-plane endpoints and MCP Server resources; verify IAM inventory has no project-wide egress, owner/editor, `allUsers`, or unrelated endpoint binding.
- [x] 3.4 Reconcile Registry viewer, ID-token minting, Cloud Run Invoker, Artifact Registry pull, and Vertex AI permissions as separate least-privilege bindings; verify the effective identity chain and each authorization responsibility are recorded independently.
- [x] 3.5 Add an unregistered or unbound control destination that cannot execute the validation Tool; verify it has no egress or endpoint-invocation binding and cannot affect unrelated services.

## 4. Local regression and immutable artifacts

- [x] 4.1 Run dependency installation, unit tests, Terraform tests, Tool-spec consistency, SDK remote-MCP contract, container build, and local MCP smoke tests; verify every pre-cloud check has a reproducible command and actual result.
- [x] 4.2 Build and push the MCP Server and CA-enabled Agent Runtime images, resolve immutable digests, scan captured output for secrets/PEM bodies, and verify Terraform inputs use the reviewed `@sha256:` references.
- [x] 4.3 Generate a scoped migration plan with the reviewed digests and `common-egress` ID; verify the plan contains only intended consumer-owned create/update actions, no unintended GKE deletion, and no common-owned or unrelated action.

## 5. Runtime migration and cloud reconciliation

- [x] 5.1 Apply the reviewed consumer-only plan and save sanitized apply/resource evidence; verify no common-owned resource changed and stop rather than broadening ownership if the platform requires an additional shared policy/extension.
- [x] 5.2 Read the deployed Runtime from the live API; verify its image digest, `AGENT_IDENTITY`, effective identity, and exact `common-egress` association match the reviewed plan.
- [x] 5.3 Read back Registry/control-plane resources, MCP Server entries, endpoint-scoped egress IAM, Cloud Run IAM, and Runtime artifact pull access; verify each live value matches Terraform and no legacy `20260822` dependency remains.
- [ ] 5.4 Exercise the required Agent Registry, regional/global Vertex AI, IAM Credentials, and Artifact Registry control-plane calls from the Runtime path; verify failures are attributed to discovery, Gateway egress, identity, or service IAM instead of being reported as generic MCP success.

## 6. Cloud Run governed E2E regression

- [ ] 6.1 Invoke the Registry-resolved Cloud Run MCP endpoint directly through the migrated Agent Runtime; verify one correlation ID links Runtime configuration, Registry Service ID, resolved host, effective identity, `common-egress` allow evidence, Cloud Run authorization, Tool result, and server-side MCP execution log.
- [ ] 6.2 Invoke the same objective through Claude Agent SDK and require remote Tool selection; verify the Claude Tool event, final response, Registry resolution, Gateway allow, Cloud Run request, and MCP execution all refer to the same correlation ID before marking PASS.
- [ ] 6.3 Run Cloud Run requests with no token, wrong audience, and an endpoint-unauthorized identity; verify Cloud Run rejects each before Tool execution and no corresponding MCP execution log exists.
- [ ] 6.4 Request an unregistered or egress-unbound destination from Agent Runtime; verify `common-egress` denies it before endpoint delivery and no endpoint/application execution log exists for the correlation ID.
- [ ] 6.5 Remove a disposable MCP Server egress binding temporarily, verify Gateway denial, restore the exact reviewed binding, and verify the approved E2E recovers without changing shared Gateway resources.

## 7. Private GKE route validation

- [x] 7.1 Confirm the `common-egress` Network Attachment path and design a consumer-owned private DNS plus trusted internal HTTPS Load Balancer frontend backed by the GKE `ClusterIP`; verify the reviewed plan exposes neither Pod nor Kubernetes Service directly to the Internet.
- [ ] 7.2 Apply the GKE private-front-door phase only after a scoped plan passes the common-resource and unrelated-resource guards; verify internal frontend address, DNS, certificate, firewall/backend health, endpoint authorization, ClusterIP, and Pod exposure separately.
- [ ] 7.3 Invoke the Registry-resolved GKE MCP Tool from Agent Runtime through `common-egress`; verify Gateway VPC routing, internal frontend authorization, backend delivery, Claude Tool event, and Pod execution share one correlation ID.
- [ ] 7.4 Run no-token, wrong-audience, endpoint-unauthorized, and egress-unbound GKE cases; verify each denial occurs at the expected layer and no MCP Tool log exists after rejection.
- [x] 7.5 If any private-route prerequisite cannot be constructed or evidenced, record GKE as SKIP/FAIL with the exact blocker; verify operator-side or in-cluster smoke results are not labeled Agent Runtime E2E and do not introduce a public unauthenticated fallback.

## 8. Documentation, evidence, and retained state

- [x] 8.1 Update README and runbook in Japanese with `common-egress` ownership, preflight, CA trust, Runtime association, Registry discovery, Gateway egress, endpoint authentication, Cloud Run/GKE routes, reproducible commands, and the rule that Registry discovery alone does not imply connectivity or authorization.
- [x] 8.2 Add Japanese evidence for inventory, plan/apply, identity/IAM, Cloud Run positive/negative tests, and GKE results; verify every PASS names caller, effective identity, source, Gateway, destination, authorization layer, correlation ID, expected/actual result, and log reference without secrets or PEM bodies.
- [x] 8.3 Update `validation-report.md` with PASS/FAIL/SKIP per layer and compare results against the prior old-Gateway baseline; verify no Claude or Agent Runtime E2E row is PASS without both Tool-selection and server-side execution evidence.
- [x] 8.4 Run a final Terraform drift plan, repository secret/certificate scan, OpenSpec strict validation, and documentation command review; verify only intended retained consumer resources exist and common/shared consumers remain unchanged.
- [x] 8.5 Produce a consumer-only teardown inventory and plan for later human review, but do not apply it; verify `common-egress`, common VPC/subnet/Network Attachment, unrelated Registry entries, existing GKE, and other Runtime consumers are excluded.
