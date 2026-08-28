# Consumer plan scope (2026-08-28, reconciled)

Command:

```text
terraform -chdir=terraform plan -input=false -no-color -out=/tmp/consumer-20260828.tfplan \
  -var=agent_gateway_id=projects/nnyn-dev/locations/us-central1/agentGateways/common-egress \
  -var=runtime_image_uri=us-central1-docker.pkg.dev/nnyn-dev/agent-gateway-20260828/claude-agent-gateway@sha256:<reviewed-digest>
terraform -chdir=terraform show -json /tmp/consumer-20260828.tfplan
END```text

The initial approved plan contained 12 consumer-side creates and one data read,
with zero updates and zero destroys. The follow-up reconciliation restored the
consumer-owned `google_vertex_ai_reasoning_engine.runtime` declaration using
the pinned `google-nightly` provider, then imported the already-deployed
Runtime:

```text
terraform -chdir=terraform import \
  google_vertex_ai_reasoning_engine.runtime \
  projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552
```

With the common handoff and immutable image digest supplied, the reconciled
plan reports `0 to add, 0 to change, 0 to destroy`. The endpoint IAM member
derives its principal from the Runtime's computed effective identity. The
Runtime block contains
`deployment_spec.agent_gateway_config.agent_to_anywhere_config.agent_gateway`
with the full common Gateway ID. The plan contains no
`google_network_services_agent_gateway`, VPC, subnet, Network Attachment,
`Authz Extension`, `AuthzPolicy`, or common-resource import action.

The Runtime's initial deployment used the atomic v1 REST payload before the
nightly provider support was confirmed; it is now represented in consumer
Terraform state without a replacement or update. No destroy was run.
