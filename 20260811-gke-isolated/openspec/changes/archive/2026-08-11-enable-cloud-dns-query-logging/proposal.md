## Why

NetworkPolicy / Dataplane V2 の deny ログには宛先 IP アドレスしか記録されず、その通信に先立ってワークロードがどの FQDN を名前解決したかを後から確認できない。対象 VPC の Cloud DNS Query Logging を有効にし、DNS 応答と deny ログを時刻・送信元・宛先 IP で相関できる証跡を Cloud Logging に残す必要がある。

## What Changes

- GKE クラスタが使用する既存 VPC に Cloud DNS Policy を Terraform で関連付け、DNS Query Logging を有効化する。
- Cloud DNS API を既存の Terraform 管理対象 API に追加し、DNS Policy が API 有効化後に作成されるようにする。
- テスト Pod から DNS 問い合わせを発生させ、`dns_query` ログの `queryName`、`sourceIP`、`rdata` を有限時間内に確認する再実行可能な検証を追加する。
- DNS Query Logging と NetworkPolicy deny ログを、時刻、Pod IP / `sourceIP`、名前解決結果 / deny 宛先 IP によって調査する手順と、キャッシュおよび Kubernetes メタデータ非付与の制約を文書化する。
- ログは既存の Cloud Logging 保存経路を利用し、外部 sink やプロジェクト全体へ影響する exclusion は追加しない。

## Capabilities

### New Capabilities

- なし。

### Modified Capabilities

- `isolated-claude-agent-runtime`: 対象 VPC の DNS Query Logging を IaC で有効化し、GKE ワークロードの FQDN、名前解決結果、送信元 IP を Cloud Logging で確認して NetworkPolicy deny ログと相関できる要件を追加する。

## Impact

- `terraform/`: Cloud DNS API と、既存 VPC に対する `google_dns_policy` の管理を追加する。
- `scripts/`: テスト Pod から DNS 問い合わせを発生させ、Cloud Logging を polling・検証するスクリプトを追加する。
- `README.md`: Logs Explorer / CLI の検索例、deny ログとの相関手順、namespace で直接絞れない制約、キャッシュおよび Shared VPC の注意点を追加する。
- Google Cloud: 対象 VPC 全体の DNS query log が Cloud Logging に保存され、ログ量と課金が増加する可能性がある。
