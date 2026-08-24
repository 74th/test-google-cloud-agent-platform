# Isolated backend validation evidence

Date: 2026-08-24  
Project: `nnyn-dev`  
Image digest: `sha256:952427685e4c97f00e54a4d5e93748f28b1bbec8fb3412fe6b1b6f08946de9ca`

## Cloud Run

- Service `mcp-20260823-mcp-server-run` was created with the immutable digest.
- The service has no `allUsers` binding in the Terraform configuration.
- A request without a credential returned HTTP 403 before MCP Tool execution.
- Dedicated caller ID-token verification could not be completed because the
  operator account is denied `iam.serviceAccounts.getAccessToken` for the
  caller SA even during a target-only temporary operator prerequisite. This is
  recorded as incomplete, not PASS.

## GKE cluster-local regression

- Dedicated Standard cluster: `mcp-20260823-mcp-server-gke`
- Dedicated VPC/subnet and secondary ranges were created; existing Autopilot
  cluster and default VPC were not targeted.
- Kubernetes Deployment and validation Job use the exact image digest above.
- Deployment rollout completed successfully.
- Validation Job passed `initialize`, `tools/list`, valid `tools/call`, and
  invalid-input handling.
- Service is `ClusterIP` with cluster IP `10.242.2.230`, port 80, and no
  external IP. The Pod image ID equals the reviewed digest.
- A first Job attempt hit a startup DNS race using the short service name. The
  failed experiment-owned Job was removed and recreated with the fully
  qualified in-cluster service DNS name; the retry passed.

This evidence proves backend/runtime-only behavior. It does not prove Agent
Runtime, Agent Gateway, GKE HTTPS/IAP, or Claude E2E behavior.

## Repeat verification

On 2026-08-24 the experiment namespace was reconciled with the same reviewed
image digest. The Deployment rolled out successfully and a fresh validation
Job again passed `initialize`, `tools/list`, valid `tools/call`, and
invalid-input handling. The Service remained `ClusterIP` with no external IP.

A direct unauthenticated POST to the Cloud Run `/mcp` endpoint returned HTTP
403. An operator ID token could not be minted with an audience because the
active account is not a Service Account; no authorized positive call is
claimed from this repeat check.
