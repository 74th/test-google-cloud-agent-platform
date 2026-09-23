# Design

## Context

- このディレクトリには、まだ実装がない。既存の OpenSpec spec もない。
- 兄弟ディレクトリ `20260811-gke-isolated` で、GKE Dataplane V2、FQDNNetworkPolicy、Workload Identity（KSA principal への直接 IAM 付与）、Vertex AI 上の Claude Agent SDK（`claude-haiku-4-5@20251001`、`CLOUD_ML_REGION=global`）が動くことは確認済みである。Terraform の書き方、NetworkPolicy のメタデータサーバー許可ルール、Dockerfile（node ベースに claude-code と Python venv を入れる構成）は、そこを参考にする。
- GKE Agent Sandbox の中身は OSS の kubernetes-sigs/agent-sandbox で、`Sandbox` CRD（`agents.x-k8s.io/v1alpha1`）を提供する。`Sandbox` は「Pod 1 つ、安定した識別子、`volumeClaimTemplates` による永続ボリューム」を持つシングルトンで、Job ではない。gVisor によるカーネル分離は、GKE Sandbox ノードプールと `runtimeClassName: gvisor` で実現する。
- 対象プロジェクトは `nnyn-dev`、リージョンは `us-central1`、既存 VPC は `default` とする（兄弟ディレクトリと同じ）。

## Goals / Non-Goals

**Goals:**
- 「1 回実行して終了する」ワークロードを Sandbox で動かし、終了の検出、一時停止、再開のサイクルが成り立つことを確認する。
- Egress 制御、ワークスペース永続化、gVisor 分離の 3 点について、CLI 経由で自動判定できる検証を作る。

**Non-Goals:**
- SandboxWarmPool、SandboxTemplate、SandboxClaim によるプールや起動の高速化。これらは今回の検証対象外とする。
- 複数ユーザーでの同時利用、認可、マルチテナント分離。
- 本番運用を想定した監視、コスト最適化、CI。
- Agent Gateway（`common/`）との統合。

## Decisions

### D1. ワークロードは Sandbox + `restartPolicy: Never` で動かし、終了したら `replicas: 0` で一時停止する

Sandbox の `podTemplate` に `restartPolicy: Never` を指定し、Agent Runner が終了すると Pod が `Succeeded` または `Failed` になるようにする。CLI は Pod のコンテナ終了を検出したら、Sandbox の `spec.replicas` を 0 にして Pod を削除する。このとき PVC は残る。続きの対話では `replicas: 1` に戻し、新しい Pod で同じ PVC をマウントする。

- 代替案 A: Kubernetes Job と自前の PVC。Agent Sandbox を検証するという目的から外れるので採用しない。
- 代替案 B: Sandbox を常駐させて `kubectl exec` で実行する。要件にある「Job のように実行し、終了まで監視する」に合わず、環境変数で入力を指定する方式とも一致しないので採用しない。
- 前提（最初のスパイクで確認する）: コントローラが `restartPolicy: Never` を受け付けること、完了した Pod を勝手に再作成しないこと、`replicas` 0/1 による一時停止と再開に対応していること。どれかが成り立たない場合のフォールバックは次のとおり。セッションごとの PVC を CLI が先に作成し、`podTemplate.volumes` で参照する。そのうえで、実行のたびに Sandbox 自体を作成・削除する。この場合でも「Sandbox で実行する」「ワークスペースが残る」という spec は満たせる。ただし「Agent Sandbox の仕組みで永続化する」ことからは外れるので、証跡にその旨を明記する。

### D2. セッション ID と Kubernetes・GCS 上の名前の対応

- セッション ID は、CLI が発行する 12 桁の小文字 16 進数とする。DNS-1123 に適合させるため、この形式にしている。
- Sandbox 名は `agent-<session-id>`、PVC は `volumeClaimTemplates` の `workspace` から作られる名前を使う。Sandbox には label `agent-sandbox-validation/session=<id>` を付ける。
- GCS は `gs://<bucket>/sessions/<id>/input.jsonl` と `output.jsonl` を使う。環境変数 `INPUT_GCS_URI` と `OUTPUT_GCS_URI` はセッション内で固定なので、再開のときに podTemplate を変更する必要がない。
- 次のターンでは、CLI が `output.jsonl`（前回の結果）を読み、新しい行を追記して `input.jsonl` に書き込む。書き込み後に `replicas: 1` にする。
- セッションが存在するかどうかは、Sandbox リソースの有無で判定する。Claude SDK のセッション ID は CLI のセッション ID とは別物で、JSONL の各行に記録する。

### D3. JSONL の行スキーマ

```json
{"turn": 1, "prompt": "...", "created_at": "...",
 "response": "...", "claude_session_id": "...", "is_error": false,
 "meta": {"model": "claude-haiku-4-5@20251001", "pod_name": "...", "pod_uid": "...",
          "node_name": "...", "kernel": "<contents of /proc/version>", "runtime_class": "gvisor",
          "workspace_manifest_before": [{"path": "...", "sha256": "..."}],
          "started_at": "...", "finished_at": "...", "num_turns": 3, "cost_usd": 0.0}}
```

Runner は `response` がない行だけを処理する。その際、直前の行の `claude_session_id` を `resume` に渡す。Pod の情報は Downward API の環境変数から取得する。

### D4. 永続ワークスペースのレイアウト

PVC を `/workspace` にマウントし、次のように使う。

- `CLAUDE_CONFIG_DIR=/workspace/.claude`: SDK のセッション記録。`resume` が Pod をまたいで機能するために必要。
- `HOME=/workspace/home`
- エージェントの `cwd=/workspace/work`

PVC は `standard-rwo` の 1Gi とする。コンテナは非 root で実行し、`fsGroup` で書き込み権限を与える。

### D5. エージェントのツール構成

`allowed_tools` は `WebFetch`、`Read`、`Write`、`Edit`、`Glob`、`Bash` とする。`permission_mode` は `bypassPermissions`、`max_turns` は 10 程度にする。

- `20260811-gke-isolated` では Python 側で URL を事前取得していた。しかし今回は、エージェント自身がネットワークにアクセスして失敗する様子を見たいので、ツール経由で取得させる。
- WebFetch には、Anthropic の API にドメインの安全性を問い合わせる事前確認がある。これを通すと Egress 許可リストが広がるので、`skipWebFetchPreflight` を設定して無効化する。あわせて `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` を設定し、テレメトリなどの通信も止める。
- WebFetch が github.com の取得に使えない場合（たとえば事前確認を無効化できない場合）は、Bash の `curl` で取得するようシステムプロンプトで指示する。

### D6. Egress 制御は標準 NetworkPolicy + FQDNNetworkPolicy で行う

`20260811-gke-isolated` の構成を流用する。

- default deny の NetworkPolicy で、kube-dns（53/UDP・TCP）と、メタデータサーバー（`169.254.169.252/32` の 987・988、`169.254.169.254/32` の 80・8080）だけを許可する。
- FQDNNetworkPolicy で、`aiplatform.googleapis.com`、`storage.googleapis.com`、`github.com` の 443 を許可する。Vertex のエンドポイント名は global リージョンに合わせる。GitHub のリダイレクト先が必要になった場合は、spike の結果に応じて追加し、証跡に記録する。
- 対象の Pod は、Sandbox の podTemplate に付ける label `app=agent-runner` で選択する。
- 代替案として、Agent Gateway や Secure Web Proxy も考えられる。しかし今回はクラスタ内で完結する制御を確認したいので採用しない。

### D7. GKE の構成

- ゾーンクラスタ `agent-sandbox`（`us-central1-a`）を使う。`datapath_provider = ADVANCED_DATAPATH`、`enable_fqdn_network_policy = true`、Workload Identity を有効にする。
- ノードプールは 2 つ作る。1 つはシステム用の `system-pool`（`e2-standard-2` × 1）。もう 1 つは gVisor 用の `sandbox-pool`（`e2-standard-4` × 1、`sandbox_config { sandbox_type = "gvisor" }`、`GKE_METADATA`）。GKE Sandbox では gVisor ノードプールだけのクラスタは作れないので、2 つに分けている。
- Sandbox の podTemplate に `runtimeClassName: gvisor` を指定する。GKE が自動で付ける `sandbox.gke.io/runtime=gvisor` の nodeSelector と toleration も付ける。
- IAM は KSA principal に直接付与する（`principal://.../ns/agent-sandbox/sa/agent-runner`）。対象は `roles/aiplatform.user`（プロジェクト）と `roles/storage.objectUser`（バケット）の 2 つ。
- ワークロードの namespace は `agent-sandbox` とする。

### D8. Agent Sandbox コントローラの導入方法

kubernetes-sigs/agent-sandbox のリリース manifest を、バージョンを固定して `kubectl apply` するスクリプト（`scripts/install-agent-sandbox.sh`）で導入する。GKE のマネージド機能として有効化できる場合（クラスタのフラグやアドオンなど）は、そちらを優先する。どちらを使ったかは、最初のスパイクで決めて README に記録する。Terraform の kubernetes provider で CRD を管理する方法は、apply の順序や CRD の扱いが複雑になるので採用しない。

### D9. CLI の実装

- Python と uv を使う（兄弟ディレクトリに合わせる）。依存は `kubernetes`、`google-cloud-storage`、`typer`。
- サブコマンドは `run <prompt> [--session ID] [--timeout] [--verbose]`、`delete <session>`、`list` の 3 つ。
- 監視では Pod を watch し、`containerStatuses[].state.terminated` を検出する。ログは `read_namespaced_pod_log` で取得する。
- Kubernetes への接続は kubeconfig（`gcloud container clusters get-credentials`）、GCS へは ADC を使う。
- クラスタ名、namespace、バケット、イメージ URI は、Terraform の output から作った `.env` または環境変数で渡す。

### D10. 検証スクリプト

`scripts/validate.py` は CLI をサブプロセスとして呼び出し、`--verbose` の JSON を解析して判定する。

- **Egress:** `https://github.com/74th` の要約では、応答に `74th` とリポジトリに関する語が含まれることを確認する。`https://www.tohoho-web.com/` の要約では、取得失敗を示す内容であることを確認する。さらに、同じ時間帯に使い捨ての Sandbox（同じ label、同じ policy）で `curl` を直接実行し、tohoho は接続失敗、github は成功することを確認する。LLM の文章による判定はぶれることがあるので、この直接接続の結果を主な判定根拠にする。
- **永続化:** spec の 4 点を確認する。トークンは `secrets.token_hex(8)` で生成する。
- 結果は `evidence/YYYYMMDD-validation.md` と JSON に保存する。

## Risks / Trade-offs

- [Agent Sandbox コントローラが `restartPolicy: Never` や完了した Pod に対応していない] → 最初にスパイク（tasks 2.x）で確かめ、だめなら D1 のフォールバックに切り替える。
- [gVisor 上で Node.js や Claude Code が動かない、または遅い] → スパイクで `claude --version` と簡単なクエリを実行して確認する。
- [gVisor の Pod で FQDNNetworkPolicy やメタデータサーバーが効かない] → スパイクで GCS と Vertex の呼び出しと、未許可の宛先への curl を確認する。
- [WebFetch の事前確認やリダイレクトで、許可した github.com でも取得に失敗する] → D5 の設定と Bash curl へのフォールバックで対処する。追加した FQDN は証跡に記録する。
- [LLM の応答による成否判定がぶれる] → 直接接続試験とメタデータ（ファイル一覧、Pod UID）による機械的な判定を主にする。
- [ノード 2 台分のコストが続く] → 検証が終わったら `terraform destroy` とセッション削除を行う手順を README に書く。

## Migration Plan

新規構築なので、移行作業はない。

作業の順序: Terraform の plan を確認して apply する → Agent Sandbox を導入する → イメージを build・push する → namespace、KSA、NetworkPolicy を適用する → スパイクを行う → CLI を実装する → 検証を実行する → 証跡を保存する → destroy する。

切り戻しは、セッションの一括削除と `terraform destroy` で行う。

## Open Questions

- Agent Sandbox のどのバージョンを固定するか。導入時点の最新の安定リリースを選び、README に記録する。
- github.com の要約に、`github.com` 以外の FQDN（`avatars.githubusercontent.com` など）が必要かどうか。スパイクで確認し、必要なら最小限だけ追加する。
