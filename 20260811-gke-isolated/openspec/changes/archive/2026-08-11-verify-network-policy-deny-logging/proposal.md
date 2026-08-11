## Why

現在の検証は未許可ホストへの `curl` が timeout することだけを確認しており、NetworkPolicy による拒否だったことを後から追跡できる永続的な証跡がない。GKE Dataplane V2 の Network Policy Logging を有効化し、拒否通信が Cloud Logging に記録されることまで受入シナリオとして検証したい。

また、汎用的な Artifact Registry ID `claude-agent` が別プロダクトと衝突し、cleanup時に所有対象を誤認できる状態だった。検証環境固有のIDとTerraform stateを唯一の削除対象として、他プロダクトのリポジトリを変更・削除しない境界を明確にする必要がある。

## What Changes

- GKE が自動作成する `NetworkLogging/default` を構成し、許可通信のログは増やさず、拒否通信だけを Cloud Logging の `policy-action` ログへ出力する。
- NetworkPolicy 適用後に未許可の `checkip.amazonaws.com` への接続失敗を発生させ、対象クラスタ、Pod、egress、deny、発生時刻で絞り込んだログが有限時間内に取得できることを検証する。
- 接続元 Pod、宛先 IP/port、protocol、direction、disposition、集約 count を表示し、アプリケーションの timeout とデータプレーンの拒否ログを対応付ける。
- ログ反映遅延、deny ログの集約、Cloud Logging の保存・課金、およびトラブルシューティング手順を README に記載する。
- 既存の FQDN allowlist は変更せず、`claude.ai` を含む追加ホストをログ確認のために許可しない。
- `artifact_repository_id` の既定値を `test-gke-isolated` とし、image build、push、deploy、出力、README、cleanupではTerraform outputから得た同じIDを一貫して使用する。
- Terraform stateにない同名リポジトリを既存環境からimportして削除対象へ加えることを禁止し、cleanupは現在のstateが所有するリソースだけに限定する。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `isolated-claude-agent-runtime`: GKE Dataplane V2 のdenyログをCloud Loggingから追跡できる要件と、Artifact Registryを検証環境固有のID・Terraform state所有境界で安全に管理する要件を追加する。

## Impact

- `k8s/`: クラスタ既定の `NetworkLogging/default` に deny logging を設定するマニフェストまたは適用処理。
- `scripts/`: logging 設定の適用、拒否通信の発生、`gcloud logging read` による有限時間の照合検証。
- `terraform/`: Artifact Registry IDの既定値、Logging API、リポジトリURL output、およびstate所有対象だけを削除する運用境界。
- `README.md`: 実行順、Logs Explorer/gcloud の検索例、期待するログ項目、反映遅延とログ集約の注意事項。
- Google Cloud: GKE Dataplane V2、Cloud Logging の `policy-action` ログ、ログ保存量に応じた課金。
- セキュリティ境界: Pod の外向き許可先および Workload Identity の IAM 権限は変更しない。ログ検索は検証を実行するオペレータの Google Cloud 認証を使用する。
