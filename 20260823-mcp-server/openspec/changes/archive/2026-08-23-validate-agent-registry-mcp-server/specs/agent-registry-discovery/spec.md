## Purpose

Agent Registry を MCP Server と Tool の信頼できるメタデータ検索面として利用し、ホスティング先とは独立して登録内容を発見・検証できるようにする。

## ADDED Requirements

### Requirement: Versioned Tool specification
リポジトリは MCP Server の Tool 名、説明、および input schema と一致する、検証可能で version 管理された Agent Registry 登録用 Tool specification を提供しなければならない（SHALL）。

#### Scenario: Runtime と登録 spec の整合性
- **WHEN** 検証処理が稼働中 Server の `tools/list` と登録用 Tool specification を比較する
- **THEN** Tool 名、説明、および input schema に差分が存在しない

### Requirement: Hosting-specific registry entries
Agent Registry は Cloud Run と GKE Standard の各 MCP Server を区別できる表示名、説明、interface URL、および protocol binding で別々に登録しなければならない（SHALL）。

#### Scenario: Cloud Run Server の登録
- **WHEN** Cloud Run 用の登録処理を実行する
- **THEN** Agent Registry は Cloud Run の MCP interface と Tool specification を持つ一意な Server entry を返す

#### Scenario: GKE Server の登録
- **WHEN** GKE 用の登録処理を実行する
- **THEN** Agent Registry は GKE の MCP interface と Tool specification を持つ一意な Server entry を返す

### Requirement: Server and Tool discovery
認証済みの検証 client は Agent Registry を検索し、登録した各 Server と検証用 Tool を発見できなければならない（SHALL）。検索結果は実行先 endpoint と Tool schema を特定するのに十分な情報を含まなければならない（MUST）。

#### Scenario: Tool 名による発見
- **WHEN** client が登録済み検証 Tool に一致する条件で Agent Registry を検索する
- **THEN** 検索結果は Cloud Run と GKE の該当 Server、および一致する Tool metadata を返す

### Requirement: Discovery and execution distinction
検証は Agent Registry による discovery と、発見された MCP endpoint に対する Tool execution を別の操作として扱い、それぞれの結果を記録しなければならない（SHALL）。

#### Scenario: 発見後の直接実行
- **WHEN** client が Registry から Server の interface を発見して Tool を実行する
- **THEN** Registry 検索の成功と対象 MCP Server の実行成功が独立した証跡として記録される

