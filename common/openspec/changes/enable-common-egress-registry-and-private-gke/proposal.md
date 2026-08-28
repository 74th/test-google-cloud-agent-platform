## Why

Agent Runtime の Agent Registry discovery が共有 `common-egress` Gateway の `default_denied` で拒否され、consumer-owned の private GKE MCP endpoint へ進めない。`240.0.0.2:443` の意味と拒否レイヤーを live evidence で確定し、共有 Gateway の default-deny と所有境界を維持したまま、必要最小限の許可と private route を検証可能にする必要がある。

## What Changes

- `common-egress` が Registry discovery の CONNECT をどの endpoint、identity、rule、authorization layer として評価したかを、live API と Gateway log から再現可能かつ非機密の証跡として記録する。
- Registry/control-plane endpoint と consumer-owned GKE MCP endpoint に対する allow を、host、port、protocol、principal、resource、適用範囲で明示し、default-deny を維持する。必要な common-owned policy が判明した場合だけ、事前 plan/read-back と承認境界を経て最小変更を適用する。
- Gateway ID、etag、direction、protocol、Registry 関係、Network Attachment、DNS peering、および allow/deny rule を変更前後に read-back し、consumer state が common-owned resource を管理しないことを検証する。
- Gateway 許可後に `gke.mcp-20260823.internal` の private DNS、`10.240.0.5` の Internal HTTPS Load Balancer、TLS、healthy backend、ClusterIP、Pod 実行までを Agent Runtime から correlation ID で追跡する。
- Registry discovery、Gateway allow、endpoint authorization、MCP server-side execution を独立した判定層として扱い、途中の成功だけで Agent Runtime E2E を PASS にしない。
- anonymous/public fallback、既存 Autopilot GKE の変更、秘密情報の証跡化、consumer state への common resource import、および `terraform destroy` を禁止する。安全な最小変更で完了できない場合は、正確な enforcement layer、owner、approval boundary、再試行条件を blocker として返す。

## Capabilities

### New Capabilities

- `shared-agent-gateway-consumer-access`: 共有 Agent Gateway の default-deny を保った consumer endpoint 許可、common/consumer 所有境界、private GKE 経路、および Agent Runtime E2E の層別証跡契約を規定する。

### Modified Capabilities

- なし。

## Impact

- `common`: `common-egress` の read-only 診断、必要な場合の Terraform 管理された Gateway authorization/policy、静的検査、preflight、read-back、validation runbook、および非機密 evidence。
- Consumer `20260823-mcp-server`: Runtime principal、Agent Registry Service `mcp-20260823-gke`、private DNS/Internal HTTPS Load Balancer、および Pod execution log を検証入力・証跡として参照するが、consumer Terraform の common resource 所有権は変更しない。
- Google Cloud `nnyn-dev/us-central1`: Agent Gateway、Network Services/Network Security、Agent Registry、Vertex AI Agent Runtime、IAM/IAP、Cloud DNS、Internal Application Load Balancer、および GKE logging の read API。書き込みは evidence で必要性を確定した common-owned resource の最小変更に限定する。
- 既存の `common-egress` 利用者: policy 変更前に consumer inventory と plan を確認し、既存 allow を後退させない。OpenSpec 提案作成自体はクラウドリソースを変更しない。
