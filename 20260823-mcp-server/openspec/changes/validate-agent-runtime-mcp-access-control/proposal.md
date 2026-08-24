## Why

前回の検証は、operatorまたはGKE内の検証PodがAgent RegistryからURLを取得してMCP Serverへ直接接続したものであり、Agent Runtime上のClaude Agent SDKからの利用、接続先の集中管理、endpoint認可のend-to-end動作を証明していない。Agent Registryを接続先のsource of truthとして利用し、Agent Runtime identityに基づく認可を通してCloud RunとGKEのToolを実行できるかを検証する必要がある。

## What Changes

- Agent Runtime上でClaude Agent SDKを実行する専用agentを構築し、operatorの代わりにagent自身がMCP Toolを選択・呼び出す経路を追加する。
- Agent RuntimeはCloud Run／GKEのendpoint URLを設定へ直書きせず、許可されたAgent Registry Service IDからinterface、protocol binding、Tool metadataを解決する。
- Registryから取得した接続情報をproject、location、Service ID、protocol、host、Tool schemaのallowlistと照合し、未登録、想定外、または不整合な接続先を実行前に拒否する。
- 検証専用Agent GatewayをAgent Runtimeへ関連付け、Agent Registry endpointとAgent Runtimeのeffective identityに対する`roles/iap.egressor`を実際の接続許可として使用する。未登録またはbindingのない接続先はdefault denyで拒否する。
- Cloud RunではAgent Runtime identityに最小限のInvoker権限を付与し、有効なidentityの成功と未認証・未許可identityの拒否を確認する。
- GKE MCP ServerにはAgent Runtimeから到達可能な認証付きHTTPS入口を設け、専用identityだけを許可する。既存のcluster-local経路はruntime単体確認用として分離する。
- Claude Agent SDKがRegistryで管理されたCloud RunとGKEの各MCP Serverを明示的に利用し、Tool結果とserver側log／request correlationの両方で実行先を証明する。
- Registry entryの接続先更新がAgent Runtime imageの再buildやURL設定変更なしで反映され、削除・無効化されたentryをagentが利用できないことを検証する。
- discovery、接続先検証、token取得、endpoint認可、MCP protocol、ClaudeによるTool選択を別々の証跡として記録し、推測によるPASSを禁止する。

## Capabilities

### New Capabilities

- `agent-runtime-mcp-client`: Agent Runtime上のClaude Agent SDKがRegistry管理されたremote MCP Serverを解決し、認証付きでToolを選択・実行する振る舞い。
- `mcp-connection-governance`: Registry entryとAgent Gateway／IAP認可を接続許可のsource of truthとし、登録変更、削除、不正URL、認可失敗を安全に扱う接続先管理とaccess-control境界。

### Modified Capabilities

- `agent-registry-discovery`: operatorによる検索だけでなく、Agent RuntimeがRegistryを実行時の接続先source of truthとして利用する要件を追加する。
- `mcp-server-runtime`: Cloud RunとGKEの両endpointがAgent Runtime identityを認可し、未認証・未許可呼び出しをTool実行前に拒否する要件へ拡張する。
- `terraform-poc-environment`: Agent Runtime、runtime identity、GKEの認証付きHTTPS入口、証跡用IAMと安全なteardownを検証環境へ追加する。
- `verification-evidence`: Agent Runtime／Claude Agent SDKから両hosting先へのE2E成功、接続先管理、negative authorization testを必須matrixへ追加する。

## Impact

- Agent Runtime用のcustom container、Claude Agent SDK adapter、Registry resolver、認証header生成、runtime invocation testを追加する。
- Cloud Run IAM、Agent Runtime effective identity、専用Agent Gateway、Agent Registry endpoint IAM、IAP認可、およびGKEのHTTPS公開・認証関連resourceをTerraformまたは検証済みの補助commandで管理する。
- GKEはAgent Runtimeから到達可能にするため、Gateway／Ingress、Load Balancer、TLS、DNS、認証機構の追加コストと攻撃面が発生する。
- `scripts/registry.sh`、Tool spec整合性検査、Kubernetes manifest、runbook、README、validation report、sanitized evidenceを更新する。
- 既存Autopilot cluster、既存Agent Runtime、および他のRegistry entryは再利用・変更しない。Googleのプロジェクト単位Gateway排他制約により、既存`agw-20260822-egress`はTerraformで管理せず参照だけ行い、検証用の重複Gatewayは作成しない。
