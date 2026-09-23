# Proposal

## Why

GKE Agent Sandbox は、エージェントのコードを gVisor でカーネル分離された Pod として実行し、Sandbox ごとの永続ストレージとライフサイクル管理を提供するとされている。ただし、Job のような「1 回実行して終了する」使い方、Egress の通信制御、セッションをまたいだワークスペース永続化が、Claude Agent SDK と組み合わせて実際に機能するかはまだ確認できていない。そこで、最小構成を実際に構築して、実機で動作を確かめる。

## What Changes

- Terraform で GKE Standard クラスタを新規に構築する。Dataplane V2 と FQDN Network Policy、Workload Identity Federation を有効にし、システム用ノードプールと gVisor（GKE Sandbox）ノードプールを作る。あわせて Artifact Registry、GCS バケット、KSA principal への IAM も用意する。
- Agent Sandbox コントローラ（`Sandbox` CRD）をクラスタに導入する。
- Agent Runner コンテナを新規に作る。環境変数で指定した GCS 上の JSONL を読み込み、Vertex AI の Claude Haiku 4.5（`claude-haiku-4-5@20251001`）で Claude Agent SDK を実行する。応答を追記した JSONL は GCS に書き戻す。Claude のセッション状態と作業ファイルは Sandbox の永続ボリューム（`/workspace`）に保存する。
- ローカル CLI を新規に作る。プロンプトを GCS に保存し、Sandbox を作成または再開して終了まで監視する。終了後に応答とセッション ID を表示する。セッション ID を渡すと、前回の会話とワークスペースを引き継いで続きの対話ができる。
- Sandbox Pod に Egress 制御（default deny + FQDN 許可リスト）を適用する。
- 検証手順を用意する。`https://github.com/74th` にはアクセスでき要約できること、`https://www.tohoho-web.com/` にはアクセスできず要約できないこと、ワークスペースが永続化されていることを、スクリプトで確認できるようにする。

## Capabilities

### New Capabilities
- `sandbox-infrastructure`: Terraform による GKE Standard クラスタ（gVisor ノードプール、Dataplane V2、FQDN Network Policy、Workload Identity）、Artifact Registry、GCS、IAM、Agent Sandbox コントローラの導入
- `agent-runner`: GCS の JSONL を入出力とし、Vertex AI 上の Claude Haiku 4.5 で Claude Agent SDK を実行し、状態を永続ワークスペースに保存するコンテナ
- `sandbox-session-cli`: プロンプトの投入、Sandbox の作成・再開・監視、応答とセッション ID の表示、セッション継続を行う CLI
- `sandbox-egress-control`: Sandbox Pod の Egress を default deny とし、必要な FQDN だけを許可する通信制御
- `sandbox-validation`: Egress 制御、ワークスペース永続化、カーネル分離を確認する検証手順と記録

### Modified Capabilities
（なし。このプロジェクトには既存の spec がない）

## Impact

- 新規ディレクトリ: `terraform/`、`k8s/`、`container/`、`cli/`（Python / uv）、`scripts/`、`evidence/`、`README.md`
- GCP プロジェクト `nnyn-dev` に次を新規作成する: GKE クラスタ、ノードプール、Artifact Registry リポジトリ、GCS バケット、IAM バインディング。既存の VPC `default` を利用する。
- 外部依存: kubernetes-sigs/agent-sandbox（CRD とコントローラ）、`claude-agent-sdk`、`@anthropic-ai/claude-code`、`google-cloud-storage`、`kubernetes` Python クライアント
- コスト: GKE Standard のノード（システムプールと gVisor プール）、Vertex AI の Claude 呼び出し。検証が終わったら destroy する手順を用意する。
- 既存の兄弟ディレクトリ（`20260811-gke-isolated` など）や `common/` の state には触れない。
