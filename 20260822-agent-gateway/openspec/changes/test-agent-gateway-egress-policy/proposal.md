## Why

Google Cloud Agent Platform の Agent Gateway が、Claude Agent SDK を用いた BYOC エージェントの外向き通信を許可リスト方式で制御できるかを再現可能な構成で検証する必要がある。GitHub への必要な通信は許可しつつ、未許可の内閣府ホストにはデフォルト拒否によって接続できないことを実証する。

## What Changes

- 既存の `20260801-agent-hosting` を参考に、重複しないリソース名で Claude Agent SDK の BYOC エージェントと必要な Google Cloud リソースを新規構築する。
- Agent Gateway の外向き通信をデフォルト拒否とし、`github.com` への通信だけを明示的に許可する。
- Model Garden の Claude Haiku 4.5 を `nnyn-dev` プロジェクトから利用できる実行サービスアカウントと権限を構成する。
- GitHub 組織ページの要約が成功し、未許可の `www8.cao.go.jp` から 2027 年の祝日を取得する指示が接続制御によって失敗することを確認する検証手順と証跡を用意する。

## Capabilities

### New Capabilities

- `agent-gateway-egress-validation`: Agent Gateway 配下の BYOC エージェントについて、許可リスト型の外向き通信制御、Claude Haiku 4.5 の利用、および許可・未許可ホストに対する検証可能な振る舞いを定義する。

### Modified Capabilities

なし。

## Impact

- Claude Agent SDK のエージェントサービス、コンテナ、デプロイ・呼び出しスクリプト、テスト、README を追加する。
- Terraform で Agent Platform、Agent Gateway、実行サービスアカウント、IAM、ネットワーク／ポリシー関連リソースを `us-central1`（Vertex AI モデル利用は `global`）に新規作成する。
- Google Cloud プロジェクト `nnyn-dev`、Model Garden の Claude Haiku 4.5、GitHub および内閣府サイトへの検証トラフィックに影響する。
- 参考プロジェクトの構成と実装は再利用するが、既存または削除済みのリソース名や状態には依存しない。
