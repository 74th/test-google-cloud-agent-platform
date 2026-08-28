# Shared Agent Gateway runbook

## Fixed scope

- Google Cloud project: `nnyn-dev`
- Region: `us-central1`
- Terraform root/state: `common/terraform`, local backend `terraform.tfstate`
- Main resources: dedicated VPC, `/28` PSC interface subnet, Network Attachment, VPC-connected Agent Gateway
- Consumer resources such as Agent Runtime, Agent Registry Service, MCP server, GKE, Cloud Run, Artifact Registry, endpoint IAM, and authorization policy are out of scope.

The Network Attachment is mandatory: provider schema exposes Agent Gateway VPC connectivity as `network_config.egress.network_attachment`. Merely creating a VPC and subnet does not connect the Gateway.

## Verified API and provider surface

Verified on 2026-08-28 using Terraform `1.13.1`, Google provider `7.45.0`, Google Cloud CLI `581.0.0`, and `google-nightly` `2026.4.8-7.27.0`.

- Agent Gateway CLI: <https://cloud.google.com/sdk/gcloud/reference/network-services/agent-gateways>
- Network Attachment resource: <https://registry.terraform.io/providers/hashicorp/google/7.45.0/docs/resources/compute_network_attachment>
- Agent Gateway resource is currently supplied by the pinned `hashicorp/google-nightly` provider. `terraform providers schema -json` confirmed:
  - `network_config.egress.network_attachment` is required when the egress network block is present.
  - `google_managed.governed_access_path` accepts `AGENT_TO_ANYWHERE`.
  - `protocols` accepts `MCP`.
- `google_compute_network_attachment` requires `connection_preference` and `subnetworks`; this configuration uses `ACCEPT_AUTOMATIC` on a dedicated `/28` subnet.

Re-run the schema checks before changing the pinned versions. Do not guess replacement fields.

## Static validation

```bash
terraform -chdir=terraform init
./scripts/validate.sh
RUN_TERRAFORM_PLAN=1 ./scripts/validate.sh
terraform -chdir=terraform show -json /tmp/common-agent-gateway.tfplan | jq '.resource_changes[] | {address, actions: .change.actions}'
```

Expected planned infrastructure is four main resources plus API-enablement state:

- `google_compute_network.agent_gateway`
- `google_compute_subnetwork.agent_gateway`
- `google_compute_network_attachment.agent_gateway`
- `google_network_services_agent_gateway.shared`

## Existing experiment cleanup

Always use explicit directories and saved plans. Never run a broad command from the repository root.

```bash
terraform -chdir=../20260822-agent-gateway/terraform workspace show
terraform -chdir=../20260822-agent-gateway/terraform state list
terraform -chdir=../20260822-agent-gateway/terraform plan -destroy -input=false -out=/tmp/common-migration-20260822-destroy.tfplan

terraform -chdir=../20260823-mcp-server/terraform workspace show
terraform -chdir=../20260823-mcp-server/terraform state list
terraform -chdir=../20260823-mcp-server/terraform plan -destroy -input=false -out=/tmp/common-migration-20260823-destroy.tfplan
```

Apply only the reviewed binary plan. Delete consumer runtimes before the Gateway owner state. After each apply, confirm `terraform state list` and live resources.

The 2026-08-28 migration found two older `20260822-agent-gateway` Runtime consumers outside both Terraform states. Gateway deletion must remain blocked until those external resources are separately authorized and deleted or detached.

## Common deployment

Before plan, confirm the old Gateway is absent and `10.243.0.0/28` remains unused.

```bash
gcloud network-services agent-gateways list --project=nnyn-dev --location=us-central1
gcloud compute networks subnets list --project=nnyn-dev --regions=us-central1
terraform -chdir=terraform plan -input=false -out=/tmp/common-agent-gateway.tfplan
terraform -chdir=terraform show /tmp/common-agent-gateway.tfplan
```

Apply only after the exact saved common plan is reviewed and approved:

```bash
terraform -chdir=terraform apply -input=false /tmp/common-agent-gateway.tfplan
terraform -chdir=terraform output -json
```

## Live verification

```bash
gcloud network-services agent-gateways describe common-agent-gateway-egress --project=nnyn-dev --location=us-central1 --format=json
gcloud compute network-attachments describe common-agent-gateway-attachment --project=nnyn-dev --region=us-central1 --format=json
gcloud compute networks describe common-agent-gateway-vpc --project=nnyn-dev --format=json
gcloud compute networks subnets describe common-agent-gateway-subnet --project=nnyn-dev --region=us-central1 --format=json
```

Pass only if the Gateway's `networkConfig.egress.networkAttachment` equals the common Network Attachment URI and that attachment resolves to the common subnet/VPC.

## Rollback and cleanup

Prefer correcting the common configuration and applying from the same state. Before destroying common, inventory every Runtime consumer and review a saved destroy plan. Never destroy common while any Runtime references its Gateway.
