## 1. Capability and prerequisite discovery

- [x] 1.1 Inventory the current project APIs, Agent Runtime/Gateway/Registry resources, GKE clusters, IAM bindings, networks, DNS, certificates, and provider versions read-only; save sanitized output and verify every pre-existing resource is marked out of scope.
- [x] 1.2 Verify the installed and current official command/resource surfaces for Agent Runtime `AGENT_IDENTITY`, Agent Gateway MCP egress, Agent Registry MCP endpoints, endpoint-scoped `roles/iap.egressor`, and IAP authorization logs; record exact supported syntax and verify no design assumption depends only on adjacent-repository behavior.
- [x] 1.3 Verify a pinned Claude Agent SDK version supports remote Streamable HTTP MCP servers and refreshed request headers; run a local authenticated fake-server contract test and stop before cloud creation if the SDK path cannot execute `tools/list` and `tools/call`.
- [x] 1.4 Verify whether the Agent Runtime effective identity can mint audience-bound ID tokens directly; otherwise document and test the dedicated keyless caller Service Account impersonation chain, including a denied attempt to mint for any other Service Account.
- [ ] 1.5 Select and verify the supported GKE Gateway-or-Ingress plus IAP configuration, `gke_mcp_hostname`, DNS control, and trusted certificate prerequisites; prove the hostname can be authorized without committing secrets. A private HTTP Gateway may be used only as a separately recorded routing diagnostic and is not an authorization result.

## 2. MCP runtime and Agent Runtime client

- [x] 2.1 Add a non-secret correlation identifier and hosting-target marker to the MCP validation flow and sanitized server logs; verify automated tests correlate a Tool result with the expected Cloud Run or GKE target without changing the registered Tool schema unexpectedly.
- [x] 2.2 Implement Registry resolution by fixed project, location, and Cloud Run/GKE Service IDs with no endpoint URL accepted from prompt or runtime URL settings; verify unit tests reject an arbitrary URL before any network call.
- [x] 2.3 Implement validation of Registry Service ID, HTTPS scheme, allowed host, `JSONRPC` binding, and Tool schema; verify malformed host, protocol, and schema fixtures fail before credential generation.
- [x] 2.4 Implement per-invocation resolution or bounded cache invalidation for Registry lifecycle changes; verify tests observe an interface update and reject a deleted entry without stale-URL fallback.
- [x] 2.5 Implement short-lived audience-bound credential generation for Cloud Run and the GKE authentication audience, redacting all credential values; verify tests cover refresh, exact audience, wrong audience, mint denial, and sanitized errors.
- [x] 2.6 Implement the Agent Platform custom-container `query` and `stream_query` contract using Claude Agent SDK with Registry-resolved remote MCP configurations; verify adapter tests show Claude receives only the approved Cloud Run/GKE Tools and never a user-supplied URL.
- [x] 2.7 Add deterministic Cloud Run and GKE validation objectives that require Claude to select the corresponding remote MCP Tool; verify a fake SDK test fails when Claude returns an answer without a Tool execution event.
- [x] 2.8 Implement stage-specific errors for Registry discovery, metadata validation, token generation, Gateway denial, endpoint authorization, MCP protocol, and Tool execution; verify each injected failure maps to one stage and is not converted into a successful model response.
- [x] 2.9 Build a validation runner that records invocation input, Registry/endpoint IDs, validated host, identity chain, correlation ID, Claude Tool events, final response, and log references while excluding tokens and credentials; verify an automated secret scan passes on fixture evidence.

## 3. Governed infrastructure

- [x] 3.1 Extend Terraform/provider constraints and variables for independently named Agent Runtime, Agent Gateway, Registry endpoints, caller identity, GKE hostname, DNS/certificate, and IAP resources; run `terraform fmt -check`, initialization, validation, and static naming checks successfully.
- [x] 3.2 Add the dedicated Agent Runtime image repository and runtime definition with `AGENT_IDENTITY`, Vertex AI Claude settings, telemetry, and the approved existing Agent Gateway association; verify plan/tests contain no Anthropic API key, Service Account key, or reuse of existing runtime IDs.
- [x] 3.3 Add a dedicated MCP caller identity only if direct runtime token minting is unsupported, with token-creator delegation restricted to the runtime effective principal and target-specific invocation roles; verify IAM inventory contains no project-wide owner/editor or unrestricted Service Account impersonation.
- [x] 3.4 Reuse the approved existing fail-closed Agent Gateway, remove the duplicate experiment Gateway/IAP resources, and add required Google control-plane Registry endpoints; verify the runtime is attached to the existing gateway and its prior policy is not managed by this state.
- [x] 3.5 Manage Cloud Run and GKE MCP Registry Services plus projected endpoint lookup, and bind `roles/iap.egressor` only for the runtime effective identity on the two approved endpoints; verify an unregistered control endpoint has no binding.
- [x] 3.6 Bind the authorized runtime/caller identity to Cloud Run Invoker without `allUsers`; verify Terraform tests and the rendered IAM policy distinguish Registry read, Gateway egress, token mint, and Cloud Run invocation roles.
- [ ] 3.7 Add the GKE authenticated HTTPS front door backed by the existing `ClusterIP` MCP Service, including trusted TLS, IAP, health checks, and no direct Pod/Service public exposure; verify rendered resources contain no anonymous access or plain-HTTP external listener. The separate Gateway API HTTP diagnostic does not satisfy this task.
- [ ] 3.8 Grant the authorized runtime/caller identity only the GKE front-door access role and configure the exact token audience; verify a separate unauthorized identity has neither Gateway endpoint permission nor GKE access.
- [x] 3.9 Generate and review a create-only plan for all phases, save a sanitized summary, and verify it contains only the new experiment prefix/labels with no change or destroy action against existing Agent Runtime, Agent Gateway, Autopilot, default VPC, or unrelated Registry entries.

## 4. Local and hosting regression validation

- [x] 4.1 Run dependency installation, unit tests, MCP Tool-spec consistency, Terraform tests, container build, and local smoke tests; verify all pre-cloud checks pass with pinned versions.
- [x] 4.2 Build and push immutable MCP and Agent Runtime images, resolve both digests, and verify all Cloud Run, GKE, validation Job, and Agent Runtime definitions reference the reviewed digests rather than mutable tags.
- [x] 4.3 Apply the isolated Cloud Run/GKE backend phase and repeat the archived runtime-only tests; verify Cloud Run authorized/unauthorized behavior and GKE cluster-local MCP execution before introducing Agent Runtime or Gateway variables.
- [x] 4.4 Apply the Agent Runtime/Gateway/Registry phase and inventory runtime effective identity, gateway attachment, Registry endpoint IDs, egress bindings, and endpoint IAM; verify every observed value matches reviewed outputs.

## 5. Cloud Run governed E2E validation

- [x] 5.1 Invoke the Registry-resolved Cloud Run MCP endpoint from Agent Runtime with the approved Gateway and endpoint identity; verify discovery, Gateway allow, Cloud Run authorization, MCP Tool execution, correlation log, and direct Tool result all succeed independently.
- [ ] 5.2 Invoke the Cloud Run endpoint without a token, with the wrong audience, and with an endpoint-unauthorized identity; verify each request is rejected before Tool execution and save the distinct authorization evidence.
- [ ] 5.3 Request an unregistered or Registry-unbound control endpoint from Agent Runtime; verify Agent Gateway default-denies the request and no Cloud Run/application execution log exists for its correlation ID.
- [x] 5.4 Invoke Agent Runtime with the Cloud Run objective and require Claude Agent SDK to select the remote Tool; verify the final response, SDK Tool event, Registry Service ID, Gateway allow log, Cloud Run request log, and MCP correlation all refer to the same invocation.

## 6. GKE governed E2E validation

- [ ] 6.1 Apply the trusted GKE HTTPS/IAP front door and inventory DNS, certificate, listener, backend, IAP, Kubernetes Service, and Pod exposure; verify only the authenticated HTTPS entry is externally reachable and the `ClusterIP` remains internal.
- [ ] 6.2 Invoke the Registry-resolved GKE MCP endpoint from Agent Runtime with the approved Gateway and endpoint identity; verify discovery, Gateway allow, GKE front-door authorization, backend Tool execution, and correlation log all succeed independently.
- [ ] 6.3 Invoke the GKE endpoint without a token, with the wrong audience, and with an endpoint-unauthorized identity; verify each request is rejected before reaching the MCP Tool and correlate front-door deny evidence with the absence of application execution logs.
- [ ] 6.4 Remove the runtime's GKE Registry-endpoint egress binding temporarily and invoke the same objective; verify Agent Gateway denies it before GKE, then restore the reviewed binding and confirm access recovers.
- [ ] 6.5 Invoke Agent Runtime with the GKE objective and require Claude Agent SDK to select the remote Tool; verify the final response, SDK Tool event, Registry Service ID, Gateway allow log, GKE authorization log, and Pod log share the same correlation ID.

## 7. Registry lifecycle and governance validation

- [x] 7.1 Update a disposable approved Registry interface within the reviewed host policy and invoke Agent Runtime again; verify it resolves the updated interface without rebuilding the Agent Runtime image or changing a URL setting.
- [x] 7.2 Delete or disable the disposable Registry entry and invoke the same logical target; verify discovery fails, no stale URL is contacted, and neither Gateway nor endpoint has an execution log for the correlation ID.
- [ ] 7.3 Attempt Registry mutation with the Agent Runtime identity and endpoint invocation with a Registry-read-only identity; verify Registry mutation and MCP execution are independently denied at their expected boundaries.
- [x] 7.4 Restore the desired Registry entries and bindings, run a final drift check, and verify Terraform reports no unintended changes before evidence review.

## 8. Reporting and teardown

- [x] 8.1 Update README and runbook with the three control layers, exact Agent Runtime-to-Cloud Run/GKE flows, identities, prerequisites, retry behavior, negative tests, evidence locations, and explicit distinction between discovery, egress authorization, endpoint authorization, and Tool execution; verify all documented commands are reproducible.
- [x] 8.2 Produce a PASS/FAIL/SKIP matrix for every required layer and test case, including expected/actual outcomes and correlated evidence; verify no Agent Runtime or Claude E2E item is PASS without both SDK Tool-selection and server-side execution evidence.
- [x] 8.3 Compare Cloud Run and GKE for governed Agent Runtime integration using measured setup effort, identity/token handling, Gateway policy, endpoint authentication, latency, public surface, cost, and operations; verify limitations and production prerequisites are explicit.
- [x] 8.4 Generate a teardown plan and Registry/Gateway/Kubernetes deletion inventory, run the scope guard, and verify only the new experiment-owned resources are targeted before any destructive action.
- [x] 8.5 After operator evidence review, remove the new Registry entries/bindings, Agent Runtime, Agent Gateway, GKE HTTPS resources/workloads, and Terraform resources; verify no experiment resource or stale kubeconfig context remains while existing resources and enabled APIs are unchanged.
