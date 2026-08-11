## 1. Terraform 基盤

- [x] 1.1 `terraform/` に provider、入力変数、既定値、必要 API の有効化、および既存 `default` VPC/subnet の data source を定義する
- [x] 1.2 `test-isolated` ゾーンクラスタと 1 台固定の `e2-standard-2` ノードプールを定義し、Dataplane V2、Workload Identity、FQDN Network Policy を有効にする
- [x] 1.3 Artifact Registry、KSA principal への Vertex AI/BigQuery の最小 IAM role を定義する
- [x] 1.4 後段処理に必要な project、cluster、zone、KSA principal、image repository の Terraform output を追加し、`terraform fmt` と `terraform validate` を通す

## 2. エージェントコンテナ

- [x] 2.1 `container/` にバージョン固定した Claude Agent SDK、Claude Code CLI、BigQuery クライアント、curl を含む Dockerfile と依存定義を作る
- [x] 2.2 prompt 引数、Vertex AI の project/location、`claude-haiku-4-5@20251001`、最小ツール設定を使って最終応答を出力する `claude_agent_sdk.py` を実装する
- [x] 2.3 指定された Google Trends SQL を BigQuery ジョブとして実行し、結果または 0 行を明確に出力する `test_bq.py` を実装する
- [x] 2.4 コンテナをローカルで build し、両 Python スクリプトの引数・構文・起動時エラーがないことを確認する

## 3. Kubernetes マニフェスト

- [x] 3.1 `k8s/` に GSA annotation を持たない `test` Kubernetes Service Account マニフェストを作る
- [x] 3.2 専用ラベル、`test` KSA、Vertex 用環境変数、差し替え可能な image を持ち、`kubectl exec` 用に常駐する `test` Deployment を作る
- [x] 3.3 対象 Pod の egress をデフォルト拒否し、クラスタ DNS と Workload Identity metadata endpoint だけを許可する標準 NetworkPolicy を別適用可能な形で作る
- [x] 3.4 `github.com`、`aiplatform.googleapis.com`、`bigquery.googleapis.com` の TCP 443 だけを許可する GKE FQDNNetworkPolicy を別適用可能な形で作る
- [ ] 3.5 マニフェストの client-side/server-side dry-run を行い、通常リソースだけを適用する経路と通信制御を追加適用する経路が分離されていることを確認する

## 4. 人間が再実行できる操作スクリプト

- [x] 4.1 前提ツールと対象 project を検査し、Terraform init/plan/apply、kubeconfig 取得、クラスタ構成確認を行う基盤セットアップスクリプトを `scripts/` に作る
- [x] 4.2 Terraform output を使って image を build/push し、KSA/Deployment を適用して rollout 完了まで待つデプロイスクリプトを作る
- [x] 4.3 GitHub keys の curl、指定 prompt の Claude Agent SDK、BigQuery クエリを順に実行し、いずれかの失敗を非ゼロで返す制限前テストスクリプトを作る
- [x] 4.4 通信制御マニフェストを適用し、対象リソースの成立を表示して収束を待つスクリプトを作る
- [x] 4.5 制限前と同じ 3 つの成功確認に加え、有限 timeout 付き `checkip.amazonaws.com` が接続失敗することを必須とする制限後テストスクリプトを作る
- [x] 4.6 各スクリプトに `set -euo pipefail`、前提検査、対象表示、再実行可能性を持たせ、実行順・想定結果・手動 `kubectl exec` 例・rollback/cleanup を README に記載する

## 5. 実環境での基準検証

- [ ] 5.1 Terraform plan をレビューして apply し、`test-isolated` が `us-central1-a`、`default` subnet、Dataplane V2 有効、`e2-standard-2` 1 ノードであることを gcloud/kubectl で確認する
- [ ] 5.2 image を Artifact Registry に push して通常マニフェストだけを deploy し、Pod が `test` KSA で Ready になることと長期サービスアカウント鍵がないことを確認する
- [ ] 5.3 通信制御未適用の状態で GitHub keys、Claude Agent SDK の GitHub 要約、BigQuery 公開データクエリがすべて成功するまで原因を修正し、出力を確認する

## 6. 許可リスト適用後の検証

- [ ] 6.1 標準 NetworkPolicy と FQDNNetworkPolicy を適用し、選択対象、DNS、metadata endpoint、および許可 FQDN が意図した値であることを確認する
- [ ] 6.2 新しい `kubectl exec` 接続で GitHub keys、Claude Agent SDK の GitHub 要約、BigQuery クエリが引き続き成功することを確認する
- [ ] 6.3 `curl http://checkip.amazonaws.com` が timeout 内に失敗し、未許可ホストの応答本文を取得できないことを確認する
- [ ] 6.4 必要な正規 endpoint が不足した場合は実行ログと DNS 観測を記録し、正確な FQDN だけを許可リストへ追加して制限前後の全テストを再実行する
- [ ] 6.5 最終的なスクリプトを先頭から再実行して受入シナリオを再現し、README の手順と実際のコマンド・期待結果が一致することを確認する
