## 1. Environment Discovery and Guardrails

- [x] 1.1 Inventory project `nnyn-dev` APIs, regions, VPCs, subnets, Artifact Registry repositories, Cloud Run services, and GKE clusters read-only; save sanitized output and verify the existing Autopilot cluster is explicitly identified as out of scope.
- [x] 1.2 Check current official Agent Registry documentation, installed `gcloud` version/help, API availability, supported locations, and Terraform provider resources; record the chosen registration surface and verify a concrete location and command syntax are documented.
- [x] 1.3 Select non-overlapping node, Pod, and Service CIDRs from the inventory, define project/region/zone/prefix variables, and verify every planned name or label carries `20260823-mcp-server` without conflicting with an existing resource.

## 2. MCP Server and Container

- [x] 2.1 Scaffold the MCP application with locked dependencies and developer commands, and verify a clean dependency installation succeeds.
- [x] 2.2 Implement the stateless Streamable HTTP `/mcp` server and one deterministic test Tool listening on `0.0.0.0:$PORT`, and verify automated tests cover initialization, `tools/list`, valid Tool execution, and invalid input.
- [x] 2.3 Add the versioned Agent Registry Tool specification plus a consistency checker, and verify the checker reports no difference in Tool name, description, or input schema from runtime `tools/list`.
- [x] 2.4 Add a non-root production Dockerfile and local MCP smoke test, then build and run the image locally and verify initialization and Tool execution succeed through the container port.

## 3. Terraform Foundation and Cloud Run

- [x] 3.1 Add Terraform provider/version constraints, variables, required Google Cloud APIs, and the dedicated Artifact Registry repository; run `terraform fmt -check`, `terraform init`, and `terraform validate` successfully.
- [x] 3.2 Add dedicated Cloud Run runtime, test invoker, and GKE node/workload identities with only required IAM bindings, and verify no workload uses the default Compute Engine Service Account and no `allUsers` binding exists.
- [x] 3.3 Add the Cloud Run v2 service using an immutable image reference, IAM-only invocation, minimum instances 0, bounded maximum instances, and experiment labels; verify Terraform configuration tests or plan assertions cover those settings.
- [x] 3.4 Generate and review the GKE-disabled Terraform plan, save sanitized plan evidence, and verify it creates only experiment-scoped resources without changing or deleting existing resources.

## 4. Cloud Run and Agent Registry Validation

- [x] 4.1 Build and push a versioned MCP image, resolve its digest, update the deployment input to that digest, and verify the same immutable reference is recorded for both hosting targets.
- [x] 4.2 Apply the reviewed Cloud Run phase and inventory the resulting service, revision, identity, IAM, URL, and scaling settings; verify each observed value matches the Terraform outputs and expected experiment scope.
- [x] 4.3 Run the Cloud Run MCP smoke test with an authorized ID token and without authentication, and save evidence that the authorized Tool call succeeds while the unauthenticated request is rejected before Tool execution.
- [x] 4.4 Implement idempotent Agent Registry create/update, describe, search, and delete automation for separate Cloud Run and GKE entries using the verified Terraform resource or `gcloud` surface, and verify dry-run/static checks contain no credential or temporary public-access step.
- [x] 4.5 Register the Cloud Run MCP Server, search for its Server and Tool, then invoke the discovered interface with IAM authentication; save separate discovery and execution evidence and verify both match the expected Tool specification and endpoint.
- [x] 4.6 Identify an available Cloud Run instance-count or equivalent metric, wait for observable idle scale-down, then compare a post-idle call with a warm call; record startup/log and latency evidence, marking the scale-to-zero result SKIP rather than PASS if zero instances cannot be demonstrated.

## 5. GKE Standard Validation

- [x] 5.1 Add Terraform for a custom VPC, subnet with secondary ranges, zonal VPC-native GKE Standard cluster, Workload Identity, and a small dedicated node pool behind a default-off feature flag; verify plan assertions show no Autopilot mode, external workload Load Balancer, or default node Service Account.
- [x] 5.2 Add Kubernetes manifests for the digest-pinned MCP Deployment, ClusterIP Service, and disposable in-cluster validation Job, and verify rendered manifests use the same image digest and expose only the internal `/mcp` service.
- [x] 5.3 Enable GKE, generate and review a second Terraform plan, apply it, and save evidence that the new Standard cluster uses the dedicated VPC/ranges and reaches Ready state without modifying existing clusters.
- [x] 5.4 Deploy the MCP workload and run the validation Job against the cluster DNS URL; verify rollout, MCP initialization, `tools/list`, and deterministic Tool execution all succeed and capture application/Job logs.
- [x] 5.5 Register and search the GKE Agent Registry entry, pass the discovered cluster-local URL to an in-cluster execution check, and save separate evidence that Registry metadata, runtime Tool schema, and executed endpoint agree.

## 6. Results and Teardown Readiness

- [x] 6.1 Create the reproducible runbook with prerequisites, sanitized commands, variables, build/deploy/register/validate order, resource inventory, and evidence locations; verify a secret scan finds no token, credential, or sensitive Terraform value.
- [x] 6.2 Complete the PASS/FAIL/SKIP report for every minimum validation item with expected result, actual result, evidence, issue, and interpretation; verify no PASS entry lacks command, API, resource-state, metric, or log evidence.
- [x] 6.3 Compare Cloud Run and GKE using measured deployment effort, authentication, reachability, scale-to-zero, cold-start latency, operational load, and ongoing cost; verify the conclusion states the preferred stateless MCP host, when GKE is justified, limitations, and pre-production follow-ups.
- [x] 6.4 Document Agent Registry entry removal and Terraform teardown, produce a destroy plan for explicit review, and verify its targets are limited to `20260823-mcp-server` resources before any destructive cleanup is performed.
