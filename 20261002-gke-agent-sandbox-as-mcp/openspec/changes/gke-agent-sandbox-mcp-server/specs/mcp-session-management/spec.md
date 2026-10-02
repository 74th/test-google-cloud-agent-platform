# Spec Delta

## Purpose

MCP クライアントから渡される `session_id` と `user_email` をもとに、セッションごとに専用の Sandbox を割り当て、別ユーザーによる再利用を防ぎ、生のメールアドレスを外部に残さずに Sandbox 内へ渡す。

## ADDED Requirements

### Requirement: session_id を検証する
MCP Server は `session_id` の文字種と長さに上限を設け、条件を満たさない値を受け取った場合は Kubernetes を操作せずにエラーを返さなければならない（SHALL）。`user_email` もメールアドレスとして妥当な形式でなければエラーを返さなければならない（SHALL）。

#### Scenario: 不正な session_id はエラーになる
- **WHEN** 許可されていない文字を含む、または上限より長い `session_id` でツールを呼び出す
- **THEN** バリデーションエラーが返り、Sandbox や SandboxClaim は作成されない

### Requirement: session_id から決定的なリソース名を作る
SandboxClaim の名前は `session_id` の SHA-256 から作った DNS-1123 準拠の名前（`sandbox-session-` + 16 進 20 桁）でなければならない（SHALL）。同じ `session_id` からは常に同じ名前が得られなければならない（SHALL）。メールアドレスをリソース名に使ってはならない（MUST NOT）。

#### Scenario: 同じ session_id から同じ名前ができる
- **WHEN** 同じ `session_id` で名前を 2 回生成する
- **THEN** 2 回とも同じ `sandbox-session-<20 桁>` の名前になる

#### Scenario: MCP Server 再起動後も同じセッションに再接続できる
- **WHEN** セッションで Sandbox を作成したあと MCP Server を再起動し、同じ `session_id` と `user_email` で `exec_command` を呼び出す
- **THEN** 新しい Sandbox は作られず、既存の SandboxClaim とワークスペースが使われる

### Requirement: session_id と user_email を 1 対 1 で binding する
新しいセッションを作成するとき、MCP Server は `user_email` の HMAC-SHA256（鍵は Kubernetes Secret から読み込む）を SandboxClaim の annotation に保存しなければならない（SHALL）。既存セッションへのアクセスでは、渡された `user_email` の HMAC と annotation の値を比較し、一致しなければエラーを返して Sandbox を操作してはならない（MUST NOT）。binding は MCP Server の再起動後も検証できなければならない（SHALL）。

#### Scenario: 別のメールアドレスでのアクセスは拒否される
- **WHEN** `session_id=abc123, user_email=alice@example.com` でセッションを作成したあと、`session_id=abc123, user_email=bob@example.com` でツールを呼び出す
- **THEN** binding 不一致のエラーが返り、コマンドの実行やファイルの変更は行われず、Sandbox の状態も変わらない

#### Scenario: 再起動後も binding が検証される
- **WHEN** MCP Server を再起動したあと、別の `user_email` で既存の `session_id` にアクセスする
- **THEN** binding 不一致のエラーが返る

### Requirement: Sandbox 内で USER_EMAIL を参照できる
Sandbox 内のプロセスは、環境変数 `USER_EMAIL` でセッションの `user_email` を取得できなければならない（SHALL）。`exec_command` で実行したコマンドからも、Sandbox 内で起動した別のプロセスからも取得できなければならない（SHALL）。Suspend と Resume をはさんでも値が変わってはならない（MUST NOT）。

#### Scenario: exec_command から USER_EMAIL が見える
- **WHEN** `user_email=alice@example.com` のセッションで `exec_command` により `echo $USER_EMAIL` を実行する
- **THEN** `output` が `alice@example.com` になる

#### Scenario: Python プロセスから USER_EMAIL が見える
- **WHEN** `exec_command` で `python /opt/tools/internal_tool.py`（`os.environ["USER_EMAIL"]` を表示する）を実行する
- **THEN** `output` がセッションの `user_email` になる

### Requirement: 生のメールアドレスを外部に残さない
MCP Server は、生のメールアドレスを Kubernetes の label、annotation、リソース名、metric label、tracing attribute、通常のアプリケーションログに保存・出力してはならない（MUST NOT）。単純な SHA-256 も保存してはならない（MUST NOT）。ログでユーザーを識別する必要がある場合は、HMAC から作った短い識別子（例: `user_hash=ff8d9819fc0e`）だけを出力しなければならない（SHALL）。Sandbox Pod 内の `USER_EMAIL` には生のメールアドレスを渡してよい。

#### Scenario: ログとリソースにメールアドレスが含まれない
- **WHEN** 複数のツール呼び出し（エラーになる呼び出しを含む）を行ったあと、MCP Server のログ、REST API の応答、Namespace 内の SandboxClaim / Sandbox / PVC / Pod の label・annotation を検索する
- **THEN** 使用したメールアドレスの文字列はどこにも含まれない
