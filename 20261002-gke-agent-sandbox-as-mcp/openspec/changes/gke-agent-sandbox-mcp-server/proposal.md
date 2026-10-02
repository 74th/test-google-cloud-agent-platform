# Proposal

## Why

MCP クライアント（エージェント）にコマンド実行環境を渡す場合、セッションごとに分離され、作業内容が残り、使っていない間は計算資源を消費しない Sandbox が必要になる。GKE Agent Sandbox は gVisor による分離、PVC による永続ワークスペース、`operatingMode` による Suspend / Resume を提供するとされているが、SandboxTemplate / SandboxClaim / per-claim `env` を組み合わせて、MCP Server からセッション単位で安全に操作できるかはまだ確認できていない。以前の検証（`../20260923-gke-agent-sandbox`）の基盤設計を引き継ぎ、production に発展させられる構造で MCP Server を作って実機で確かめる。

## What Changes

- 以前の検証の設計（D4、D6、D7、D8）に合わせて、Terraform で検証用基盤を新規に構築する。クラスタ名は `agent-sandbox-mcp` とし、GCS バケットと `roles/aiplatform.user` は作成・付与しない。
- Agent Sandbox コントローラ（Sandbox / SandboxClaim / SandboxTemplate / SandboxWarmPool の CRD）を導入し、実クラスタの CRD 仕様（`operatingMode`、`shutdownTime`、`volumeClaimTemplates`、claim の `env`、ownerReference、PVC の挙動）を確認して記録する。
- MCP Server を書く前に、Suspend / Resume、PVC の保持、`env` 注入、`shutdownTime` の挙動を手動で検証する。
- Python（uv）製の MCP Server を新規に作る。公式 `mcp` Python SDK v2 の `MCPServer` を使い、Streamable HTTP でツールを提供する。Coding Agent のワークスペース操作としてそのまま使えるよう、ツールの入出力は Codex の同名ツールにできるだけ合わせる。どのツールも `session_id` と `user_email` を受け取り、必要なら Sandbox を作成または Resume してから操作する。
  - `exec_command`: コマンドを実行する。`yield_time_ms` 以内に終わらなければ `process_id` を返し、バックグラウンドで実行を続ける（Codex のプロセス ID `session_id` は、ワークスペースの `session_id` と区別するため `process_id` とする）
  - `write_stdin`: 実行中のプロセスへの入力と、出力のポーリングを行う
  - `apply_patch`: Codex のパッチ形式でファイルを追加・更新・削除する
  - `view_image`: Sandbox 内の画像を返す
  - `delete_workspace`: 実行中のプロセスを停止し、Sandbox、Claim、PVC を削除する（Codex にはない独自ツール）
- ワークスペースの状態（Running / Suspended、最終 activity、Suspend / 削除の予定時刻）は、MCP ツールではなく MCP Server と同じプロセスの REST API で返す。
- `session_id` と `user_email` の 1 対 1 binding を、SandboxClaim の annotation に保存した HMAC で検証する。リソース名は `session_id` の hash から決定的に作り、生のメールアドレスは label、annotation、リソース名、ログに残さない。Sandbox 内では環境変数 `USER_EMAIL` で参照できるようにする。
- 最終 activity からの sliding idle timeout で Suspend し（PVC は保持）、実行中のプロセスがある間は Suspend しない。長期間（既定 7 日）使われないワークスペースは Sandbox / Claim / PVC ごと GC する。
- MCP Server をクラスタ内の通常 Deployment（1 replica、最小権限の RBAC）としてデプロイし、E2E 検証を実施する。検証の対象は MCP Server なので、LLM は使わず、MCP クライアントのスクリプトからツールを直接呼び出して判定する。結果を `evidence/` と README にまとめる。

## Capabilities

### New Capabilities
- `sandbox-infrastructure`: Terraform による GKE Standard クラスタ（gVisor ノードプール、Dataplane V2、FQDN Network Policy、Workload Identity）、Artifact Registry、Agent Sandbox コントローラの導入、Namespace・KSA・RBAC・SandboxTemplate などの Kubernetes マニフェスト
- `sandbox-egress-control`: Sandbox Pod の Egress を default deny とし、必要な FQDN だけを許可する通信制御
- `mcp-session-management`: `session_id` の検証、決定的なリソース名、`session_id` と `user_email` の binding、`USER_EMAIL` の注入、生メールアドレスを残さないプライバシー要件
- `mcp-sandbox-tools`: Codex 準拠のワークスペース操作ツール（`exec_command`、`write_stdin`、`apply_patch`、`view_image`）と `delete_workspace` の入出力と振る舞い、および状態取得の REST API
- `sandbox-lifecycle`: sliding idle timeout による Suspend、実行中プロセスの保護、Resume 時のワークスペース保持、retention 経過後の GC、MCP Server 停止時の安全網
- `sandbox-validation`: 実クラスタでの CRD 仕様確認、事前の手動検証、LLM を使わない E2E 検証、計測と証跡の記録

### Modified Capabilities
（なし。このプロジェクトには既存の spec がない）

## Impact

- 新規ディレクトリ・ファイル: `terraform/`、`k8s/`、`container/`、`scripts/`、`src/`、`tests/`、`evidence/`、`Dockerfile`、`pyproject.toml`、`uv.lock`、`README.md`
- GCP プロジェクト `nnyn-dev` に次を新規作成する: GKE クラスタ `agent-sandbox-mcp`、ノードプール 2 つ、Artifact Registry リポジトリ。既存の VPC `default` を利用する。
- 外部依存: kubernetes-sigs/agent-sandbox（CRD とコントローラ）、`k8s-agent-sandbox`、`mcp`（v2）、`kubernetes` Python クライアント
- コスト: GKE Standard のノード 2 台。検証が終わったら `terraform destroy` するかをユーザーに確認する。
- 既存の兄弟ディレクトリ（`20260923-gke-agent-sandbox`、`20260811-gke-isolated` など）や `common/` のリソースと state には触れない。
