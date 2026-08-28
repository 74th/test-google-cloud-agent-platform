## 1. Scope and Live Baseline

- [x] 1.1 Record the current `common` backend/workspace/state ownership and the consumer state boundary, and verify the inventory shows Gateway, VPC, subnet, and Network Attachment only in the common state with no common resource imported by `20260823-mcp-server`.
- [x] 1.2 Capture non-secret live read-backs for `common-egress` ID, etag, state, direction, protocols, registries, Network Attachment, DNS peering, attached security/authz policy or extension, and required API versions; verify every recorded project/location is `nnyn-dev/us-central1`.
- [x] 1.3 Inventory existing Agent Runtime associations and known `common-egress` consumers plus their recent allow/deny rules, and verify the change impact table identifies any consumer that could regress before a policy plan is created.
- [x] 1.4 Inspect the pinned `google`/`google-nightly` provider schemas, Network Services/Network Security API discovery, and current `gcloud` commands for the actual Gateway allow/enforcement surface; verify the evidence names the supported resource, fields, mutability, etag semantics, and whether Terraform can manage it without replacement.
- [x] 1.5 Add scope guards to the common validation workflow for project, region, Gateway ID, no Gateway/VPC/Network Attachment replacement or deletion, no Autopilot GKE mutation, and no destroy command; verify `scripts/validate.sh` and `tests/test_terraform.sh` reject representative unsafe fixtures or plans.

## 2. Registry Discovery Denial Diagnosis

- [x] 2.1 Add a bounded probe/evidence helper that generates a non-secret probe ID and UTC window, invokes the specified Runtime/Registry target without persisting credentials, and collects only the relevant structured Gateway/control-plane log fields; verify a dry run or fixture test redacts Authorization, token, CA body, private key, credential, and Secret content.
- [x] 2.2 Reproduce one GKE Registry discovery failure against Runtime `2332905838663958528` and Service `mcp-20260823-gke`, and verify the evidence joins the Runtime response to the `common-egress` request by correlation ID or explicitly labelled provisional time/resource/method tuple.
- [ ] 2.3 Determine what `240.0.0.2:443` represents using an official document, live API/metadata relation, or same-request structured log field, and verify the evidence distinguishes Registry scope, host/port/protocol, effective identity, policy/extension, and TLS hypotheses without attributing the failure to GKE or CA by inference.
- [x] 2.4 Identify the exact resource and rule that owns `default_denied`, or write a blocker packet when it cannot be proven; verify the result includes enforcement layer, owner, required common-owned policy/resource, consumer non-ownership reason, and minimum retry condition.
- [x] 2.5 Read back the Runtime effective principal and the resource-scoped `roles/iap.egressor` binding for `mcp-20260823-gke`, and verify the evidence states separately whether that binding authorizes Registry/endpoint access and whether an additional Gateway-side subject condition is required.

## 3. Minimal Common-Owned Allow Implementation

- [x] 3.1 From observed denied requests, define the minimum allow tuple inventory with logical name, exact host, port, protocol, principal/resource scope, purpose, enforcement resource, and rollback action; verify no candidate uses `allUsers`, Owner/Editor, empty or wildcard host, broad public allow, or an unobserved Google API endpoint.
- [x] 3.2 If Terraform supports the proven enforcement surface, implement typed allow inputs/resources in the common root while retaining explicit default-deny and existing consumer rules; verify Terraform validation and static tests cover accepted tuples and reject wildcard host, wrong port/protocol, broad principal, and duplicate rule names.
- [x] 3.3 If only an official API surface exists, document an idempotent etag-guarded mutation and Terraform drift/rollback behavior and obtain a separate approval before implementing it; if no safe supported surface exists, complete a blocker report and verify no cloud write or speculative fallback occurred.
- [x] 3.4 Extend machine-readable outputs or read-back tooling only as needed to expose policy/rule identifiers without secrets, and verify the output still includes unchanged Gateway, VPC, subnet, and Network Attachment IDs.
- [x] 3.5 Update the common runbook with exact preflight, plan review, apply gate, post-read-back, positive/negative probe, and tuple-only rollback procedures; verify the runbook never instructs `terraform destroy`, TLS verification bypass, anonymous HTTP, public frontend creation, or consumer import of common resources.

## 4. Plan, Approval, and Common-Side Read-Back

- [x] 4.1 Run formatting, initialization, validation, static tests, and a refresh-only plan, and verify provider/state drift is either absent or fully explained before producing a normal saved plan.
- [x] 4.2 Produce and review a saved common Terraform plan that lists resource, principal, host, port, protocol, scope, existing-consumer impact, and rollback; verify it has no replacement, deletion, unrelated IAM/API change, or broadening beyond the diagnosed tuples.
- [x] 4.3 Present the saved plan and pre-change Gateway ID/etag/direction/protocol/Registry/Network Attachment read-back at the required human approval boundary, and verify no apply occurs until explicit approval is received.
- [x] 4.4 After explicit approval, apply only the reviewed common plan and capture post-apply state/API read-back; verify Gateway identity, direction, protocol, Registry, VPC path, and existing rules remain stable while only approved rules change.
- [ ] 4.5 Run an approved positive probe and adjacent unauthorized identity/host/port/protocol negative probes, and verify Gateway logs name the expected allow rule while out-of-scope traffic still matches a deny rule.

## 5. Registry and Control-Plane Progression

- [x] 5.1 Retry Runtime Registry discovery for `mcp-20260823-gke` after each approved tuple, and verify the evidence records the next observed destination/decision rather than treating discovery success as endpoint or MCP success.
- [ ] 5.2 Add any Vertex AI regional/global or IAM Credentials tuple only when a new same-probe denial proves it is required, repeating the scoped plan/approval/read-back flow; verify every added endpoint has observed evidence and a negative regression case.
- [ ] 5.3 Validate the resolved Registry Service metadata and interface for project, location, Service ID, HTTPS scheme, host `gke.mcp-20260823.internal`, port/path, MCP binding, and Tool schema; verify mismatched host/protocol/schema fails before credential generation or endpoint connection.

## 6. Private Route, TLS, and Endpoint Authorization Preconditions

- [ ] 6.1 Read back the Network Attachment accepted connection, VPC/subnet relation, DNS peering suffix, private zone/record, `INTERNAL_MANAGED` forwarding rule at `10.240.0.5`, target HTTPS proxy, certificate metadata, backend health, NEG, ClusterIP `10.242.0.20:80`, and Pod; verify no Internet-facing frontend or external Service IP exists.
- [ ] 6.2 Validate Runtime-to-Gateway CA presence/verification/fingerprint separately from Gateway-to-origin SNI, SAN, validity, issuer/fingerprint, and supported trust chain; verify no certificate body/private key is saved and no `-k`, hostname bypass, or plain HTTP is used.
- [ ] 6.3 Obtain consumer-owner evidence for endpoint authorization with approved Runtime identity/audience and credential-less, wrong-audience, or wrong-identity negative cases; verify common state is unchanged and mark governed E2E blocked if the internal endpoint still accepts unauthenticated requests.
- [ ] 6.4 Run a post-Gateway private-path probe and identify the last successful and first failing layer among DNS, Network Attachment, TLS, frontend, endpoint authorization, backend, ClusterIP, and Pod; verify in-cluster/operator smoke is labelled only as backend baseline.

## 7. Correlated Agent Runtime E2E

- [ ] 7.1 Generate one correlation ID and invoke the registered GKE Tool exactly once from Agent Runtime, and verify the Runtime response records the target Service ID and resolved host without accepting a prompt-supplied URL.
- [ ] 7.2 Collect the matching Registry, Gateway allow, endpoint authorization, Internal HTTPS Load Balancer/backend, and GKE Pod execution records, and verify all records use the same correlation ID plus consistent Runtime identity, host, Tool name, and result.
- [ ] 7.3 Execute the required unauthorized negative case without Tool execution, and verify Gateway or endpoint authorization denies it and the Pod has no execution log for that correlation ID.
- [ ] 7.4 Assign independent `PASS`, `FAIL`, `SKIP`, or `BLOCKED` verdicts to discovery, Gateway, private routing/TLS, endpoint authorization, and MCP execution, and verify Agent Runtime E2E is `PASS` only when every required positive layer and negative authorization case is evidenced.

## 8. Evidence and Closeout

- [ ] 8.1 Publish a non-secret common-side evidence report containing reproducible commands, UTC timestamps, caller, effective identity, route, resource IDs, authorization layer, log queries, correlation IDs, before/after read-backs, and verdicts; verify a secret-pattern scan finds no token, CA body, private key, credential, or Secret value.
- [ ] 8.2 Update the common runbook and validation documentation with the final supported access contract, owner/approval boundaries, rollback, and blocker recovery procedure; verify consumer documentation can use the Gateway ID without remote state access or common resource ownership.
- [ ] 8.3 Run `terraform fmt -check`, Terraform validation, common static/integration tests, `scripts/validate.sh`, and `openspec validate enable-common-egress-registry-and-private-gke --strict`; verify all applicable checks pass and any cloud-dependent SKIP/BLOCKED item cites its exact unmet prerequisite.
- [ ] 8.4 Confirm no `terraform destroy` ran, no existing Autopilot GKE or public frontend changed, and no unrelated worktree file was modified; verify the final scope inventory and cloud read-back are attached to the closeout report.
