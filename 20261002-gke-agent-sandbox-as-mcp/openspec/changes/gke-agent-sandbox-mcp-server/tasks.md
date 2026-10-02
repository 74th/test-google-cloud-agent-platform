# Tasks

## 1. Terraform 基盤

- [ ] 1.1 `terraform/` に `.gitignore`（`terraform.tfvars`、`*.tfstate*`、`.terraform/`、`.envrc`）、`.terraform-version`、`versions.tf`（`hashicorp/google` / `google-beta` のバージョン範囲を明示）、`providers.tf`、`variables.tf`、`terraform.tfvars.example`（`project_id = "nnyn-dev"`）を作成し、`terraform init && terraform validate` が通ることを確認する
- [ ] 1.2 `main.tf` に、必要な API の有効化（`disable_on_destroy = false`）、既存 VPC `default` と subnet の data 参照、ゾーンクラスタ `agent-sandbox-mcp`（Standard、`ADVANCED_DATAPATH`、FQDN Network Policy、Workload Identity、`deletion_protection = false`）を日本語コメント付きで定義し、`terraform validate` が通ることを確認する
- [ ] 1.3 `system-pool`（`e2-standard-2` × 1）と `sandbox-pool`（`e2-standard-4` × 1、`sandbox_config { sandbox_type = "gvisor" }`、`GKE_METADATA`）を定義し、`terraform validate` が通ることを確認する
- [ ] 1.4 GKE のマネージド機能で Agent Sandbox を有効化できるかを調べ、できる場合はクラスタ定義に追加する。調査結果をメモし、1.6 の evidence に含める
- [ ] 1.5 `registry.tf`（Artifact Registry）、`iam.tf`（必要な IAM がなければコメントのみ）、`outputs.tf`（クラスタ名、ゾーン、プロジェクト、イメージリポジトリ）を作成し、`terraform fmt -check && terraform validate` が通ることを確認する
- [ ] 1.6 `terraform plan -out=tfplan` を実行し、作成対象がこの変更のリソースだけで既存 VPC、`common/`、兄弟ディレクトリに変更・削除がないことを確認してから `terraform apply tfplan` する。`gcloud container clusters describe`、`kubectl get nodes -o wide`、`kubectl get runtimeclass gvisor` の結果を `evidence/YYYYMMDD-infrastructure.md` に保存する
- [ ] 1.7 Terraform の output から `.env` を生成する手順（スクリプトまたは README のコマンド）を用意し、生成した `.env` にクラスタ名、ゾーン、イメージリポジトリが含まれることを確認する

## 2. Agent Sandbox の導入と仕様確認

- [ ] 2.1 マネージド機能が使えない場合は、kubernetes-sigs/agent-sandbox の最新安定リリースを選び、core と extensions の manifest をバージョン固定で適用する `scripts/install-agent-sandbox.sh` を作成して実行する。`kubectl get crd | grep agents` で 4 種類の CRD があり、コントローラ Pod が Ready であることを確認する
- [ ] 2.2 GKE、コントローラ、Agent Sandbox API、各 CRD のバージョン、既定の StorageClass と `standard-rwo` の存在を記録し、`kubectl explain` で `sandbox.spec`、`sandboxclaim.spec`、`sandboxtemplate.spec`、`sandboxwarmpool.spec` を確認する。`operatingMode`、`shutdownTime` / `shutdownPolicy`、`volumeClaimTemplates`、claim の `env` の有無とドキュメントとの差異を `evidence/YYYYMMDD-crd-spec.md` に保存する

## 3. Kubernetes マニフェストとイメージ

- [ ] 3.1 `k8s/namespace.yaml`（`agent-sandbox`）と `k8s/service-account.yaml`（`sandbox-runner` と `mcp-server`）を作成・適用し、`kubectl get sa -n agent-sandbox` で 2 つの KSA があることを確認する
- [ ] 3.2 `k8s/network-policy.yaml`（Sandbox Pod の label を対象に default deny + kube-dns + メタデータサーバー）と `k8s/fqdn-network-policy.yaml`（`github.com` の 443）を作成し、`kubectl apply --dry-run=server` が通ることを確認してから適用する
- [ ] 3.3 `container/Dockerfile`（Python slim、非 root、`bash`、`coreutils`、`procps`、`util-linux`、`ripgrep`、`/opt/tools/internal_tool.py`。`/opt/tools/apply_patch` は 5.6 で追加する）を作成し、`scripts/build_push.sh` で Terraform の output からイメージ URI を組み立てて build・push する。`gcloud artifacts docker images list` でイメージがあることを確認する
- [ ] 3.4 `k8s/sandbox-template.yaml` に SandboxTemplate（gVisor、nodeSelector・toleration、非 root、`fsGroup`、Sandbox 用 label、`/workspace` の `volumeClaimTemplates`、常駐プロセス）を作成・適用し、`kubectl get sandboxtemplate -n agent-sandbox` で存在を確認する

## 4. 手動検証（MCP Server を書く前）

- [ ] 4.1 kubectl で `env: USER_EMAIL` 付きの SandboxClaim を作り、Sandbox と PVC の作成、Pod の `runtimeClassName` と `/proc/version`、`id -u` が 0 以外であること、`echo $USER_EMAIL` と `python /opt/tools/internal_tool.py` の出力、Claim・Sandbox・PVC の ownerReference を確認する。cold start の時間を計測し、`evidence/YYYYMMDD-manual-claim.md` に保存する
- [ ] 4.2 `/workspace/test.txt` に書き込んでから `operatingMode: Suspended` に patch し、Pod が削除され PVC が残ることを確認する。`Running` に戻して新しい Pod で `cat /workspace/test.txt` が `hello` になること、`USER_EMAIL` が変わらないことを確認する。Resume の時間を計測し、`evidence/YYYYMMDD-manual-suspend-resume.md` に保存する
- [ ] 4.3 `shutdownTime` / `shutdownPolicy` を近い時刻に設定して期限到達時の挙動（Delete か、PVC が残るか）を確認し、`shutdownTime` の更新で期限が延長できるかを確認する。方式 1 と方式 2 の比較を `evidence/YYYYMMDD-manual-shutdown-time.md` に保存し、design.md D6 の採用方式を確定する
- [ ] 4.4 Claim を削除したときに Sandbox、Pod、PVC が削除されるかを確認し、PVC の明示削除が必要かを確定する（design.md D10）。Claim の annotation が MCP Server から patch でき、コントローラに上書きされないことも確認する。結果を `evidence/YYYYMMDD-manual-delete.md` に保存する
- [ ] 4.5 SandboxWarmPool を作り、`env` なしの claim と `env` ありの claim でそれぞれ WarmPool の Pod が adopt されるかと起動時間を計測し、`evidence/YYYYMMDD-manual-warmpool.md` に保存する
- [ ] 4.6 `k8s-agent-sandbox` SDK をインストールし、claim の作成・取得、suspend / resume、コマンド実行の API を確認する。SDK のコマンド実行がバックグラウンド実行と逐次の出力取得に対応し、クラスタ内の Deployment から使えるかを判断する（design.md D9）。結果を `evidence/YYYYMMDD-manual-sdk.md` に保存する
- [ ] 4.7 小さな Python スクリプトで、kubernetes クライアントの exec（`_preload_content=False`）により Sandbox 内で `setsid` 付きのプロセスを起動し、出力の逐次読み出し、stdin への書き込み（`tty` あり / なし）、status チャネルからの終了コード取得、idle timeout より長い接続の保持、接続を切ったときに Sandbox 内のプロセスがどうなるかを確認する。結果を `evidence/YYYYMMDD-manual-exec.md` に保存する
- [ ] 4.8 手動検証の結果が design.md の暫定の決定（D3、D4、D6、D9、D10）と違う場合は design.md を更新し、要件を満たせない点があればユーザーに確認する。更新した決定が evidence と一致していることを確認する

## 5. MCP Server の実装

- [ ] 5.1 `pyproject.toml`（Python 3.12 以上、`mcp` v2、`k8s-agent-sandbox`、`kubernetes`、設定・テスト用ライブラリをバージョン明示）を作成して `uv lock` し、インストールした `mcp` パッケージのソースで `MCPServer`、Streamable HTTP、画像コンテンツの返し方、ASGI アプリへの REST ルートの追加方法を確認する。`uv run python -c "import agent_sandbox_mcp"` が通ることを確認する
- [ ] 5.2 `config.py`（design.md D13 の環境変数）と `logging.py`（構造化ログ、`user_hash` のみ出力）を実装し、設定の既定値と上限チェックを pytest で確認する
- [ ] 5.3 `naming.py`（`session_id` と `user_email` の検証、claim 名の生成）と `binding.py`（HMAC の計算、`compare_digest` による比較、`user_hash`）を実装し、claim 名の決定性、不正な `session_id` の拒否、binding 一致・不一致を pytest で確認する
- [ ] 5.4 `k8s_backend.py` を実装する。SandboxClaim の作成（`env`、annotation、`shutdownTime`）・取得・削除、`operatingMode` の patch、Ready 待ち、annotation の更新、PVC の確認と削除、exec の起動（ストリームを返す）を含める。単体テスト用のフェイク実装も用意し、実クラスタに対して作成・exec・Suspend・Resume・削除を 1 回ずつ行う小さなスクリプトで動作を確認する
- [ ] 5.5 `processes.py` を実装する。exec の接続の保持と読み出しスレッド、出力のリングバッファ、`process_id` の払い出しとセッションとの対応づけ、`yield_time_ms` までの待機、前回以降の出力の返却、終了コードの取得、`max_output_tokens` による切り詰めと `original_token_count`、最大実行時間での停止、セッションあたりの上限を含める。フェイクの exec を使った pytest で、すぐ終わる場合、yield して `process_id` を返す場合、ポーリングで完了を受け取る場合、別セッションの `process_id` の拒否、切り詰め、最大実行時間を確認する
- [ ] 5.6 `container/tools/apply_patch`（Codex のパッチ形式の解析と、全 hunk を確認してからの適用、`/workspace` 基準の相対パス、Codex と同じ形式の結果）を実装し、Codex の `apply-patch` のテストケースを参考にした pytest で、追加・更新・削除・移動、文脈の不一致で何も書き込まれないこと、不正な形式のエラーを確認する。Sandbox イメージに入れて build・push し直す
- [ ] 5.7 `manager.py` を実装する。セッション単位のロック、取得または作成、binding 確認、Resume、処理中のツール呼び出しの数、heartbeat、`last-activity` の更新、状態の取得、削除（実行中のプロセスの停止を含む）を含める。フェイクの backend を使った pytest で、binding 不一致では backend を操作しないこと、Suspended なら Resume すること、例外でも処理中の数が戻ることを確認する
- [ ] 5.8 `tools.py` に `exec_command`、`write_stdin`、`apply_patch`（exec で `/opt/tools/apply_patch` に stdin で渡す）、`view_image`（サイズ確認、base64 での読み出し、マジックバイトによる判定）、`delete_workspace` を実装する。フェイクの backend を使った pytest で、入出力の形式が design.md D9 の表どおりであること、`view_image` の形式・サイズのエラーを確認する
- [ ] 5.9 `lifecycle.py` に idle Suspend ループと GC ループを実装する。pytest で、実行中のプロセスや処理中のツール呼び出しがある間は Suspend しないこと、最後のプロセスの終了と最後のツール呼び出しの完了の遅いほうから判定すること、Suspend 直前に再確認すること、retention 経過で削除し実行中は削除しないこと、PVC が残らないことを確認する
- [ ] 5.10 `rest_api.py`（`POST /api/v1/workspace-status`、`/healthz`）と `server.py`（`MCPServer` と 5 つのツール、lifespan でのループの起動・停止）を実装する。pytest で REST API の応答（Sandbox を作らない、binding 不一致で 403、内部情報を返さない）を確認し、ローカルで起動して MCP クライアントからツール一覧が 5 つ返り `workspace_status` が含まれないことを確認する
- [ ] 5.11 MCP Server のログ、ツールのエラー応答、REST API の応答に生メールアドレスが含まれないことを、ログをキャプチャする pytest で確認する。`uv run pytest` がすべて成功することを確認する

## 6. デプロイ

- [ ] 6.1 リポジトリ直下の `Dockerfile`（uv、非 root）を作成し、`scripts/build_push.sh` で MCP Server のイメージも build・push できるようにする。push したイメージが Artifact Registry にあることを確認する
- [ ] 6.2 `k8s/mcp-server-rbac.yaml`（Namespace 内の Sandbox 関連リソース、PVC、Pod の get/list/watch、`pods/exec`、binding 用 Secret の get のみ）を作成・適用し、`kubectl auth can-i --as=system:serviceaccount:agent-sandbox:mcp-server` で必要な操作が `yes`、別 Namespace と不要な操作が `no` になることを確認する
- [ ] 6.3 binding 用 Secret の作成手順と、`k8s/mcp-server.yaml`（Deployment `replicas: 1`、`strategy: Recreate`、環境変数、probe、ClusterIP Service）を作成・適用し、Pod が Ready で、`kubectl port-forward` 経由でツール一覧と REST API の応答が取得できることを確認する

## 7. E2E 検証と計測

- [ ] 7.1 `scripts/validate.py` を実装する。LLM は使わず、`mcp` SDK のクライアントで port-forward 先に接続してツールを直接呼び出し、REST API も直接呼び出して、spec の E2E 13 項目を順に判定する。kubectl / kubernetes クライアントで Sandbox・Pod・PVC の状態とログ・label・annotation も確認する。結果を `evidence/YYYYMMDD-e2e.md` と JSON に保存する
- [ ] 7.2 idle timeout（例: 120 秒）と retention（例: 300 秒）を短くした設定で MCP Server をデプロイし、`scripts/validate.py` を実行して 13 項目すべてが成功することを確認する。失敗した項目は原因を直して再実行する
- [ ] 7.3 MCP Server 経由での cold start（新規セッションの最初の `exec_command`）と Resume の時間を計測し、4.5 の WarmPool の結果とあわせて `evidence/YYYYMMDD-measurements.md` に保存する

## 8. ドキュメントと後片付け

- [ ] 8.1 `README.md` に構成図と各コンポーネントの責務、MCP ツールと Codex のツールの対応と差異（合わせた Codex のコミットを含む）、REST API の仕様、バージョンと CRD 仕様の確認結果（ドキュメントとの差異を含む）、構築・デプロイ・削除（`terraform destroy`）の手順、環境変数の一覧、idle Suspend 方式の比較と採用理由、計測結果、Resume 後と MCP Server の再起動後は `/workspace` のファイルだけが残る（実行中の `process_id` も失われる）前提、手作業が必要だった箇所、production へ向けた残課題（複数 replica 化、認証、NetworkPolicy、監視など）を記載する。記載したコマンドが実際に使ったものと一致していることを確認する
- [ ] 8.2 検証用の SandboxClaim と PVC が残っていないことを確認し、`terraform destroy` を実行するかをユーザーに確認する（勝手に削除しない）。承認された場合は destroy 後に `gcloud container clusters list` でクラスタが残っていないことを確認し、結果を `evidence/` に記録する
