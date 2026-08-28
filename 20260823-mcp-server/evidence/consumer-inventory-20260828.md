# Consumer resource ownership inventory（2026-08-28）

| 範囲 | live/current result | 分類 |
| --- | --- | --- |
| consumer Terraform state | 初期状態では resource list なし | consumer-owned、これから構築 |
| consumer Agent Registry service/MCP server | `gcloud agent-registry services/mcp-servers list` は該当時点で空 | consumer-owned、legacy entry へ fallback しない |
| Cloud Run | `us-central1` の service list は空 | consumer-owned、これから構築 |
| GKE | `asia-northeast1/autopilot` のみ。network/subnetwork は `default/default` | unrelated、変更・削除禁止 |
| shared Gateway/VPC/attachment | common state と live inventory に存在 | common-owned、consumer の state/cleanup 外 |
| project IAM | relevant binding は既存の別 consumer が保持。consumer の endpoint IAM は未作成 | unrelated または consumer-owned を分離 |

この inventory は「存在しない consumer resource」を成功とみなすものではなく、移行前の空の consumer state と、変更禁止の既存環境を区別するためのもの。Registry discovery、Gateway egress、endpoint authorization、MCP execution は後続タスクで独立に検証する。
