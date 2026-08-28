# common-egress 移行 apply/read-back 証跡（2026-08-28）

## Apply

対象は consumer Terraform state のみです。事前に保存した plan は `scripts/check_scope.py` で確認し、共有 Gateway、common VPC、subnet、Network Attachment、既存 GKE、他 Runtime の action がないことを確認しました。

```text
terraform plan -refresh-only -no-color -detailed-exitcode <reviewed immutable image variables>
No changes. Your infrastructure still matches the configuration.

python3 scripts/check_scope.py <saved plan JSON>
scope guard: PASS: consumer-only actions

terraform apply -input=false -auto-approve /tmp/mcp-20260828-common-egress.tfplan
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

この apply は既に構築済みの consumer resources の reviewed plan を再確認した no-op です。`common-egress` の etag は read-back 前後で `dJ8MLgd6POm1aIr09nFj08MG6sYT3_r_kQdbTE7p57E` のままでした。

## Runtime read-back

Agent Runtime API GET の実測値:

| 項目 | 実測値 |
| --- | --- |
| Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528` |
| display name | `mcp-20260823-runtime` |
| identity type | `AGENT_IDENTITY` |
| effective identity | `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528` |
| Runtime image | `us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server-agent/agent-runtime@sha256:48c06e1bd9b248d702d6491b21dbe52a01adfdada0400725341042a9617feb23` |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |

Cloud Run の ready revision は platform-specific child digest `a3aa4c33c0ada331b6c3be1e272b142857dea6cdf8e9073a0086d1a8a6545d28` を報告しました。Terraform と reviewed image input は multi-platform image index `bff4bbfa89bf27f04d9db044bc426de317c0f901e75d85367182eb304069de6e` を固定しており、実行プラットフォームが child manifest を選択するため、mutable tag ではありません。

## Registry / IAM read-back

consumer-owned Service は次の5件を live list で確認しました。Cloud Run MCP Server は `mcp-20260823-cloud-run`、Agent Registry、Vertex regional/global、IAM Credentials は `mcp-20260823-mcp-server-*` です。MCP Server interface は Cloud Run の HTTPS `/mcp`、`JSONRPC`、`validate_echo` spec と一致しました。旧 `20260822 managed` service/endpoint は Terraform state/data source にありません。

Runtime principal の `roles/iap.egressor` は4 control-plane endpoint と1 Cloud Run MCP Server の resource scopeだけです。Cloud Run `roles/run.invoker`、caller Service Account の ID-token mint、Artifact Registry repository pull、Registry viewer、Vertex user は [IAM reconciliation](iam-reconciliation-20260828.md) に責務別に記録しています。

Apply/read-back は invocationではないため `correlation_id=N/A (plan/apply/read-back)` です。E2E correlation IDを取得できなかったRuntime probeは別証跡で FAIL としています。
