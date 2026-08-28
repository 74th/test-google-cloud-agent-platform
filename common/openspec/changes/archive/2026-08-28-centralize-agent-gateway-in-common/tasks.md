## 1. 現行能力と移行対象の確認

- [x] 1.1 公式 Google Cloud API discovery と Terraform provider schema で VPC 接続 Agent Gateway の resource、接続フィールド、必要な補助リソース、project/direction 上限を確認し、参照 URL、API/provider version、schema 抜粋を runbook に記録してレビューできることを確認する
- [x] 1.2 `nnyn-dev/us-central1` の Gateway、VPC、subnet、CIDR、長時間 operation を読み取り専用で inventory し、共有リソース名と重複しない subnet CIDR を選定して証跡ファイルに保存する
- [x] 1.3 `20260822-agent-gateway` と `20260823-mcp-server` の backend、workspace、state list、Gateway 参照、Agent Runtime などの consumer を読み取り専用で棚卸しし、state ごとの所有対象と未解決 consumer が一覧化されていることを確認する

## 2. common 共有 Terraform の実装

- [x] 2.1 `common/terraform` に version/provider/backend、`nnyn-dev/us-central1` の境界、固有名、labels、subnet CIDR validation を定義し、`terraform fmt -check` と `terraform validate` が成功することを確認する
- [x] 2.2 auto subnet を無効化した専用 VPC と `us-central1` の専用 subnet を実装し、Terraform test または plan JSON が意図した project、region、CIDR、および2リソースだけを示すことを確認する
- [x] 2.3 公式 schema に従って専用ネットワークへ接続する共有 Agent Gateway を実装し、静的テストと plan JSON が Gateway から VPC/subnet または公式接続リソースへの依存を示すことを確認する
- [x] 2.4 `agent_gateway_id`、`network_id`、`subnetwork_id` の output と非機密属性を実装し、Terraform test が完全修飾 Gateway ID の project/location と各 output の存在を検査することを確認する
- [x] 2.5 API 有効化と必須補助リソースを最小範囲で実装し、構成と plan を検査して Agent Runtime、Registry service、MCP server、GKE、Cloud Run、Artifact Registry、検証固有 IAM が common の管理対象に含まれないことを確認する

## 3. 静的検証と運用手順

- [x] 3.1 Terraform format/validate/test と plan JSON 検査を一括実行できる検証手順を追加し、空の専用 state に対する plan が VPC、subnet、VPC 接続 Gateway、および文書化された必須補助対象だけを作成することを確認する
- [x] 3.2 preflight、destroy 承認ゲート、旧コード除去、common plan/apply 承認ゲート、live 検証、rollback を順序付き runbook に記述し、どの destroy/apply も自動実行されず対象 directory/state/command が明記されていることを確認する
- [x] 3.3 common と隣接2ディレクトリの変更を別コミット・別検証結果で扱う手順、および利用側を再 apply しない境界を文書化し、レビューで所有権と実行範囲を追跡できることを確認する

## 4. 既存 state の承認付き cleanup

- [x] 4.1 各既存 state で refresh-only plan、通常 plan、`terraform plan -destroy -out=<専用ファイル>` を個別に作成し、全削除対象、project、workspace、Gateway consumer、想定外変更を人間へ提示する。このタスクでは destroy を実行していないことを確認する
- [x] 4.2 `20260822-agent-gateway` の destroy plan に対する人間の明示承認を得た場合のみ、その保存済み plan を対象 directory で適用し、operation 完了、state、Gateway list、残存リソースを確認する。承認がなければ未完了のまま停止する
- [x] 4.3 `20260823-mcp-server` の destroy plan に対する人間の明示承認を得た場合のみ、その保存済み plan を対象 directory で適用し、operation 完了、state、および残存リソースを確認する。承認がなければ未完了のまま停止する
- [x] 4.4 承認済み cleanup 完了後、project に競合する同方向 Gateway と未解決 consumer が存在しないことを live API と保存済み inventory の差分で確認する

## 5. 旧所有コードと利用側契約の更新

- [x] 5.1 `20260822-agent-gateway` から Gateway、Gateway 専用 authorization resource、不要になった変数/output/テスト/スクリプト結合を除去し、静的テストと `terraform validate` が Gateway resource を所有しない構成で成功することを確認する
- [x] 5.2 `20260823-mcp-server` からコメントアウト済み Gateway 作成コード、不要な Gateway name、旧固定 Gateway ID を除去し、共有 `agent_gateway_id` を明示入力として要求するテストと `terraform validate` が成功することを確認する
- [x] 5.3 両利用側について `terraform plan` または apply を実行せず、コード差分、テスト結果、および「未デプロイ」の状態を移行証跡へ記録して、この変更中に再 apply されていないことを確認する

## 6. common の承認付きデプロイと live 検証

- [x] 6.1 既存 Gateway の消失確認後に common の最終 plan を専用ファイルへ保存し、project、region、backend/state、名前、CIDR、作成/変更/削除 action を人間へ提示する。このタスクでは apply を実行していないことを確認する
- [x] 6.2 common の保存済み plan に対する人間の明示承認を得た場合のみ apply し、Terraform state と JSON output から共有 Gateway、VPC、subnet の ID を取得できることを確認する。承認がなければ未完了のまま停止する
- [x] 6.3 Gateway/VPC/subnet を live API で describe し、Gateway の公式ネットワーク接続識別子が common の VPC/subnet に解決され、`nnyn-dev/us-central1` に存在することをタイムスタンプ付き証跡で確認する
- [x] 6.4 Terraform state と live inventory を突合し、common が検証固有リソースを所有せず、利用側 state が共有 Gateway を所有せず、利用側が再 apply されていないことを最終レポートで確認する
- [x] 6.5 全 artifact と実装結果に対して OpenSpec strict validation、Terraform の全静的テスト、および変更済み利用側テストを実行し、計画検証と live 検証の結果を区別して最終レポートへ記録する
