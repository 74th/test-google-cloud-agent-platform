# Cloud Run validation evidence

Resource: `mcp-20260823-mcp-server-run` in `us-central1`.

Observed with `gcloud run services describe`:

- Ready condition: `True`; revision `mcp-20260823-mcp-server-run-00001-5w9`.
- Image: `us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server/mcp-server@sha256:1fcd5735921ed59fe63b6522395b11e2ec90928ef0786e42549ba2f0b3a0dea7`.
- Runtime service account: `mcp-20260823-mcp-server-run@nnyn-dev.iam.gserviceaccount.com`.
- Scaling annotations: `minScale=0`, `maxScale=3`.
- IAM policy: only the dedicated `mcp-20260823-invoker` service account has `roles/run.invoker`; no `allUsers` binding.

Protocol checks used the Cloud Run URL from Terraform output and an ID token minted as the dedicated invoker identity. `initialize`, `tools/list`, and `tools/call(validate_echo)` each returned HTTP 200 and the deterministic response. The request without a token returned HTTP 403.

The metric descriptor `run.googleapis.com/container/instance_count` was identified through the Cloud Monitoring API. It showed active instance count `0` during an idle observation window, and the Cloud Run startup log recorded `mcp-server-20260823-mcp-server listening on 0.0.0.0:8080` at `2026-08-23T09:18:31Z`. A cold-vs-warm latency comparison was not recorded because the operator-only token-mint prerequisite was intermittently denied; this item is SKIP, not PASS.
