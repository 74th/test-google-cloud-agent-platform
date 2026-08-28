# consumer-only teardown inventory（2026-08-28）

これは後日、人間が対象を確認してから実行するための inventory です。destroy plan の作成・確認だけを行い、apply は実行していません。

## 含める候補

- `mcp-20260823-mcp-server` / `mcp-20260823-mcp-server-agent` Artifact Registry repository
- `mcp-20260823-mcp-server-run` Cloud Run と専用 Service Account/IAM
- `mcp-20260823-runtime` Agent Runtime と consumer Registry Service/endpoint/MCP Server/IAM
- consumer が将来有効化した場合だけ、その `mcp-20260823` GKE/VPC/Kubernetes resources

## 明示的に除外

- `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
- `common-agent-gateway-vpc`、subnet、Network Attachment
- 既存 `asia-northeast1` Autopilot GKE、`default` VPC、および既存 Runtime consumer
- consumer 外の Registry Service/endpoint、既存 IAM、旧 Gateway

## 確認結果

```text
terraform plan -destroy -input=false <reviewed immutable image variables>
python3 scripts/check_scope.py <saved destroy plan JSON>
scope guard: PASS: consumer-only actions
```

plan は後日の人間レビュー用に保持し、明示承認なしに `terraform apply` しません。`terraform destroy` も実行していません。
