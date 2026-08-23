## Purpose

Agent RegistryをMCP接続先の管理面として利用し、Agent Runtimeが許可された登録情報だけを採用するとともに、実行先endpointの独立した認可を必須にする。

## ADDED Requirements

### Requirement: Registry is the connection source of truth
Agent RuntimeはCloud RunおよびGKE MCP Serverの接続先を許可されたAgent Registry Service IDから解決しなければならず、runtime image、prompt、または利用者入力に含まれる任意のendpoint URLを接続先として採用してはならない（MUST NOT）。

#### Scenario: 登録済み接続先の解決
- **WHEN** agentが許可されたMCP Serverを利用する
- **THEN** 接続先URL、protocol binding、およびTool metadataは該当するRegistry entryから取得される

#### Scenario: 任意URLの拒否
- **WHEN** promptまたはrequestがRegistry allowlistに存在しないMCP URLの利用を要求する
- **THEN** agentはnetwork requestを送信する前に接続先を拒否する

### Requirement: Registry metadata validation
Registryから取得した接続情報は、期待するproject、location、Service ID、HTTPS要件、許可host、protocol binding、およびTool schemaと照合され、検証に失敗したentryを使用してはならない（MUST NOT）。

#### Scenario: 改変または不整合entryの拒否
- **WHEN** Registry entryのhost、protocol、またはTool schemaが期待する値と一致しない
- **THEN** Agent Runtimeはendpoint credentialを生成せず、validation errorを記録する

### Requirement: Registry lifecycle controls runtime availability
Registry entryの更新、無効化、または削除はruntime imageの再buildやURL設定変更なしで次回の接続解決へ反映されなければならない（SHALL）。

#### Scenario: 接続先更新の反映
- **WHEN** 許可されたService IDのinterfaceが検証済みの新endpointへ更新される
- **THEN** 次回のagent invocationはRegistryから新しい接続先を解決する

#### Scenario: Entry削除後の利用拒否
- **WHEN** 許可されていたRegistry entryが削除または無効化される
- **THEN** agentは以前のURLへfallbackせず、discovery failureとしてTool実行を中止する

### Requirement: Discovery and endpoint authorization remain independent
Registry entryを検索できることはendpoint実行権限を付与してはならず（MUST NOT）、Cloud RunとGKEはそれぞれの認可境界でcaller identityを検証しなければならない（SHALL）。

#### Scenario: Registry閲覧者のendpoint拒否
- **WHEN** Registryを検索できるがendpoint実行権限を持たないidentityがMCP endpointを呼び出す
- **THEN** Registry検索は成功してもTool実行はendpointで拒否される

### Requirement: Agent Gateway enforces registered endpoint access
Agent Runtimeの外向きMCP通信はdefault denyのAgent Gatewayを通過し、許可されたAgent Registry endpointに対してAgent Runtimeのeffective identityが明示的なegress権限を持つ場合だけ転送されなければならない（SHALL）。

#### Scenario: 登録・許可済みendpointへの通信
- **WHEN** Agent RuntimeがRegistryに登録され、runtime identityへegress権限が付与されたCloud RunまたはGKE endpointへ接続する
- **THEN** Agent Gatewayは通信を許可し、endpoint側の認可処理へrequestを転送する

#### Scenario: 未登録または未許可endpointのdefault deny
- **WHEN** Agent RuntimeがRegistry endpointとして登録されていない、またはruntime identityにegress権限がないhostへ接続する
- **THEN** Agent Gatewayはendpointへ到達する前に通信を拒否し、deny判定を記録する
