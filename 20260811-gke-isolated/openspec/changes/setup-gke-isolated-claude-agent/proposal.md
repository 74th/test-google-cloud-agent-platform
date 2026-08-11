## Why

Claude Agent SDK を GKE 上で安全に実行し、Vertex AI と BigQuery の利用を維持しながら、エージェントが接続できる外部ホストを明示的な許可リストに制限できることを検証したい。再現可能な Terraform、Kubernetes マニフェスト、コンテナ、検証スクリプトを揃えることで、この構成を人間が後から再構築・再検証できるようにする。

## What Changes

- Terraform で `us-central1-a` に 1 ノードの GKE クラスタ `test-isolated` を構築し、GKE Dataplane V2 と Workload Identity を有効化する。
- Kubernetes Service Account から Vertex AI の Claude Haiku 4.5 と BigQuery ジョブを利用できるよう、最小限の Google Cloud IAM 権限を関連付ける。
- Claude Agent SDK のワンショット実行と BigQuery 公開データへのクエリ実行を行う Python コンテナを用意する。
- Service Account、Deployment、および許可リスト方式の外向き通信制御を `k8s/` のマニフェストとして管理する。
- 通信制御の適用前後に、GitHub、Claude Agent SDK、BigQuery の成功と、未許可ホストへの接続失敗を段階的に確認できる再実行可能なスクリプトを `scripts/` に用意する。

## Capabilities

### New Capabilities

- `isolated-claude-agent-runtime`: GKE Dataplane V2 上で Claude Agent SDK と BigQuery を実行し、必要な Google API と GitHub だけへの外向き通信を許可して検証できる隔離実行環境。

### Modified Capabilities

なし。

## Impact

- `terraform/`: GKE、ネットワーク設定、Artifact Registry、Workload Identity および KSA principal への IAM の構成。
- `container/`: Claude Agent SDK と BigQuery 検証用 Python コード、およびコンテナイメージ定義。
- `k8s/`: Service Account、Deployment、外向き通信ポリシーのマニフェスト。
- `scripts/`: プロビジョニング、ビルド・デプロイ、通信制御適用前後の検証を人間が実行できるスクリプト。
- Google Cloud の課金対象リソース、Vertex AI Model Garden の Claude モデル、BigQuery 公開データ、GitHub への外部通信。
