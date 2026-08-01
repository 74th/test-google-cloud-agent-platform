# Claude Agent SDK × Google Cloud Session Store 検証

Claude Agent SDK のプロセスを終了した後、Google Cloud Agent Platform Session Store から Claude セッション ID と会話イベントを取得し、同一ローカル環境で `resume` できるかを検証する最小サンプルです。

> Session Store は Claude のローカルトランスクリプトを代替しません。`resume` は同じマシン・同じ `CLAUDE_SESSION_CWD` で保持された Claude SDK のトランスクリプトを必要とします。Claude のワークスペース永続化は対象外です。

## 前提条件

- Python 3.11 以上と [uv](https://docs.astral.sh/uv/)
- Session Store を利用できる Google Cloud プロジェクト、リージョン、空の Agent Engine
- Claude Haiku 4.5 を利用可能にした Google Cloud プロジェクトと、Agent Engine / Vertex AI User 権限を持つ Google Cloud 認証（例: `gcloud auth application-default login`）

`.env.example` を `.env` としてコピーして設定します。CLI はプロジェクト直下の `.env` を自動読込します。認証情報ファイルやアクセストークンは `.env` に書き込まず、ADC で管理してください。

```bash
export GOOGLE_CLOUD_PROJECT=nnyn-dev
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_CLOUD_AGENT_ENGINE=projects/nnyn-dev/locations/us-central1/reasoningEngines/your-agent-engine-id
export SESSION_STORE_USER_ID=verification-user
export VERTEX_AI_LOCATION=us-east5
export CLAUDE_SESSION_CWD="$PWD"
```

Claude API キーは不要です。SDK は `CLAUDE_CODE_USE_VERTEX=1`、`ANTHROPIC_VERTEX_PROJECT_ID=nnyn-dev`、`CLOUD_ML_REGION=us-east5` を実行時に設定し、Vertex AI の `claude-haiku-4-5@20251001` を使用します。ADC は `gcloud auth application-default login` で構成してください。

Agent Engine は Google Cloud の Agent Engine 作成画面または SDK で、コードを配備せずに作成できます。既存リソースを指定する場合は、上記に完全なリソース名を設定してください。

### Agent Engine を Terraform で作成する

未作成の場合は、[terraform](terraform/) の定義で Vertex AI API と Session Store 専用の空の Agent Engine を作成できます。この構成にはエージェントコード、サービスアカウント、秘密情報、IAM 変更を含めません。次のコマンドは人間が実行してください（Codex は `apply` を実行しません）。

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
terraform output -raw agent_engine_name
```

最後の出力をプロジェクトルートの `.env` へ設定します。

```dotenv
GOOGLE_CLOUD_AGENT_ENGINE=projects/nnyn-dev/locations/us-central1/reasoningEngines/...
```

不要になった検証用 Agent Engine は、内容を確認したうえで同じディレクトリから `terraform destroy` で削除できます。`aiplatform.googleapis.com` は destroy 後も有効のままです。

## 実行

依存関係を同期して初回プロセスを実行します。

```bash
uv run claude-session-store-verify start
```

出力は JSON です。`session_name`（完全な Session Store リソース名）を控え、必ずプロセスを終了します。別シェルの別プロセスで次を実行します。

```bash
uv run claude-session-store-verify resume "projects/.../sessions/..."
```

`success: true` は `session_created`、`events_appended`、`events_retrieved`、`claude_resumed`、`nonce_matched` がすべて真であることを表します。`resume` の成功は、Session Store から初回イベントと Claude セッション ID を取得でき、Claude SDK がローカルのトランスクリプトを用いて nonce を再現できたことを意味します。

失敗時にも JSON の `error_stage`、`error_type`、`error_message` を確認してください。とくにローカルトランスクリプトがない場合、`events_retrieved` は真のまま `claude_resumed` が偽になります。

## テスト

```bash
uv run --extra test pytest -q
```

テストは API のテストダブルで、イベントの保存順序、管理情報の復元、設定不足、未存在・不完全セッション、保存失敗、ローカルトランスクリプト欠落、二段階の nonce 一致、および JSON 成功条件を検証します。

### Vertex AI を使う 3 ターン統合テスト

次のテストは実際に Claude Agent SDK と Vertex AI の Claude Haiku 4.5 を呼び出すため、通常のテストから除外されます。初回応答、同一 session ID を指定した 1 回目の再開、2 回目の再開の計 3 ターンで、nonce の一致と session ID の継続を確認します。実行には ADC と `.env` の設定が必要で、モデル利用料金が発生します。

```bash
RUN_LIVE_VERTEX_TESTS=1 uv run --extra test pytest -m live_vertex -q
```

同じコマンドでは、custom MCP ツール `ask_human` のライブテストも実行する。初回の tool/human 会話を Session Store へ保存してクラウドから取得し、取得した Claude session ID で tool/human 会話を再開する。Claude が各ターンでツールへ質問を渡すこと、ツールが返した人間役の回答を最終応答に使うこと、Session Store に保存した初回会話と session ID を復元できることを検証する。自動テストでは固定の人間役回答を使うため、実際の担当者へ入力を求める対話テストではない。

この tool/human / Session Store ライブテストは、実行後に次の 3 ファイルを `tmp/<claude-session-id>/` へ出力する。`tmp/` は Git 管理対象外であり、会話・tool call・人間役回答を含むため共有しないこと。

- `session-store-events.json`: Session Store から取得した生イベント
- `claude-transcript.jsonl`: Claude SDK がローカルに保存したトランスクリプト
- `claude-final-responses.json`: tool call 後に Claude へ明示的に報告を求めて受け取った最終実行結果
- `comparison.json`: 各ファイル名、session ID、Session Store のイベント数

Session Store 側には、アダプターが保存する初回プロンプト・最終応答・管理情報に加え、`event_type: tool_call` と `event_type: tool_result` の JSON 管理イベントが含まれる。後者にはツール名、入力（質問）、結果（人間役回答）が保存される。Claude のローカルトランスクリプトは SDK 詳細イベントを含む。両者は同一形式ではないため、内容を 1 対 1 に一致させる比較ではなく、同じ Claude session ID と各 tool interaction の対応関係を確認するために用いる。

Claude Code のローカルトランスクリプトは、in-process MCP tool の結果を返した直後を `No response requested.` という合成メッセージで記録する場合がある。テストはその後に同一 session ID へ実行結果の報告を明示的に依頼し、SDK の `ResultMessage.result` から受け取った Claude の最終応答を `claude-final-responses.json` に保存する。初回の最終応答は Session Store の assistant イベントにも保存される。

## 検証記録

| 項目 | 値 |
| --- | --- |
| 実装日 | 2026-08-01 |
| 固定依存関係 | `claude-agent-sdk==0.1.35`, `google-cloud-aiplatform==1.153.1`, `mcp==1.29.0` |
| Claude モデル | Vertex AI `claude-haiku-4-5@20251001` |
| 自動テスト | `uv run --extra test pytest -q` |
| Claude SDK 3 ターン統合テスト | 2026-08-01 に成功（初回 1 回と同一 session ID での再開 2 回。全応答で nonce が一致） |
| Claude SDK tool call / 人間質問 / Session Store 統合テスト | 2026-08-01 に成功（初回 tool/human 会話を Session Store に保存・取得し、同じ Claude session ID で tool/human 会話を再開） |
| 実クラウド二段階検証 | 2026-08-01 に成功（`session_created`、`events_appended`、`events_retrieved`、`claude_resumed`、`nonce_matched` はすべて `true`） |

実測は `claude-agent-sdk==0.1.35`、`google-cloud-aiplatform==1.153.1` で行いました。認証値・nonce・会話内容・セッション ID は記録しません。再検証時は、実行日、SDK バージョン、各 JSON の真偽だけをこの表へ追記してください。

### 今回確認できたこと

2026-08-01 に、`nnyn-dev` プロジェクトで Terraform 作成後の Agent Engine を使い、初回実行と別プロセスの再開を順に実行した。いずれも JSON の `success` が `true` となった。

| 確認項目 | 実測結果 |
| --- | --- |
| Vertex AI 認証 | Anthropic API キーを使わず、ADC と Vertex AI の Claude Haiku 4.5 で Claude Agent SDK を実行できた。 |
| Session Store への保存 | `start` が Session Store セッションを作成し、初回プロンプト、Claude 応答、Claude セッション ID と nonce を含む管理情報を保存できた。 |
| プロセスをまたぐ取得 | 初回コマンドの終了後、別の `resume` プロセスから指定 Session Store のイベントと Claude セッション ID を取得できた。 |
| Claude ネイティブ再開 | 取得した Claude セッション ID を `resume` に渡し、以前の会話を参照する応答を得られた。 |
| 継続判定 | 再開時の応答が保存済み nonce と完全一致した。 |

この結果から、**同一ローカル実行環境**では、Google Cloud Agent Platform Session Store に保存した対応情報を使って Claude Agent SDK のプロセス間再開を検証できた。

一方で、以下はこの検証の対象外であり、成功を意味しない。

- 別マシンや消去済みのローカルトランスクリプトからの Claude ネイティブ再開
- Session Store のイベントだけから Claude の内部トランスクリプトを復元すること
- Claude のワークスペースや作業ディレクトリの永続化
- 同時更新、長期保持、暗号化方針、可用性などの本番運用要件

## クリーンアップと注意事項

- このサンプルが作成した Session Store セッションは Google Cloud コンソール、または Sessions API から明示的に削除してください。
- 検証専用に作成した Agent Engine は、不要になった時点でコンソールまたは SDK の `agent_engine.delete(force=True)` により削除してください。子セッションも削除されます。
- Agent Engine、Session Store、モデル利用には課金が発生することがあります。事前に予算とクォータを確認してください。
- 最小権限の IAM を使い、API キー、ADC 資格情報、環境変数値をイベント・ログ・ソースコードに書き込まないでください。
