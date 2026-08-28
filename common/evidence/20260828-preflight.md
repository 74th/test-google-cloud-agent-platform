# 2026-08-28 preflight and migration evidence

## Tool and identity context

- Terraform: `1.13.1`
- Google Cloud CLI: `581.0.0`
- Active account: `74th.pc@gmail.com`
- Target project/region: `nnyn-dev/us-central1`
- Existing state workspaces: both `default`

## Live network inventory before cleanup

- `default`: auto subnet VPC; `us-central1/default` is `10.128.0.0/20`
- `mcp-20260823-mcp-server-vpc`: custom VPC with `10.240.0.0/20`; owned by the 20260823 state and approved for destruction
- Selected common PSC interface CIDR: `10.243.0.0/28`; no overlap was present in the inspected `us-central1` subnet inventory

## Provider schema evidence

- `google-nightly` version: `2026.4.8-7.27.0`
- `google_network_services_agent_gateway.network_config.egress.network_attachment`: required string URI inside an egress block
- `google_compute_network_attachment.connection_preference`: required; accepted values include `ACCEPT_AUTOMATIC`
- `google_compute_network_attachment.subnetworks`: required list

## Existing states and reviewed plans

### 20260822-agent-gateway

- Normal plan: no changes
- Destroy plan: `0 add, 0 change, 21 destroy`
- Includes Agent Gateway `agw-20260822-egress`, Reasoning Engine `7911550761069182976`, six Registry Services, IAP endpoint binding, authorization policy/extension, Artifact Registry repository/IAM, and API-enablement state.
- Saved plan: `/tmp/common-migration-20260822-destroy.tfplan`

### 20260823-mcp-server

- Normal plan before destroy: `0 add, 2 change, 10 destroy` because defaults no longer matched deployed image digests and `enable_gke=false`; it was not applied.
- Destroy plan: `0 add, 0 change, 43 destroy`
- Includes Reasoning Engine `826966334750326784`, GKE Standard cluster/node pool and dedicated VPC, Cloud Run, two Artifact Registry repositories, Registry Services, service accounts, IAM, and API-enablement state.
- Saved plan: `/tmp/common-migration-20260823-destroy.tfplan`

## Cleanup result

- User explicitly approved Terraform destroy on 2026-08-28.
- `20260823-mcp-server`: success, `43 destroyed`; state is empty.
- `20260822-agent-gateway`: partial success. Runtime `7911550761069182976`, Registry Services, IAM, authz policy/extension, and Artifact Registry were deleted. Agent Gateway deletion returned HTTP 400 because two external Runtime consumers remain:
  - `2779698985680502784`, display name `20260822-agent-gateway-claude-identity`, image tag `20260822-r3`
  - `382095134059134976`, display name `20260822-agent-gateway-claude-local-webfetch`, image tag `20260822-r4`
- These consumers are not in either inspected Terraform state. Their direct deletion is not part of the saved Terraform plans and remains a separate authorization boundary.
- Remaining 20260822 state contains the Agent Gateway plus API-enablement entries. The APIs use `disable_on_destroy=false` and remain enabled.

## Deployment boundary

- No consumer Terraform apply was run.
- Common Terraform plan `/tmp/common-agent-gateway.tfplan` passed format, validate, static boundary tests, and JSON inspection with `8 add, 0 change, 0 destroy`.
- The eight creates are four API-enablement state entries plus the dedicated VPC, `/28` subnet, Network Attachment, and VPC-connected Agent Gateway.
- Common Terraform had not been applied at the time of this record.
- OpenSpec validation is planning evidence; it is not live VPC-connectivity evidence.
