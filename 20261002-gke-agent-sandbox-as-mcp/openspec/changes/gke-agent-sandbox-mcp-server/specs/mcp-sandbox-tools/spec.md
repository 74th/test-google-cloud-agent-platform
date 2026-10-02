# Spec Delta

## Purpose

MCP クライアント（Coding Agent）がセッションの Sandbox をワークスペースとして操作するためのツールを、Codex のワークスペース操作ツールにできるだけ近い入出力で定める。あわせて、ワークスペースの状態を返す補助の REST API を定める。

## ADDED Requirements

### Requirement: MCP Server は Streamable HTTP で Codex 準拠のツールを提供する
MCP Server は Streamable HTTP transport で、`exec_command`、`write_stdin`、`apply_patch`、`view_image`、`delete_workspace` の 5 つのツールを提供しなければならない（SHALL）。すべてのツールは `session_id` と `user_email` を必須の入力として受け取り、binding を確認してから Sandbox を操作しなければならない（SHALL）。`exec_command`、`write_stdin`、`apply_patch`、`view_image` の入出力は、Codex の同名ツールに合わせなければならない（SHALL）。ただし、Codex でプロセスを指す `session_id` は `process_id` という名前にしなければならない（SHALL）。Codex の承認関連の入力（`sandbox_permissions`、`justification`、`prefix_rule`、`environment_id`）は提供してはならない（MUST NOT）。MCP Server はクラスタ内の通常 Deployment として 1 replica で動作しなければならない（SHALL）。

#### Scenario: ツール一覧を取得できる
- **WHEN** MCP クライアントが Streamable HTTP で接続し、ツール一覧を取得する
- **THEN** `exec_command`、`write_stdin`、`apply_patch`、`view_image`、`delete_workspace` の 5 つが返り、`workspace_status` は含まれない

#### Scenario: ツールを呼ぶと Sandbox が用意される
- **WHEN** 存在しない `session_id` でいずれかのワークスペース操作ツール（`delete_workspace` 以外）を呼び出す
- **THEN** Sandbox と PVC が作成されてから操作が行われる。Suspended のセッションなら Resume されてから操作が行われる

### Requirement: exec_command でコマンドを実行する
`exec_command` は `cmd`（必須）、`workdir`（既定 `/workspace`）、`tty`（既定 false）、`yield_time_ms`（既定 10000、250〜30000 に丸める）、`max_output_tokens`（既定 10000）、`shell`（既定は Sandbox イメージの既定シェル）、`login`（既定 true）を受け取らなければならない（SHALL）。コマンドが `yield_time_ms` 以内に終了した場合は、`output`、`wall_time_seconds`、`exit_code` を返さなければならない（SHALL）。終了しなかった場合は、その時点までの `output` と `process_id` を返し、プロセスはバックグラウンドで実行を続けなければならない（SHALL）。`tty` が false のとき、stdout と stderr は受け取った順に 1 つの `output` にまとめなければならない（SHALL）。コマンドが非ゼロで終了した場合も、ツール自体はエラーにせず `exit_code` で返さなければならない（SHALL）。

#### Scenario: すぐ終わるコマンド
- **WHEN** 新規セッションで `exec_command` により `echo hello` を実行する
- **THEN** `output` が `hello\n`、`exit_code` が 0 の結果が返り、`process_id` は含まれない

#### Scenario: 長いコマンドは process_id を返して継続する
- **WHEN** `yield_time_ms=1000` で `sleep 30; echo done` を実行する
- **THEN** 約 1 秒で `process_id` を含み `exit_code` を含まない結果が返り、Sandbox 内でプロセスが実行を続けている

#### Scenario: 非ゼロの終了コードを返す
- **WHEN** `exec_command` で `exit 3` を実行する
- **THEN** `exit_code` が 3 の結果が返る

### Requirement: write_stdin で実行中のプロセスに入力し出力を取得する
`write_stdin` は `process_id`（必須）、`chars`（既定は空）、`yield_time_ms`、`max_output_tokens` を受け取り、`exec_command` と同じ形式で結果を返さなければならない（SHALL）。`chars` が空の場合は、何も書き込まずに出力をポーリングしなければならない（SHALL）。前回の呼び出し以降の新しい出力だけを返し、プロセスが終了していれば `exit_code` を返さなければならない（SHALL）。`process_id` は、そのセッションで起動したプロセスのものでなければならない（SHALL）。存在しない、または別セッションの `process_id` はエラーにしなければならない（SHALL）。

#### Scenario: ポーリングで完了を受け取る
- **WHEN** `exec_command` が返した `process_id` に対し、プロセスの終了後に `chars` を空にして `write_stdin` を呼び出す
- **THEN** 残りの出力（`done\n`）と `exit_code` 0 が返る

#### Scenario: 対話的なプロセスに入力する
- **WHEN** `exec_command` で `tty=true` として `read x; echo got:$x` を実行し、返った `process_id` に `chars="abc\n"` で `write_stdin` を呼び出す
- **THEN** `output` に `got:abc` が含まれ、`exit_code` が 0 で返る

#### Scenario: 別セッションの process_id は使えない
- **WHEN** セッション A で得た `process_id` を、セッション B の `session_id` と `user_email` で `write_stdin` に渡す
- **THEN** エラーが返り、セッション A のプロセスには何も書き込まれない

### Requirement: プロセスの出力と実行時間を制限する
`output` は `max_output_tokens` に相当する量で切り詰め、切り詰める前の量を `original_token_count` で返さなければならない（SHALL）。`max_output_tokens` の上限は環境変数で設定できなければならない（SHALL）。読み出されていない出力をバッファする量にも上限を設けなければならない（SHALL）。プロセスが環境変数で設定した最大実行時間を超えた場合は停止しなければならない（SHALL）。セッションあたりの同時実行プロセス数にも上限を設け、上限を超える `exec_command` はエラーにしなければならない（SHALL）。

#### Scenario: 巨大な出力は切り詰められる
- **WHEN** 上限を超える出力を生成するコマンドを実行する
- **THEN** 返される `output` は上限以下で、`original_token_count` が上限より大きい

#### Scenario: 最大実行時間を超えたプロセスは停止される
- **WHEN** 最大実行時間を短く設定して、それより長い `sleep` を実行する
- **THEN** 最大実行時間の経過後にプロセスが停止され、次の `write_stdin` で終了したことが分かる

### Requirement: apply_patch でファイルを編集する
`apply_patch` は Codex のパッチ形式（`*** Begin Patch` 〜 `*** End Patch`。`Add File`、`Delete File`、`Update File`、`Move to` を含む）の文字列を `input` で受け取り、Sandbox 内で適用しなければならない（SHALL）。相対パスは `/workspace` を基準に解決しなければならない（SHALL）。成功した場合は、追加・更新・削除したファイルの一覧を返さなければならない（SHALL）。パッチの形式が不正な場合、または文脈が一致しない場合は、エラーを返し、ファイルを部分的に変更してはならない（MUST NOT）。ファイルは Sandbox の非 root ユーザーの権限で書き込まなければならない（SHALL）。

#### Scenario: ファイルを追加・更新・削除する
- **WHEN** `Add File: a.txt`、既存の `b.txt` への `Update File`、既存の `c.txt` への `Delete File` を含むパッチを適用する
- **THEN** 3 つの変更を示す一覧が返り、`exec_command` で確認すると `a.txt` が作成され、`b.txt` が更新され、`c.txt` が削除されている

#### Scenario: 文脈が一致しないパッチは失敗する
- **WHEN** 存在しない行を文脈に含む `Update File` のパッチを適用する
- **THEN** エラーが返り、パッチに含まれるどのファイルも変更されていない

### Requirement: view_image で画像を取得する
`view_image` は `path` を受け取り、Sandbox 内の画像ファイルを MCP の画像コンテンツとして返さなければならない（SHALL）。相対パスは `/workspace` を基準に解決しなければならない（SHALL）。PNG、JPEG、GIF、WebP 以外のファイル、存在しないファイル、環境変数で設定したサイズ上限を超えるファイルは、エラーにしなければならない（SHALL）。

#### Scenario: 画像を取得できる
- **WHEN** Sandbox 内に作成した PNG ファイルのパスで `view_image` を呼び出す
- **THEN** MIME タイプが `image/png` の画像コンテンツが返り、内容は元のファイルと一致する

#### Scenario: 画像でないファイルはエラーになる
- **WHEN** テキストファイルのパスで `view_image` を呼び出す
- **THEN** エラーが返る

### Requirement: delete_workspace でワークスペースを削除する
`delete_workspace` は、binding を確認したうえで、そのセッションの実行中のプロセスを停止し、Sandbox、SandboxClaim、PVC を削除しなければならない（SHALL）。存在しないセッションに対しては、Sandbox を作成せずに「存在しない」ことを返さなければならない（SHALL）。削除後に同じ `session_id` でツールを呼び出した場合は、新しい空のワークスペースが作られなければならない（SHALL）。

#### Scenario: 削除後は新規ワークスペースになる
- **WHEN** `/workspace/test.txt` を作成したセッションで `delete_workspace` を呼び出し、その後同じ `session_id` で `exec_command` により `ls /workspace/test.txt` を実行する
- **THEN** 削除後に SandboxClaim、Sandbox、PVC が残っておらず、再実行時は新しい PVC が作成されてファイルは存在しない

### Requirement: ワークスペースの状態を REST API で返す
ワークスペースの状態は MCP ツールではなく、MCP Server と同じプロセスの REST API（`POST /api/v1/workspace-status`）で提供しなければならない（SHALL）。リクエストの body で `session_id` と `user_email` を受け取り、binding を確認しなければならない（SHALL）。メールアドレスを URL のパスやクエリで受け取ってはならない（MUST NOT）。応答では、Sandbox の有無、Running / Suspended、ワークスペースの有無、実行中のプロセス数、最終 activity の時刻、Suspend 予定時刻、削除予定時刻を JSON で返さなければならない（SHALL）。この API は Sandbox の作成や Resume を行ってはならない（MUST NOT）。Pod IP、ノード名、内部のリソース名など Kubernetes の内部情報を返してはならない（MUST NOT）。binding が一致しない場合は 403 を返さなければならない（SHALL）。

#### Scenario: Suspended のセッションの状態
- **WHEN** Suspended のセッションについて REST API を呼び出す
- **THEN** 状態が Suspended、ワークスペースありの JSON が返り、Sandbox は Resume されない

#### Scenario: 存在しないセッションの状態
- **WHEN** 存在しない `session_id` で REST API を呼び出す
- **THEN** Sandbox とワークスペースがないことを示す JSON が返り、Sandbox は作成されない

#### Scenario: binding 不一致は 403
- **WHEN** 既存セッションに対し、別の `user_email` で REST API を呼び出す
- **THEN** 403 が返り、応答にメールアドレスは含まれない
