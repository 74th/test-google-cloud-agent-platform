# Tasks

## 1. Terraform 基盤

- [ ] 1.1 `terraform/` を作成する。中身は versions、providers、variables、`terraform.tfvars.example`（`project_id = "nnyn-dev"`）、`.gitignore`、`.terraform-version`。`terraform init && terraform validate` が通ることを確認する
- [ ] 1.2 次を定義する。必要な API（container、aiplatform、storage、artifactregistry、iam、sts など）の有効化（`disable_on_destroy = false`）、既存 VPC `default` と subnet の data 参照、GKE Standard のゾーンクラスタ `agent-sandbox`（Dataplane V2、FQDN Network Policy、Workload Identity）。`terraform validate` が通ることを確認する
- [ ] 1.3 `system-pool`（`e2-standard-2` × 1）と `sandbox-pool`（`e2-standard-4` × 1、`sandbox_config { sandbox_type = "gvisor" }`、`GKE_METADATA`）を定義する。`terraform validate` が通ることを確認する
- [ ] 1.4 Artifact Registry リポジトリ、GCS バケット（uniform bucket-level access、`force_destroy = true`）、KSA principal（`ns/agent-sandbox/sa/agent-runner`）への `roles/aiplatform.user` と、バケット単位の `roles/storage.objectUser` を定義する。outputs（クラスタ名、ゾーン、バケット、イメージリポジトリ）を追加し、`terraform validate` が通ることを確認する
- [ ] 1.5 `terraform plan` を保存し、作成対象がこの変更のリソースだけで、既存の VPC、`common/`、兄弟ディレクトリのリソースに変更がないことを確認する。ユーザーの承認を得てから apply し、`gcloud container clusters describe` で Standard モード、ADVANCED_DATAPATH、FQDN policy、gVisor ノードプールになっていることを確認する

## 2. Agent Sandbox の導入とスパイク

- [ ] 2.1 GKE のマネージドな Agent Sandbox 有効化手段があるかを調べ、なければ kubernetes-sigs/agent-sandbox の最新安定リリースを選ぶ。バージョンを固定した `scripts/install-agent-sandbox.sh` を作成し、実行後に `kubectl get crd sandboxes.agents.x-k8s.io` とコントローラ Pod の Ready を確認する
- [ ] 2.2 `k8s/namespace.yaml` と `k8s/service-account.yaml`（namespace `agent-sandbox`、KSA `agent-runner`）を作成する。適用後、`kubectl get runtimeclass gvisor` が存在することを確認する
- [ ] 2.3 スパイク 1: busybox の Sandbox（`runtimeClassName: gvisor`、`restartPolicy: Never`、`volumeClaimTemplates`）で次の 3 点を確かめる。(a) コマンドが終了すると Pod が Succeeded になり、再作成されない。(b) `replicas: 0` で Pod が削除され、PVC が残る。(c) `replicas: 1` で新しい Pod が同じ PVC を使い、前回書いたファイルが読める。結果を `evidence/YYYYMMDD-spike-lifecycle.md` に記録し、D1 の方式を採用するかフォールバックにするかを確定する
- [ ] 2.4 `k8s/network-policy.yaml`（default deny + DNS + メタデータサーバー）と `k8s/fqdn-network-policy.yaml`（aiplatform、storage、github.com の 443）を作成し、`kubectl apply --dry-run=server` が通ることを確認する
- [ ] 2.5 スパイク 2: curl イメージの Sandbox（`app=agent-runner` label、gVisor）で次を確かめる。github.com への接続は成功し、www.tohoho-web.com への接続は失敗する。`storage.googleapis.com` と `aiplatform.googleapis.com` に、メタデータサーバーのトークンを使って到達できる。`/proc/version` が gVisor のものになっている。結果を `evidence/YYYYMMDD-spike-egress.md` に記録する

## 3. Agent Runner コンテナ

- [ ] 3.1 `container/` に Dockerfile（node ベース、claude-code と Python venv、非 root）と requirements（`claude-agent-sdk`、`google-cloud-storage`）を作成する。`docker build` が成功することを確認する
- [ ] 3.2 `container/runner.py` に、環境変数の検証、GCS からの JSONL 読み込み、未応答行の抽出、書き戻しを実装する。不足している環境変数があると非ゼロで終了すること、未応答行だけが更新されることを、pytest（GCS は fake を使う）で確認する
- [ ] 3.3 Claude Agent SDK の呼び出しを実装する。Vertex の Haiku 4.5、`CLAUDE_CONFIG_DIR`、`HOME`、`cwd` を `/workspace` 配下に置くこと、直前行の `claude_session_id` を `resume` に渡すこと、D5 のツール構成、`skipWebFetchPreflight`、`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` を含める。SDK をモックした pytest で、オプションと resume の受け渡しを確認する
- [ ] 3.4 実行メタデータ（Downward API による Pod 名、UID、ノード名、`/proc/version`、実行前のワークスペースのファイル一覧と sha256、時刻、コスト）を記録する処理を実装する。pytest でファイル一覧の生成を確認する
- [ ] 3.5 `scripts/build_push.sh` で、Terraform の output からイメージ URI を組み立てて build・push する。`gcloud artifacts docker images list` でイメージが存在することを確認する

## 4. CLI

- [ ] 4.1 `pyproject.toml`（uv、`kubernetes`、`google-cloud-storage`、`typer`、pytest）と `cli/` パッケージを作成し、`uv run agent-sandbox-cli --help` が表示されることを確認する
- [ ] 4.2 設定の読み込み（Terraform の output から作る `.env` と環境変数）、セッション ID の発行、GCS の `input.jsonl` と `output.jsonl` の読み書きを実装する。セッション ID の形式と JSONL への追記を pytest で確認する
- [ ] 4.3 Sandbox manifest の生成を実装する。podTemplate（gVisor、`restartPolicy: Never`、label、KSA、環境変数、Downward API、`/workspace` のマウント、`fsGroup`）と `volumeClaimTemplates` を含める。あわせて、作成、再開（`replicas: 1`）、一時停止（`replicas: 0`）を実装する。生成した manifest のスナップショットを pytest で確認する
- [ ] 4.4 監視処理を実装する。Pod の watch、進捗表示、終了の検出、タイムアウト、異常時のログ末尾とイベントの表示を含める。Kubernetes クライアントをモックした pytest で、正常終了、異常終了、タイムアウトの分岐を確認する
- [ ] 4.5 `run`（新規と継続、応答とセッション ID の表示、`--verbose` での JSON 表示、存在しないセッションのエラー）、`delete`（Sandbox と PVC の削除）、`list` を実装する。実クラスタで新規実行、継続実行、削除を 1 回ずつ行い、動作を確認する

## 5. 検証

- [ ] 5.1 `scripts/validate.py` に Egress 検証を実装する。github.com/74th の要約が成功し、tohoho-web の要約が失敗することを判定する。同じ時間帯に、使い捨ての Sandbox から直接接続を試験する。実行し、両方の判定が期待どおりになることを確認する
- [ ] 5.2 `scripts/validate.py` に永続化検証を実装する。トークンの書き込み、同じセッションでの読み取り（Pod UID が変わっていること、実行前のファイル一覧にファイルがあること、トークンが一致すること、会話内容を覚えていること）、新しいセッションでファイルが見えないこと、を判定する。実行し、4 点すべてが成功することを確認する
- [ ] 5.3 カーネル分離の検証（`runtimeClassName` と `/proc/version`）を追加する。全項目の結果を `evidence/YYYYMMDD-validation.md` と JSON に保存し、ファイルにすべての判定が記録されていることを確認する

## 6. ドキュメントと後片付け

- [ ] 6.1 `README.md` に前提条件、構築手順、CLI の使い方、検証手順、スパイクで分かった制約（採用したライフサイクル方式、追加した FQDN、Agent Sandbox のバージョン）、破棄手順を記載する。記載したコマンドを順に実行し、README どおりに再現できることを確認する
- [ ] 6.2 検証が終わったら、ユーザーの承認を得て、全セッションの削除と `terraform destroy` を行う。`gcloud container clusters list` などで、この変更のリソースが残っていないことを確認し、結果を `evidence/` に記録する
