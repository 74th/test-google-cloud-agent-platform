# Spec Delta

## Purpose

Sandbox 内で 1 回だけ実行されて終了するコンテナを提供する。このコンテナは GCS 上の JSONL を入力として受け取り、Vertex AI 上の Claude Haiku 4.5 で Claude Agent SDK を実行し、応答を追記した JSONL を出力する。

## ADDED Requirements

### Requirement: 環境変数で指定された GCS の JSONL を入出力に使う
コンテナは、入力 JSONL の GCS URI と出力 JSONL の GCS URI を環境変数から受け取らなければならない（SHALL）。入力の各行は 1 ターン分のリクエストを表す JSON オブジェクトとする。出力は、入力の各行を保ったまま、未応答の行に応答フィールドを追加した JSONL でなければならない（SHALL）。

#### Scenario: 未応答の行に応答が追加される
- **WHEN** 入力 JSONL の最後の行に `prompt` があり、`response` がない
- **THEN** 出力 JSONL のその行に `response`、Claude のセッション ID、実行メタデータが追加され、それ以前の行は変更されない

#### Scenario: 必須の環境変数が不足している
- **WHEN** 入力 URI または出力 URI の環境変数が設定されていない
- **THEN** コンテナは Claude を呼び出さずに非ゼロの終了コードで終了し、不足している変数名を標準エラーに出力する

### Requirement: Vertex AI 上の Claude Haiku 4.5 を使う
コンテナは Claude Agent SDK のモデルとして、Vertex AI 経由の `claude-haiku-4-5@20251001` を使わなければならない（SHALL）。認証には Workload Identity を使い、API キーや鍵ファイルを使ってはならない（MUST NOT）。

#### Scenario: Vertex AI 経由で応答が返る
- **WHEN** 有効なプロンプトを 1 件入力する
- **THEN** Vertex AI の Claude Haiku 4.5 から応答が得られ、出力行のメタデータにモデル名 `claude-haiku-4-5@20251001` が記録される

### Requirement: Claude のセッション状態と作業ファイルを永続ワークスペースに保存する
コンテナは、Claude Agent SDK のセッション記録と、エージェントが作業するカレントディレクトリを永続ワークスペース（`/workspace` 配下）に置かなければならない（SHALL）。入力行に前回の Claude セッション ID が含まれていれば、そのセッションを再開して処理しなければならない（SHALL）。

#### Scenario: 前回のセッションを再開する
- **WHEN** 同じワークスペースで、前回の Claude セッション ID を持つ行を入力する
- **THEN** エージェントは前回の会話内容を踏まえて応答する

### Requirement: Web アクセスとファイル操作のツールを使えるようにする
エージェントは、URL の内容を取得するツールとワークスペース内のファイル操作ツールを使えなければならない（SHALL）。URL の取得に失敗した場合、エージェントは取得できなかったことを応答で示さなければならない（SHALL）。ネットワークの失敗を理由にコンテナ自体を異常終了させてはならない（MUST NOT）。

#### Scenario: 取得できない URL の要約を依頼する
- **WHEN** 通信が遮断されている URL の要約を依頼する
- **THEN** 応答には取得できなかったことが示され、コンテナは正常終了して出力 JSONL を書き戻す

### Requirement: 実行環境の証跡を記録する
コンテナは、各実行の出力メタデータに、Pod 名、Pod UID、ノード名、カーネル情報（`/proc/version` など gVisor であることを判別できる値）、実行開始前のワークスペースのファイル一覧を記録しなければならない（SHALL）。

#### Scenario: gVisor 上で実行されたことが分かる
- **WHEN** Sandbox で 1 回実行が完了する
- **THEN** 出力メタデータのカーネル情報から gVisor 上で実行されたことを判別できる

### Requirement: 処理後に終了する
コンテナは入力を処理して出力を書き戻したら、自分で終了しなければならない（SHALL）。成功時は終了コード 0、Claude 呼び出しや GCS 入出力が失敗した場合は非ゼロで終了しなければならない（SHALL）。

#### Scenario: 正常に処理すると終了コード 0 で終了する
- **WHEN** 出力 JSONL の書き戻しが成功する
- **THEN** コンテナは終了コード 0 で終了する
