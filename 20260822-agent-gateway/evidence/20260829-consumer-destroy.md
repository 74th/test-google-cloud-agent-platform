# Consumer cleanup evidence (2026-08-29)

The consumer Terraform workspace was destroyed after the common-egress live
validation, using the reviewed saved plan
`evidence/20260829-consumer-destroy-plan.txt` and the exact common Gateway
input `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`.

## Result

```text
Apply complete! Resources: 0 added, 0 changed, 12 destroyed.
```

Destroyed consumer-owned resources:

- Reasoning Engine `projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552`
- Artifact Registry repository `nnyn-dev/us-central1/agent-gateway-20260828`
- Artifact Registry repository IAM binding
- Runtime service account `agent-gateway-20260828-runtime@nnyn-dev.iam.gserviceaccount.com`
- Runtime `roles/aiplatform.user` and `roles/serviceusage.serviceUsageConsumer` bindings
- Runtime service-agent Artifact Registry reader binding
- Six Terraform-managed API service entries

The six APIs remained enabled because `disable_on_destroy=false`. The common
Gateway, VPC, subnet, Network Attachment, Authz Extension, AuthzPolicy, common
Registry endpoints, and Terraform-external Runtime consumers were not targets.

Post-destroy evidence:

- consumer Terraform state is empty;
- Runtime GET returns HTTP 404 `The ReasoningEngine does not exist`;
- Artifact Registry repository lookup returns NOT_FOUND;
- common Gateway read-back still returns `common-egress` and `AGENT_TO_ANYWHERE`.

The active account could not independently describe the deleted service
account because it lacks `iam.serviceAccounts.get`; no claim beyond the
successful Terraform destruction and empty state is made for that check.
