# mcp-server-runtime Specification

## Purpose

Cloud Run と GKE Standard の異なる実行環境で、同一コンテナの最小 MCP Server が相互運用可能かつ安全に呼び出せることを検証可能にする。

## Requirements

### Requirement: Streamable HTTP MCP interface
MCP Server は `0.0.0.0` の実行環境指定ポートで待ち受け、`/mcp` において MCP Streamable HTTP の初期化、Tool 一覧取得、および Tool 呼び出しを提供しなければならない（SHALL）。

#### Scenario: Tool の一覧と実行
- **WHEN** 認証済みクライアントが MCP セッションを初期化し、`tools/list` と検証用 Tool の呼び出しを行う
- **THEN** Server は宣言済み Tool の schema と、入力に対応する決定的な JSON 応答を返す

### Requirement: Portable stateless container
MCP Server は同一の version 固定コンテナ image を Cloud Run と GKE Standard の両方で実行でき、リクエスト間の正しさを process-local state または永続ローカルファイルに依存してはならない（MUST NOT）。

#### Scenario: 二つの実行環境で同じ Tool を呼び出す
- **WHEN** 同一 image digest を Cloud Run と GKE Standard にデプロイして同じ Tool 入力を送信する
- **THEN** 両環境は同じ Tool 定義に従う正常応答を返す

### Requirement: Runtime access control
Cloud Run は unauthenticated invocation を拒否し、明示的に Invoker 権限を持つ検証 identity の呼び出しだけを受け入れなければならない（SHALL）。GKE の公開方式と到達可能範囲は明示され、不必要な Internet 公開を行ってはならない（MUST NOT）。

#### Scenario: Cloud Run の認証済み呼び出し
- **WHEN** Invoker 権限を持つ identity が有効な ID token を付けて MCP endpoint を呼び出す
- **THEN** Cloud Run は MCP リクエストを Server に配送する

#### Scenario: Cloud Run の未認証拒否
- **WHEN** client が ID token なしで IAM 保護された Cloud Run endpoint を呼び出す
- **THEN** 呼び出しは MCP Tool が実行される前に拒否される

### Requirement: Cloud Run scale-to-zero compatibility
Cloud Run service は minimum instance 数を 0 とし、idle 後の最初の MCP 呼び出しでも初期化から Tool 実行までを完了できなければならない（SHALL）。

#### Scenario: Idle 後の Tool 実行
- **WHEN** Cloud Run が稼働 instance を持たないことを確認した後、認証済み client が MCP Tool を呼び出す
- **THEN** service は instance を起動し、許容時間内に MCP 初期化と Tool 応答を完了する
