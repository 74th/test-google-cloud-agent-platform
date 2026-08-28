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

The scope guard is mandatory for every saved plan:

```bash
terraform -chdir=terraform show -json /tmp/common-agent-gateway.tfplan > /tmp/common-agent-gateway.tfplan.json
python3 scripts/check_scope.py /tmp/common-agent-gateway.tfplan.json
```

It rejects consumer resources, protected Gateway/VPC/subnet/Network
Attachment deletion or replacement, wrong project or region, broad identity
values, and public or credential-like values. The fixture tests in
`tests/test_terraform.sh` must continue to show both accepted and rejected
cases.

Expected planned infrastructure is four main resources plus API-enablement state:

- `google_compute_network.agent_gateway`
- `google_compute_subnetwork.agent_gateway`
- `google_compute_network_attachment.agent_gateway`
- `google_network_services_agent_gateway.shared`

## Read-only access diagnosis

Before proposing an allow tuple, capture the Gateway export/schema, common and
consumer state lists, private DNS relation, Registry metadata, Runtime
association, and selected Gateway log fields. Use the bounded helper for one
probe; it generates a UUID, keeps credentials in memory only, and emits only
sanitized fields:

```bash
python3 scripts/gateway_probe.py \
  --runtime-project=776113568960 \
  --runtime-location=us-central1 \
  --runtime-id=2332905838663958528 \
  --registry-service=mcp-20260823-gke \
  --target=gke
```

The Runtime response, Gateway request, Registry lookup, and endpoint result
must be joined by the same correlation ID. If the Runtime does not return the
ID, record the bounded time/resource/method join as provisional and do not
classify an internal destination by its IP alone. A `default_denied` result
must identify the actual enforcing resource and rule before any policy change
is proposed. An unavailable supported policy relation is a blocker.

## Plan and approval gate

For any supported, exact, observed policy tuple, perform the following in the
common root:

1. Read back Gateway ID, etag, access direction, protocol, Registry scope,
   Network Attachment, VPC/subnet relation, and all existing consumers.
2. Run formatting, provider initialization, validation, static tests, and a
   refresh-only plan. Explain drift before producing a normal saved plan.
3. Review the saved plan with the tuple's logical name, exact host, port,
   protocol, principal/resource scope, enforcement owner, existing-consumer
   impact, and tuple-only rollback.
4. Run the scope guard and confirm there is no protected replacement/deletion,
   unrelated IAM/API change, public frontend, or broadening beyond observed
   requests.
5. Present the saved plan and pre-change read-back to the resource owner. No
   apply is permitted until explicit human approval is recorded.

If the provider cannot represent the proven enforcement owner, do not perform
an out-of-band mutation. Record the API version, resource fields, etag
precondition, drift behavior, and rollback as a separate approval request.

## Post-change validation and rollback

After an approved apply, capture the Gateway ID/etag/direction/protocol,
Registry scope, Network Attachment, VPC/subnet, and existing-rule read-back.
Run one approved positive probe and adjacent unauthorized identity, host, port,
and protocol probes. The Gateway log must identify the expected allow rule for
the positive request and a deny rule for each out-of-scope request.

Retry Registry discovery one observed destination at a time. Discovery success
does not prove private routing, endpoint authorization, or MCP execution. For
the GKE path, independently verify private DNS, the internal HTTPS frontend,
TLS hostname/trust, backend health, endpoint authorization, ClusterIP, and Pod
execution using one correlation ID. In-cluster smoke is only a backend
baseline. Do not use certificate verification bypass, anonymous access, public
frontends, or unencrypted transport.

Rollback removes only the newly approved exact tuple through the same reviewed
common state, with an etag/read-back check and deny regression. It never removes
or transfers ownership of the Gateway, VPC, subnet, Network Attachment, or
consumer resources.

## Existing experiment cleanup boundary

Cleanup of an existing experiment is outside this runbook and requires separate
human approval after an owner inventory. This runbook does not provide a
destructive command or authorize cleanup of consumer runtimes, the Gateway, or
the common network. The 2026-08-28 migration found two older
`20260822-agent-gateway` Runtime consumers outside both Terraform states; the
shared Gateway owner must keep cleanup blocked until those external resources
are separately authorized and deleted or detached.

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
gcloud network-services agent-gateways describe common-egress --project=nnyn-dev --location=us-central1 --format=json
gcloud compute network-attachments describe common-agent-gateway-attachment --project=nnyn-dev --region=us-central1 --format=json
gcloud compute networks describe common-agent-gateway-vpc --project=nnyn-dev --format=json
gcloud compute networks subnets describe common-agent-gateway-subnet --project=nnyn-dev --region=us-central1 --format=json
```

Pass only if the Gateway's `networkConfig.egress.networkAttachment` equals the common Network Attachment URI and that attachment resolves to the common subnet/VPC.

## Rollback

Prefer correcting the common configuration and applying from the same state.
Rollback is limited to reviewed, newly-added exact policy tuples. It must not
remove the Gateway, VPC, subnet, Network Attachment, or consumer resources.
