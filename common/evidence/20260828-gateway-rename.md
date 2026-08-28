# 2026-08-28 shared Gateway rename

- Requested name: `common-egress`.
- Before the replacement, live API and common Terraform state contained only
  `common-agent-gateway-egress`.
- Terraform plan: `/tmp/common-agent-gateway-replace.tfplan`.
- The initial in-place rename attempt exposed a `google-nightly` provider
  inconsistent-result error and did not change the live name.
- The explicit replacement plan contained exactly one Gateway delete and one
  Gateway create; VPC, subnet, Network Attachment, and API state were no-op.
- Approved replacement apply result: `1 added, 0 changed, 1 destroyed`.
- Final live Gateway:
  `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`.
- Final `networkConfig.egress.networkAttachment`:
  `https://www.googleapis.com/compute/v1/projects/nnyn-dev/regions/us-central1/networkAttachments/common-agent-gateway-attachment`.
- Final Network Attachment resolves to
  `common-agent-gateway-subnet`; the subnet resolves to
  `common-agent-gateway-vpc` and uses `10.243.0.0/28`.
- Terraform output and state now use `common-egress`; the post-apply plan has
  no changes.
