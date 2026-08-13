## 1. Terraform と所有境界

- [x] 1.1 `dns.googleapis.com` を Terraform の有効化対象へ追加し、既存 VPC を参照する `google_dns_policy.gke_dns_logging` を `enable_logging = true` で追加して API 有効化との依存関係を設定する
- [x] 1.2 DNS Policy 名と logging 状態を後段検証で参照できる Terraform output を追加する
- [x] 1.3 `scripts/setup-infrastructure.sh` に対象 VPC の既存 DNS Policy と Terraform state の preflight を追加し、state 外 policy が存在する場合は重複作成や自動 import をせず plan 前に停止する
- [x] 1.4 Terraform format と validate を実行し、保存 plan が対象 VPC の単一 DNS Policy と Cloud DNS API だけを追加し、既存 VPC、IAM、通信 policy、Log Router sink / exclusion を変更しないことを確認する

## 2. DNS query log の自動検証

- [x] 2.1 対象 Pod、問い合わせ FQDN、開始 UTC 時刻を取得し、`resource.type="dns_query"` と `queryName` で Cloud Logging を有限時間 polling する `scripts/test-dns-query-logging.sh` を追加する
- [x] 2.2 検証スクリプトで実ログの末尾 dot や `rdata` 表現を許容しつつ、`queryName`、`sourceIP`、IP を含む `rdata` を必須検証し、成功時に timestamp、responseCode を含む相関フィールドを表示する
- [x] 2.3 認証・権限エラー、Logging / DNS API 無効、query 失敗、必須 field 欠落、polling timeout を非ゼロ終了にし、テスト FQDN、timeout、polling 間隔を環境変数で変更可能にする
- [x] 2.4 DNS query log の `rdata` と既存 `policy-action` deny log の宛先 IP を同じ問い合わせ名と時間窓で比較し、Pod、DNS timestamp / sourceIP / queryName / rdata、deny timestamp / destination IP / port を表示する相関検証を追加する

## 3. 運用手順と制約の文書化

- [x] 3.1 README の再現手順に DNS Policy の plan / apply 確認、DNS query log 検証スクリプト、Logs Explorer と `gcloud logging read` の `dns_query` 検索例を追加する
- [x] 3.2 `dns_query` に namespace / Pod / container metadata がないこと、`sourceIP` が常に Pod IP とは限らないこと、および時刻・問い合わせ名・`rdata`・deny 宛先 IP による相関手順を記載する
- [x] 3.3 DNS cache とログ遅延、VPC 全体のログ量・課金、Shared VPC では host project 側に記録され得ること、外部 sink と広範な exclusion を追加しない方針を記載する
- [x] 3.4 Terraform 管理の DNS logging だけを無効化または削除し、既存 GKE、VPC、NetworkPolicy logging、sink を変更しない rollback 手順を追加する

## 4. 実環境での受入確認

- [x] 4.1 レビュー済み Terraform plan を apply し、対象 VPC の DNS Policy が重複せず `enableLogging` 有効で Terraform state に所有されていることを確認する
- [x] 4.2 対象テスト Pod から解決可能な FQDN を問い合わせ、Cloud Logging の実 entry で `queryName`、`sourceIP`、`responseCode`、IP を含む `rdata` を確認する
- [x] 4.3 未許可 FQDN の deny テストと相関検証を実行し、DNS 応答 IP と `policy-action` の destination IP が時刻情報とともに対応することを確認する
- [x] 4.4 既存の GitHub、Vertex AI、BigQuery の許可通信と未許可通信の拒否を再検証し、追加の FQDN allowlist、ワークロード IAM role、外部 sink、広範な exclusion がないことを確認する
- [x] 4.5 実行 UTC 時刻、対象 Pod、DNS Policy、実ログのフィールド形、DNS / deny 相関結果を README の検証結果へ記録する
