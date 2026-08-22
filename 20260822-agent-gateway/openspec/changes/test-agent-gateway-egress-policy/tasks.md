## 1. プロジェクト基盤

- [ ] 1.1 `20260801-agent-hosting` から必要な構成だけを移植して Python 3.12／uv、Docker、`agent_service/`、`scripts/`、`terraform/`、`tests/` の雛形を作り、不要な時刻表資産がなく期待するファイル群が存在することを確認する
- [ ] 1.2 Claude Agent SDK、Agent Platform クライアント、FastAPI、Google 認証、およびテスト用依存関係を固定し、`uv sync --extra test --extra deploy` が成功することを確認する
- [ ] 1.3 値を含まない `.env.example` と固有のリソース命名規則を定義し、リポジトリ検索で `agent-hosting-20260801` と `claude-agent-runtime` が実リソース設定に残っていないことを確認する

## 2. BYOC エージェント

- [ ] 2.1 Agent Platform の `query`／`stream_query` カスタムコンテナ契約を実装し、入力検証、空回答、SDK 例外、ストリーム応答を単体テストで確認する
- [ ] 2.2 Claude Agent SDK を `claude-haiku-4-5@20251001`、Vertex AI 認証、必要最小限の Web 取得ツールで構成し、設定テストでモデル、ツール許可、API キー非依存を確認する
- [ ] 2.3 指定 URL の実取得、取得失敗時の明示、事前知識による補完禁止をシステムプロンプトへ組み込み、GitHub 成功と取得拒否を模擬したテストで回答契約を確認する
- [ ] 2.4 `0.0.0.0:8080` で非 root 実行するコンテナを作成し、イメージのビルドとローカルのヘルス／reasoning-engine 契約テストが成功することを確認する

## 3. Google Cloud と Agent Gateway

- [ ] 3.1 実装時点の公式 Agent Gateway API、Terraform Google provider、`gcloud` の対応状況を確認して採用する構築経路と固定バージョンを記録し、利用するリソーススキーマまたは API リクエストの契約テストを追加する
- [ ] 3.2 Terraform で必要 API、`20260822-agent-gateway` 固有の Artifact Registry、実行サービスアカウント、ラベル、出力値を定義し、`terraform fmt -check` と `terraform validate` を通す
- [ ] 3.3 実行サービスアカウントへ `roles/aiplatform.user`、Agent Platform サービスエージェントへ専用リポジトリの reader、Gateway に必須な用途別 IAM のみを付与し、Terraform テストで基本ロール、Anthropic API キー、Secret Manager 依存がないことを確認する
- [ ] 3.4 Agent Gateway と外向き通信ポリシーを既定拒否かつ `github.com` 許可で定義し、静的テストで既定値、許可ホスト、および `www8.cao.go.jp` の allow/deny 個別ルール不在を確認する
- [ ] 3.5 Claude Haiku 4.5 の推論に必要な Google 管理サービス経路だけを特定して利用可能にし、構成出力の検査で Web 許可リストが不必要に拡張されていないことを確認する

## 4. デプロイと操作ツール

- [ ] 4.1 コンテナを専用 Artifact Registry へ build/push するスクリプトを実装し、dry-run またはコマンド生成テストでプロジェクト、リージョン、イメージ URI が固有設定を指すことを確認する
- [ ] 4.2 固有表示名、専用サービスアカウント、Agent Gateway、`nnyn-dev/us-central1`、Vertex `nnyn-dev/global` を指定して BYOC エージェントを作成するスクリプトを実装し、設定生成テストで全環境変数と関連付けを確認する
- [ ] 4.3 認証付き呼び出し、エージェント削除、Gateway ポリシー出力、Cloud Logging 証跡収集の各コマンドを実装し、モックテストで完全リソース名、ページング、失敗終了コード、秘密情報の非出力を確認する
- [ ] 4.4 2 個の指定プロンプトを順に実行して入力、応答、終了状態、ポリシー、宛先判断ログをタイムスタンプ付きディレクトリへ保存する検証ランナーを実装し、fixture を用いたテストで合否判定と証跡ファイルを確認する

## 5. 文書化とローカル検証

- [ ] 5.1 README に前提条件、Model Garden 有効化、`PROJECT_ID=nnyn-dev`、`LOCATION=us-central1`、`VERTEX_PROJECT_ID=nnyn-dev`、`VERTEX_REGION=global`、構築、デプロイ、検証、証跡の読み方を記載し、文書中のコマンドと環境変数をテストで検査する
- [ ] 5.2 README にエージェント削除後の `terraform destroy`、残存リソース確認、失敗時の切り分けを記載し、クリーンアップ対象が固有名／ラベルに限定されることをレビューする
- [ ] 5.3 全 Python テスト、Terraform 静的テスト、コンテナ契約テストを一括実行し、ローカル CI 相当のコマンドが成功することを確認する

## 6. ライブ検証

- [ ] 6.1 `nnyn-dev` に Terraform を適用して Gateway と関連リソースを新規作成し、出力された名前が既存構成と重複せず、デプロイ済みポリシーが既定拒否、`github.com` allow、`www8.cao.go.jp` 未列挙であることを保存済み設定から確認する
- [ ] 6.2 コンテナを push して BYOC エージェントを Agent Gateway 配下へデプロイし、Claude Haiku 4.5 を用いた基本呼び出しが成功することを実行ログで確認する
- [ ] 6.3 「https://github.com/74th の内容を要約して」を実行し、ページ内容に基づく日本語要約、成功状態、および `github.com` の allow 証跡を保存して確認する
- [ ] 6.4 指定された 2027 年祝日プロンプトを実行し、ページ取得失敗を明記して祝日一覧を補完しない応答、失敗状態、および `www8.cao.go.jp` の default-deny 証跡を保存して確認する
- [ ] 6.5 検証結果を README から参照できる日付付きレポートにまとめ、実行時ポリシー、両プロンプト、応答、ログ照合、判定、制約を第三者が追跡できることを確認する
