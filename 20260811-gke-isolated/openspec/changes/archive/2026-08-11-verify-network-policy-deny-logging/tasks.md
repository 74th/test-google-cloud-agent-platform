## 1. Terraform所有境界とLogging基盤

- [x] 1.1 `artifact_repository_id` の既定値を `test-gke-isolated` に変更し、Terraform outputのrepository URLが同じIDを含むことを確認する
- [x] 1.2 `terraform/`、`scripts/`、現行README、Kubernetesマニフェストのimage build・push・deploy・表示経路を監査し、repository URLをハードコードせずTerraform outputへ統一する
- [x] 1.3 setupとcleanupの事前検査にTerraform state、project、location、repository IDの照合を追加し、state外の同名repositoryが存在する場合はimport・削除せず非ゼロで停止させる
- [x] 1.4 Terraform の required services に `logging.googleapis.com` を追加し、クラスタの Cloud Logging が有効であることを確認できるようにして `terraform fmt` と `terraform validate` を通す
- [x] 1.5 `k8s/network-logging.yaml` に `NetworkLogging/default` を定義し、deny は `log: true`、allow は `log: false`、両方の `delegate` は `false` とする
- [x] 1.6 NetworkLogging マニフェストの client-side/server-side dry-run、取得、describeによる設定エラー検査を実行できることを確認する

## 2. 適用・ログ検証スクリプト

- [x] 2.1 `scripts/apply-network-policy.sh` を、NetworkLogging を先に適用・確認してから標準NetworkPolicyとFQDNNetworkPolicyを適用する順序へ拡張する
- [x] 2.2 `scripts/test-network-policy-logging.sh` に gcloud/kubectlの前提検査、対象project・cluster・location・Podの取得、UTC開始時刻と `checkip.amazonaws.com` のIPv4解決結果の記録、有限timeout付き拒否通信を実装する
- [x] 2.3 同スクリプトに `policy-action`、開始時刻、source Pod、egress、deny、tcp、port 80で絞る `gcloud logging read` の有限pollingを実装する
- [x] 2.4 取得ログの `src.pod_name`、`dest_ip`、`dest_port`、`protocol`、`direction`、`disposition`、`count` を表示・検証し、宛先IP不一致、ログ未検出、権限エラーを区別して非ゼロ終了させる
- [x] 2.5 変更した全シェルスクリプトに `set -euo pipefail` と再実行可能性を持たせ、`bash -n` を通す

## 3. ドキュメントと静的検証

- [x] 3.1 README の再現手順に deny logging の適用と専用ログ検証を追加し、Logs Explorerと `gcloud logging read` の検索例、必要なオペレータ権限、期待fieldを日本語で記載する
- [x] 3.2 README にログ反映遅延、deny集約、暗黙denyではpolicy名が出ない制約、Cloud Loggingの保存・課金、deny loggingの無効化手順を記載する
- [x] 3.3 READMEの構築・手動操作・cleanup例を `test-gke-isolated` とTerraform outputへ統一し、`claude-agent`を運用対象として参照する記述を残さない
- [x] 3.4 Terraform planとマニフェスト差分を確認し、FQDN allowlist、KSA principalのIAM role、Podの外向き許可先が増えていないことを確認する

## 4. 実環境での受入検証とcleanup

- [x] 4.1 `nnyn-dev` のrepository一覧と空のTerraform stateを事前確認し、他repositoryを変更せず `test-gke-isolated` を新規作成するplanだけを承認してTerraformを再適用する
- [x] 4.2 通信制御前テストを成功させ、deny loggingとNetworkPolicyを適用した後、通信制御後テストでGitHub・Vertex AI・BigQueryの成功と `checkip.amazonaws.com` の拒否を再確認する
- [x] 4.3 専用ログ検証を実行し、同じPodと接続試行に対応する `policy-action` のegress denyログ、および必須fieldと名前解決済み宛先IPの一致を確認する
- [x] 4.4 destroy前にstateの `google_artifact_registry_repository.agent` が `test-gke-isolated` を指すことと、destroy planに他repositoryが含まれないことを確認する
- [ ] 4.5 README の手順を先頭から再実行して結果を追記し、確認済みdestroy planでTerraform管理リソースを削除してstateが空であること、および他のArtifact Registry repositoryが保持されたことを確認する
