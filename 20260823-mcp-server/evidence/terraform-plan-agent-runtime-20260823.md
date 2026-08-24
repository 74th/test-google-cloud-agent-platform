# Agent Runtime create-only plan summary

Date: 2026-08-23  
Command: `terraform -chdir=terraform plan -var=enable_gke=false -out=/tmp/mcp-20260823-create-only.tfplan`

The reviewed plan contains 30 resource creates, one post-create Registry
endpoint data read, zero updates, and zero destroys. All managed resource
names and labels use the `20260823-mcp-server` experiment scope. The plan does
not address the existing `20260822` gateway/runtime, the `autopilot` cluster,
the default VPC, or unrelated Registry entries.

The plan intentionally uses placeholder digest-shaped values until the
immutable MCP and Agent Runtime images are built and pushed. Apply must use the
reviewed real digests before creating Cloud Run or Agent Runtime revisions.

GKE is disabled in this phase. Its Registry service and HTTPS front door are
conditional and additionally require an operator-authorized hostname, DNS,
trusted certificate, and exact authentication audience.
