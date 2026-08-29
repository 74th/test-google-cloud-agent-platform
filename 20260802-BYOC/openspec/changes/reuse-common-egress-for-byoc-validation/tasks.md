## 1. 事前棚卸しと共有 Gateway 境界

- [x] 1.1 active account、project、region、CLI/SDK/Terraform version、BYOC Terraform workspace/state、live Runtime 一覧を読み取り専用で収集し、秘密情報を含まない preflight evidence に対象と既存 consumer が記録されていることを確認する
- [x] 1.2 `common/terraform` の `agent_gateway_id` output、`google_network_services_agent_gateway.shared` state、live `common-egress` describe を収集し、完全修飾 ID、project、location、governed access path、Registry、Network Attachment が一致することを機械的な検査で確認する
- [x] 1.3 `common/terraform` の通常 plan が no-op であること、および Network Attachment、subnet、VPC の live 参照関係が common state と一致することを確認し、drift または差分があれば以降の書き込みを停止する
- [x] 1.4 BYOC Terraform の通常 plan と live resource inventory を保存し、作成・変更対象がこの検証専用の Artifact Registry、Registry Service、Endpoint IAM、サービスアカウント、IAM、GCS、API state に限定され、common と他 experiment の resource が含まれないことを確認する

## 2. Gateway 関連付け付き Runtime デプロイ

- [x] 2.1 `scripts/deploy_agent.py` に完全修飾 `--agent-gateway` の必須入力と project/location 整合性検査を追加し、有効値、不正形式、project/location 不一致の単体テストを通す
- [x] 2.2 Runtime create payload に `spec.deploymentSpec.agentGatewayConfig.agentToAnywhereConfig.agentGateway` と既存の custom container、class methods、service account/identity を一度に設定し、serialized request の契約テストで Gateway field が除去されないことを確認する
- [x] 2.3 現行 Agent Platform SDK が原子的な Gateway 関連付けを保持できない場合は同じ v1 create payload を送る認証済み REST 実装へ切り替え、mock API テストで URL、payload、operation polling、秘密情報を含まない error handling を確認する
- [x] 2.4 Runtime 作成後の live GET から Gateway ID、identity type、`spec.containerSpec.imageUri` の image digest を要求値と照合し、不一致時は操作検証を停止する verifier とテストを追加する。BYOC GET にない revision/traffic/deployedModels は必須条件にしない
- [x] 2.5 deployment result に Runtime resource、image digest、Gateway ID、identity、時刻だけを保存し、token、header、入力本文を保存しないことをテストする
- [x] 2.6 Gateway conflict、参照不正、権限拒否を安全に分類して evidence へ残し、Gateway なしの再試行、既存 Runtime の変更、common resource の変更を行わない停止動作をテストする

## 3. ローカル検証とクラウド基盤

- [x] 3.1 `uv run pytest -q` と既存のローカル Runtime 4操作を実行し、ルート、単項、ストリーム、長時間入力正規化、ログ秘匿に回帰がないことを確認する
- [x] 3.2 コンテナをローカルで build・起動し、`POST /` と4操作の応答、順序、`request_id`/`verification_id` 付きライフサイクルログを確認して結果を保存する
- [x] 3.3 `terraform -chdir=terraform fmt -check`、`init -input=false`、`validate` と saved plan の JSON 検査を実行し、1.4 の対象境界を再確認する
- [x] 3.4 対象を確認した BYOC saved plan を apply し、Terraform output、state、作成した Artifact Registry、サービスアカウント、IAM、GCS が plan と一致することを確認する
- [x] 3.5 一意な tag でイメージを build/push し、Artifact Registry から取得した immutable digest と build 時刻を deployment evidence に記録する

## 4. common-egress 関連付けと通常操作

- [x] 4.1 1.2 で検証した `common-egress` の完全修飾 ID と3.5 の image digest を一つの create request に含めて新規 BYOC Runtime を作成し、operation 完了と Runtime resource 名を保存する
- [x] 4.2 Runtime live GET を実行し、Gateway ID が `common-egress`、identity、`spec.containerSpec.imageUri` の image digest が要求値と一致することを確認して `gateway_preflight`、`runtime_gateway_association`、`runtime_identity_image` を個別に判定する。revision/traffic/deployedModels は BYOC では `not_applicable` とする
- [x] 4.3 デプロイ済み Runtime に `query`、`async_query`、`stream_query`、`async_stream_query` を一意な検証 ID で実行し、応答内容、順序、経過時間、対応する Cloud Logging のコンテナログを照合する
- [x] 4.4 旧 `agw-20260822-*` Gateway、Registry Service、Endpoint policy と現行 `common-egress`、`mcp-20260823-*` consumer を live inventory し、旧 resource が存在しないことと保護対象を削除していないことを確認する
- [x] 4.5 BYOC Terraform に専用 GCS Registry Service、投影 Endpoint data source、対象 Runtime principal 限定の `roles/iap.egressor` を追加し、google-nightly provider schema と scoped plan を検査する
- [x] 4.6 Service、Endpoint、IAM policy を apply し、live read-back と common Gateway の不変性を確認して非機密 evidence を保存する

## 5. 長時間クエリジョブ再検証

- [x] 5.1 Service/Policy の live read-back 後に約10秒の query job を専用 GCS 入出力先で再試行し、GCS input、`POST /`、`query_completed`、成功終端、GCS output の5段階を同じ Runtime、試行 ID、時間範囲で確認する。既存の policy 前試行は診断 evidence として保持する
- [x] 5.2 5.1 の5段階がすべて成功した場合だけ960秒 query job を実行し、処理時間を超える有限の監視期限でキャンセルせず成功終端まで追跡して、対応ログと非機密の GCS 出力属性を保存する（5.1 のゲート失敗により未実行）
- [x] 5.3 同等の入力を SDK query-job 経路と REST `:asyncQuery` 経路で実行し、両方の入力形式、`POST /`、終端状態、出力 URI と非機密のサイズ/形式を比較する（5.1 のゲート失敗により未実行）
- [x] 5.4 各長時間試行について proxy、job container、Runtime、GCS、operation の証跡を段階別に評価し、不足証跡や失敗を推測で PASS にせず正確な最終到達段階として記録する

## 6. 結果、所有境界、後片付け待ち

- [x] 6.1 common Gateway describe と対象時間範囲の Gateway log を収集し、Runtime 関連付け、BYOC ingress/processing、Gateway egress decision を別々に報告して、対応 decision log がなければ `gateway_traffic=unproven` または `not_applicable` とする
- [x] 6.2 2026-08-22 の既存結果と今回の4操作、短時間、960秒、SDK/REST 比較を並べ、Runtime、image digest、Gateway ID、caller/identity、route、authorization layer、ログ検索条件を含む非機密の結果文書と README 手順を作成する
- [x] 6.3 検証後の Runtime、Terraform state、GCS オブジェクト、共有 Gateway consumer を inventory し、明示対象の Runtime 削除コマンドと BYOC destroy plan だけを提示して、人間の明示承認なしに削除または `terraform destroy` を実行していないことを確認する
- [x] 6.4 Service/Policy 追加後のすべての自動テスト、Terraform static checks、`openspec validate reuse-common-egress-for-byoc-validation --strict` を実行し、実装済み task と live evidence のみを完了として最終結果へ記録する
