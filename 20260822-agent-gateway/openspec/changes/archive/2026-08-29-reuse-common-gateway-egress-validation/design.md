## Context

See proposal.md for motivation. This checkout now retains historical egress-validation code and evidence, while its Terraform root intentionally contains no managed resources. `common/terraform` owns `common-egress`, its networking, and the single IAP Authz Extension, and exposes the Gateway through `agent_gateway_id`. The original egress-validation spec, scripts, and evidence format establish the GitHub allow, Cabinet Office default-deny, and TLS inspection checks that must remain meaningful after ownership changes.

## Goals / Non-Goals

**Goals:**

- Restore this checkout as a consumer-owned validation environment that accepts one explicit common Gateway ID.
- Make ownership mechanically visible in Terraform plans and deployment validation.
- Re-run the historical live checks with evidence that ties caller, Runtime identity, Gateway decision, and application activity together.
- Preserve default-deny: `github.com` is explicit; `www8.cao.go.jp` remains unlisted rather than receiving a host-specific deny rule.

**Non-Goals:**

- Changing `common` Terraform, Gateway policy, network attachment, Authz Extension, or its lifecycle.
- Creating a second Gateway, using anonymous HTTP, disabling TLS verification, changing Autopilot GKE, or claiming MCP E2E without its full execution chain.
- Destroying consumer or common resources after validation.

## Decisions

### Pass the full Gateway resource ID as an explicit Terraform input

Consumer configuration will expose a required `agent_gateway_id` variable and receive the exact value from `terraform -chdir=../common/terraform output -raw agent_gateway_id`. Validation will reject empty IDs and enforce the expected project, location, and Agent Gateway resource-name shape before deployment.

This preserves independent Terraform state and prevents remote-state coupling. Reading common remote state was considered, but would make the consumer implicitly depend on common backend access and obscure the handoff boundary. Recreating or importing the Gateway was rejected because common is the sole owner and project-level direction constraints make duplicate Gateway associations unsafe.

### Scope Terraform to consumer-owned resources

Terraform will restore only the Runtime, runtime identity, Artifact Registry, narrowly scoped IAM, and other validation resources required here. Static tests and an inspected plan will assert that no Gateway, VPC, Network Attachment, IAP Authz Extension, or AuthzPolicy resource appears under this root.

Maintaining the retired no-resource Terraform was considered, but it cannot exercise a Runtime configured to use common. Managing common resources here was rejected because it would conflict with common state and the documented ownership contract.

### Keep validation layers independent and correlate them in one report

The runner will begin an evidence window, invoke the Runtime using an authenticated caller, collect application logs and Gateway/IAP logs for the provided Gateway, and write a report containing identifiers, identities, outcomes, and raw non-secret records. The success case requires page-derived GitHub output and an allow decision. The negative case requires a fetch failure, no fabricated holiday list, and default-deny evidence for the Cabinet Office hostname. TLS inspection is checked through the common Gateway certificate/export and container trust configuration.

A response-only assertion was rejected because it cannot prove a destination was reached through the Gateway. Gateway log-only assertions were also rejected because they do not prove that the configured Runtime made the request.

### Treat MCP E2E as a separately gated extension

If the existing test suite includes Agent Registry/MCP coverage, its report will separately require Registry Service ID and interface resolution, Runtime caller identity, selected tool evidence, Gateway decision, endpoint authorization, and server-side MCP logs. Until all are present, the result remains a non-E2E boundary check.

This prevents an operator-side or network-only success from being reported as Agent Runtime MCP execution.

## Risks / Trade-offs

- [The common Gateway may have policy/configuration drift] → Read back its ID and non-secret configuration before tests, record it in evidence, and stop if it does not meet the stated validation contract.
- [A shared Gateway's logs contain other consumers' activity] → Query by Gateway plus the bounded test window and correlate application identifiers; report ambiguity rather than attributing unmatched events.
- [Runtime-to-Gateway direction exclusivity still blocks deployment] → Inventory active Runtime associations before apply, preserve existing resources, and report the actual association blocker without creating a second Gateway.
- [Gateway/IAP logs can arrive late] → Use a documented bounded collection retry/window and retain raw query results and timestamps.
- [The legacy checkout is retired] → Restore only the minimum consumer resources after a reviewed plan; keep historic evidence intact and leave common lifecycle outside the change.

## Migration Plan

1. Obtain and record the common Gateway output; inspect its live identity and relevant non-secret configuration.
2. Add consumer input validation, restore consumer-only Terraform and deployment wiring, and add plan/contract tests.
3. Run formatting, unit tests, image/contract checks, Terraform init/validate, and a reviewed plan confirming common resources are absent.
4. Apply only the consumer plan after approval, deploy the BYOC Runtime with the supplied Gateway ID, and run baseline, GitHub allow, Cabinet Office default-deny, and TLS trust checks.
5. Publish a dated evidence report. Roll back only consumer-owned Runtime/deployment configuration if needed; do not mutate or destroy common resources.
