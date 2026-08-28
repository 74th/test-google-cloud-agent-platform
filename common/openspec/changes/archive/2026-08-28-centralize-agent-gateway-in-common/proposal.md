## Why

`nnyn-dev` では同じ方向の Agent Gateway をプロジェクトごとに複数作成できないため、検証ディレクトリごとに Gateway を所有する構成は衝突し、別検証からの再利用元も不明確になる。共有基盤の所有権を `common` に集約し、各検証を Gateway のライフサイクルから分離する必要がある。

## What Changes

- `common` に独立した Terraform state を持つ共有基盤を追加し、`nnyn-dev/us-central1` に専用 VPC、subnet、およびそのネットワークへ接続した Agent Gateway を作成できるようにする。
- 共有 Gateway の完全修飾リソース ID と、利用者が必要とするネットワーク情報を Terraform output として公開する。
- **BREAKING**: Agent Gateway の Terraform 所有権を `20260822-agent-gateway` から `common` へ移し、検証固有 Terraform が Gateway の作成・削除を担う構成を廃止する。
- `20260823-mcp-server` を含む利用側は、検証固有 Gateway を作成せず、`common` が管理する Gateway ID を明示的に参照する。
- 既存検証環境の cleanup は事前 plan、依存確認、および人間の明示承認を必須とし、承認後に既存 state を一度 destroy してから旧 Gateway 定義を除去する。利用側 Terraform の再 apply はこの変更の対象外とする。

## Capabilities

### New Capabilities

- `shared-agent-gateway-infrastructure`: 共有 VPC/subnet/VPC 接続 Agent Gateway の Terraform 所有権、出力契約、および安全な既存環境移行を規定する。

### Modified Capabilities

- なし。

## Impact

- `common`: 新規 Terraform 構成、変数、出力、静的検証、および運用手順。
- `20260822-agent-gateway`: 既存 state の承認付き cleanup と、Gateway・関連する Gateway 専用リソースの Terraform 定義および直接参照の除去。
- `20260823-mcp-server`: 既存 state の承認付き cleanup、残存する Gateway 作成用コードの除去、および共有 Gateway ID の参照契約更新。
- Google Cloud: `nnyn-dev` の `us-central1` にある Agent Gateway、Network Services/Network Security API、専用 VPC/subnet、および関連 IAM・認可リソース。
- 既存 Gateway の削除から共有 Gateway の作成まで一時的な停止時間が発生し得る。OpenSpec の計画・検証自体はクラウドリソースを変更しない。
