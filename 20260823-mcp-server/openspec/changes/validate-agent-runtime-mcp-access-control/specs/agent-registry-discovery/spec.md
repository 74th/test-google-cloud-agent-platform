## ADDED Requirements

### Requirement: Agent Runtime resolves hosting-specific entries
Agent Runtimeは専用identityを用いて許可されたCloud RunおよびGKEのRegistry entryを取得し、各entryのinterfaceとTool metadataをremote MCP client構成へ渡さなければならない（SHALL）。

#### Scenario: Runtimeによる両entryのdiscovery
- **WHEN** Agent RuntimeがMCP接続設定を構築する
- **THEN** runtimeは許可されたCloud RunとGKEのService IDを個別に取得し、URLを設定へ直書きせず各interfaceを識別する

### Requirement: Runtime discovery uses least privilege
Agent Runtime identityには対象Registry entryの取得に必要な最小限の権限だけを付与し、Service登録、更新、削除権限を付与してはならない（MUST NOT）。

#### Scenario: RuntimeからのRegistry変更拒否
- **WHEN** Agent Runtime identityでRegistry Serviceの更新または削除を試みる
- **THEN** 操作は拒否され、既存entryは変更されない
