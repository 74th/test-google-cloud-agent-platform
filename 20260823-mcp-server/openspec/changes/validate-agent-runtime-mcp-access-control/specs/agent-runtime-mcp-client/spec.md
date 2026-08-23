## Purpose

Agent Runtime上のClaude Agent SDKが、Agent Registryで管理されたremote MCP Serverを安全に発見し、agent自身のidentityでToolを選択・実行できることを保証する。

## ADDED Requirements

### Requirement: Hosted Claude agent uses remote MCP tools
Agent Runtime上のClaude agentは、Agent Registryから解決したremote MCP ServerをClaude Agent SDKの利用可能Toolとして構成し、operatorの代理呼び出しに依存せずToolを選択・実行しなければならない（SHALL）。

#### Scenario: Cloud Run Toolの選択と実行
- **WHEN** 利用者がCloud Run側の検証Toolを必要とするpromptでAgent Runtimeを呼び出す
- **THEN** Claude agentはRegistry管理されたCloud Run MCP Toolを呼び出し、そのTool結果に基づく応答を返す

#### Scenario: GKE Toolの選択と実行
- **WHEN** 利用者がGKE側の検証Toolを必要とするpromptでAgent Runtimeを呼び出す
- **THEN** Claude agentはRegistry管理されたGKE MCP Toolを呼び出し、そのTool結果に基づく応答を返す

### Requirement: Runtime identity based authentication
remote MCP接続に必要なcredentialはAgent Runtimeの実効identityから短時間credentialとして取得されなければならず、固定token、Service Account key、またはAnthropic API keyをMCP認証用途に使用してはならない（MUST NOT）。

#### Scenario: Agent Runtime identityでの接続
- **WHEN** Agent Runtimeが許可されたCloud RunまたはGKE MCP endpointへ接続する
- **THEN** endpointはAgent Runtimeに割り当てられたidentityを検証し、許可された呼び出しだけをToolへ配送する

### Requirement: Explicit integration failure
agentはRegistry discovery、接続先validation、credential取得、endpoint認可、MCP protocol、Tool実行の失敗を区別し、Toolが成功していない場合に成功結果を生成してはならない（MUST NOT）。

#### Scenario: MCP接続失敗
- **WHEN** remote MCP Toolがdiscovery失敗、認可拒否、または到達不能によって実行できない
- **THEN** agent invocationは該当段階を示す失敗を返し、モデルの事前知識でTool結果を補完しない
