# Design

## Context

- このディレクトリには、まだ実装も既存の OpenSpec spec もない。動機は proposal.md の Why を参照。
- 以前の検証 `../20260923-gke-agent-sandbox` は設計（openspec）だけで実装はない。基盤の構成は、その design の D4（ワークスペース）、D6（Egress）、D7（GKE 構成）、D8（コントローラの導入）と tasks 1.x〜2.x に合わせる。Terraform の書き方は `../20260811-gke-isolated/terraform` を参考にする。
- 以前の検証は `Sandbox` を直接作って `replicas: 0/1` で一時停止する設計だったが、今回は SandboxTemplate / SandboxClaim / SandboxWarmPool を使い、`operatingMode`（Running / Suspended）でライフサイクルを制御する。
- Agent Sandbox の CRD（`v1beta1` を優先）、`k8s-agent-sandbox` SDK、`mcp` Python SDK v2 の API は、ドキュメントと実装が一致しない可能性がある。API 名・フィールド名は、実クラスタの CRD とインストールしたパッケージのソースで確かめてから使う。本書に出てくる SDK の関数名は概念上の名前である。
- 対象は `nnyn-dev` / `us-central1-a` / 既存 VPC `default`。`terraform apply` と `kubectl` による変更は許可されているが、このディレクトリで作ったもの以外は変更しない。

## Goals / Non-Goals

**Goals:**
- Kubernetes リソースを唯一の永続状態とし、MCP Server を再起動してもセッションの binding、最終 activity、予定時刻が失われない構造にする。
- 方式の判断（idle Suspend の方式、PVC の削除方法、コマンドの実行経路）は、実装前の手動検証の結果で確定させる。

**Non-Goals:**
- MCP Server の複数 replica 化、leader election、高可用性。課題を README に記載するだけにする。
- MCP クライアントの認証・認可（今回は `kubectl port-forward` 経由でのみ公開する）。`user_email` は MCP クライアントの申告をそのまま信頼する。
- プロセスやメモリの snapshot（GKE Pod Snapshot）。Resume 後は `/workspace` のファイルだけが残る。
- Sandbox Pod から Vertex AI や GCS を使うこと。GCS バケットと `roles/aiplatform.user` は作らない。
- 監視、メトリクス、CI。
- 検証で LLM を使うこと。検証の対象は MCP Server なので、決まった引数でツールを呼ぶスクリプトだけで判定する。
- Codex の承認の仕組み（`sandbox_permissions`、`justification`、`prefix_rule`）と複数環境（`environment_id`）。Sandbox 自体が分離された実行環境なので不要。

## Decisions

### D1. 基盤は以前の検証の構成をそのまま使い、差分だけ変える

以前の D7 の構成（ゾーンクラスタ、Dataplane V2、FQDN Network Policy、Workload Identity、`system-pool` と `sandbox-pool` の 2 プール、gVisor）を使う。差分は次のとおり。

- クラスタ名は `agent-sandbox-mcp`。
- 有効化する API は container、artifactregistry、iam、sts など必要なものだけにする。aiplatform と storage は使わない。
- KSA は 2 つ。Sandbox Pod 用の `sandbox-runner`（IAM なし、`automountServiceAccountToken: false`）と、MCP Server 用の `mcp-server`（Kubernetes RBAC のみ）。
- `iam.tf` は、必要な IAM がなければ空（コメントのみ）にする。

Terraform は GCP リソースだけを扱い、CRD、SandboxTemplate、RBAC などは `k8s/` のマニフェストを `kubectl apply` で適用する（以前の D8 と同じ。kubernetes provider で CRD を扱うと apply 順序が複雑になるため）。

以前の設計と違う構成にしたほうがよいと分かった場合は、勝手に変えず、理由を README に書いてユーザーに確認する。

### D2. コントローラは「マネージド機能 → バージョン固定スクリプト」の順で導入する

GKE のマネージド機能（クラスタのアドオンやフラグ）で Agent Sandbox を有効化できるかを最初に調べ、できればそれを Terraform で有効化する。できなければ、kubernetes-sigs/agent-sandbox のリリース manifest（core と extensions。SandboxClaim / SandboxTemplate / SandboxWarmPool は extensions 側）を、バージョンを固定して適用する `scripts/install-agent-sandbox.sh` を作る。どちらを使ったかと、選んだバージョンを README に記録する。

### D3. セッションごとに SandboxClaim を 1 つ作り、共通の SandboxTemplate を参照する

- `k8s/sandbox-template.yaml` に SandboxTemplate を 1 つ定義する。中身は、Sandbox Pod 用イメージ、`runtimeClassName: gvisor`、gVisor の nodeSelector と toleration、非 root の `securityContext`、`fsGroup`、`app=agent-sandbox-session` などの label（NetworkPolicy の対象）、`/workspace` の `volumeClaimTemplates`（`standard-rwo`、1Gi、RWO）。
- コンテナは常駐プロセス（`sleep infinity` 相当）で起動し、コマンドは後から実行する。
- セッションごとに SandboxClaim を作る。名前は `sandbox-session-` + `sha256(session_id)[:20]`。claim の `env` に `USER_EMAIL` を入れる。
- `session_id` は `^[A-Za-z0-9_-]{1,128}$` に制限する（値は設定で変更できる）。
- `volumeClaimTemplates` を Template 側と Claim 側のどちらに書けるかは、実クラスタの CRD で確認して決める。

代替案: Sandbox を直接作る（以前の検証と同じ）。SandboxClaim の `env` と WarmPool を使えず、今回の検証目的から外れるので採用しない。ただし claim の `env` や `operatingMode` が Claim 経由で扱えない場合は、MCP Server が Claim から作られた Sandbox を直接 patch する。

### D4. `USER_EMAIL` は per-claim `env` で注入する

claim の `env` で Pod の環境変数として `USER_EMAIL` を渡すので、`exec_command` 以外のプロセス（`/opt/tools/internal_tool.py` など）からも参照でき、Suspend / Resume 後も同じ値になる。

- 現行実装では `env` を指定した claim は WarmPool の Pod を adopt できず cold start になる。WarmPool あり / なしの起動時間を計測して README に書く。検証段階では起動速度よりユーザー分離を優先し、WarmPool は計測のためだけに作る。
- 代替案: exec のたびに `env USER_EMAIL=... sh -c` で渡す。`exec_command` 以外のプロセスから見えないので採用しない。claim の `env` が実クラスタで使えない場合は、この案を含めて方式をユーザーに確認する。

### D5. binding と状態は SandboxClaim の annotation に保存する

SandboxClaim に次の annotation を付ける（prefix は `mcp.agent-sandbox.74th.tech/`）。

| annotation | 内容 |
| --- | --- |
| `user-hmac` | `HMAC-SHA256(key, user_email)` の 16 進文字列 |
| `created-at` | 作成時刻（RFC 3339、UTC） |
| `last-activity` | 最後の active コマンドの完了時刻、または実行中の heartbeat 時刻 |

- HMAC の鍵は Kubernetes Secret（`mcp-server-binding-key`）から環境変数またはファイルで読み込む。Secret はランダム値で手動作成する手順を README に書き、リポジトリには入れない。
- 比較は `hmac.compare_digest` で行う。
- ログ用の `user_hash` は HMAC の先頭 12 文字にする。単純な SHA-256 はメールアドレスの総当たりで復元できるので使わない。
- Suspend 予定時刻と削除予定時刻は `last-activity` から計算して返すので、保存しない。
- 代替案: ConfigMap や外部 DB に保存する。Claim の削除と状態の削除がずれる問題があり、外部依存も増えるので採用しない。

### D6. idle Suspend は MCP Server が `operatingMode` を変更し、`shutdownTime` は安全網にする（暫定。手動検証で確定）

方式を 2 つ比較する。

1. `shutdownTime` を「最終 activity + idle timeout」に更新し続ける。期限到達時の動作は `shutdownPolicy` に依存し、現行のポリシーは Delete（または Retain）が中心で「Suspend にする」ことはできない見込み。Delete では PVC まで消える可能性があり、要件（idle 時は Suspend）を満たせない。
2. MCP Server が idle を判定して `operatingMode: Suspended` に patch する。実行中のコマンド数を考慮でき、要件どおりに Suspend にできる。

方式 2 を暫定で採用する。そのうえで、MCP Server が止まっていた場合の安全網として、`shutdownTime` を「最終 activity + retention + 余裕（例: 1 日）」に設定し、activity の更新時に一緒に延長する。安全網が Delete で働いた場合に PVC が残るかどうかは手動検証で確認し、残る場合は README に「孤立 PVC が残りうる」と記載する。手動検証で `shutdownPolicy` の挙動が想定と違えば、ここを見直す。

idle 判定のループは `SANDBOX_IDLE_CHECK_INTERVAL_SECONDS` ごとに Namespace 内の Claim を一覧し、次を満たすものを Suspend する。

- 実行中のコマンド数が 0
- `now - last-activity >= SANDBOX_IDLE_TIMEOUT_SECONDS`
- 状態が Running

Suspend / Resume の操作は、SDK に suspend / resume があればそれを使い、なければ kubernetes クライアントで `spec.operatingMode` を merge patch する。

### D7. 実行中のプロセス数はプロセス内で数え、heartbeat で annotation を更新する

- セッションごとに「`exec_command` で起動してまだ終了していないプロセス」の一覧（D9 のプロセス管理）と、処理中のツール呼び出しの数をプロセス内に持つ。ツール呼び出しの数は、開始時に +1、終了時（例外を含む）に `finally` で -1 する。
- プロセスが 1 つ以上ある間は、`SANDBOX_ACTIVITY_HEARTBEAT_SECONDS`（例: 60 秒）ごとに `last-activity` を現在時刻に更新する。プロセスの終了時と、すべてのツール呼び出し（`exec_command`、`write_stdin`、`apply_patch`、`view_image`）の完了時にも更新する。そのため idle timeout の起点は「最後のプロセスの終了」と「最後のツール呼び出しの完了」の遅いほうになる。MCP クライアントが `write_stdin` でポーリングしていなくても、プロセスが動いていれば Suspend しない。
- heartbeat を annotation にも書くのは、MCP Server が長いプロセスの途中で再起動した場合でも、すぐに Suspend や GC の対象にならないようにするため。
- GC も、実行中のプロセスと処理中のツール呼び出しがないセッションだけを対象にする。
- プロセス内の状態があるため MCP Server は 1 replica にする（Deployment の `replicas: 1`、`strategy: Recreate`）。複数 replica にするには、プロセスを持つ replica へのルーティング（`process_id` と replica の対応づけ）、実行中のプロセス数の共有（Lease など）、idle / GC ループの leader election が必要になる。これは README に課題として記載する。

### D8. 同じセッションへの操作はセッション単位のロックで直列化する

作成、Resume、Suspend、削除が並行して走ると状態が壊れるので、claim 名ごとの `asyncio.Lock` で直列化する。ロックの範囲は「Claim の取得・作成・Resume・Ready 待ち」と「Suspend」「削除」に限定し、ツールの処理そのもの（プロセスの実行、パッチの適用、画像の読み出し）はロックの外で行う。同じセッションでの並行実行は許可する。idle ループは Suspend の直前に、ロックを取ったうえで実行中のプロセス数、処理中のツール呼び出しの数、`last-activity` を再確認する。

### D9. ツールは Codex の入出力に合わせ、コマンドは exec の接続を MCP Server が保持して実行する

Coding Agent のワークスペース操作としてそのまま使えるよう、Codex（`openai/codex` の `codex-rs/core/src/tools/`）の既定のワークスペース操作ツールに合わせる。Codex には `read_file` や `grep` に当たる既定のツールがなく、読み取りや検索は `exec_command` から `rg` や `sed` で行うので、それに倣う。

| ツール | Codex との違い |
| --- | --- |
| `exec_command` | `session_id` / `user_email` を追加する。承認関連の入力と `environment_id` は除く。出力の `session_id` を `process_id` に改名する |
| `write_stdin` | 入力の `session_id`（プロセス）を `process_id` に改名し、ワークスペースの `session_id` / `user_email` を追加する |
| `apply_patch` | Codex はフリーフォーム（Lark 文法）のツールだが、MCP のツールは JSON の引数なので、Codex の JSON 版と同じくパッチ本文を `input: string` で受け取る |
| `view_image` | `detail` と `environment_id` は除く。MCP の画像コンテンツで返す |

**プロセス管理（`exec_command` / `write_stdin`）**

- `exec_command` を受けると、Sandbox が Ready になる（Pod が Running でコンテナが Ready）まで `SANDBOX_READY_TIMEOUT_SECONDS` を上限に待つ。そのうえで、kubernetes クライアントの exec（`connect_get_namespaced_pod_exec`、`_preload_content=False`）で `<shell> [-l] -c <cmd>` を `workdir` で起動する。`tty=true` なら exec の TTY を有効にする。
- MCP Server はプロセスごとに exec の WebSocket を保持し、読み出し用スレッドで stdout / stderr を受け取った順に 1 本のリングバッファ（上限 `EXEC_OUTPUT_BUFFER_BYTES`）へ書き込む。終了コードは exec の status チャネルから取得する。
- `exec_command` と `write_stdin` は、`yield_time_ms` まで、またはプロセスが終了するまで待ってから、前回以降の新しい出力を返す。終了していれば `exit_code` を返してプロセスを一覧から外す。終了していなければ `process_id` を返す。
- `process_id` は MCP Server 内で単調に増える整数とし、セッション（claim 名）と対応づける。`write_stdin` では、`process_id` がそのセッションのものであることを確認する。
- 出力は Codex と同じく、おおよそ 4 バイト = 1 トークンとして `max_output_tokens` で切り詰め（先頭と末尾を残す）、`original_token_count` を返す。`max_output_tokens` の上限は `EXEC_MAX_OUTPUT_TOKENS`。
- プロセスの最大実行時間は `EXEC_MAX_PROCESS_SECONDS`、セッションあたりの同時実行プロセス数の上限は `EXEC_MAX_PROCESSES_PER_SESSION` とする。最大実行時間を超えたプロセスは、`pkill` などで Sandbox 内のプロセスグループを止める。そのため、コマンドは `setsid` で新しいプロセスグループとして起動し、PID をファイルに記録する。
- `k8s-agent-sandbox` SDK のコマンド実行が、バックグラウンド実行と逐次の出力取得に対応していて、クラスタ内の Deployment から使える場合は、SDK に置き換えることを検討する。手動検証（tasks 4.6）で判断し、README に記録する。

**`apply_patch`**

- パッチの解析と適用は、Sandbox イメージに入れた `/opt/tools/apply_patch` スクリプトで行う。MCP Server は exec でこのスクリプトを起動し、パッチ本文を stdin で渡す。Pod 内で非 root ユーザーとして適用されるので、ファイルの所有者と権限が `exec_command` で作ったファイルと同じになる。
- スクリプトは Codex のパッチ形式（`apply_patch.lark` の文法）を解析し、すべての hunk の適用先と文脈を確認してから書き込む。どれか 1 つでも失敗したら何も書き込まずにエラーにする。相対パスは `/workspace` を基準に解決する。
- 成功時は Codex と同じく `Success. Updated the following files:` に続けて `A path` / `M path` / `D path` の一覧を返す。
- 代替案: MCP Server がファイルを exec で読み書きしてパッチを適用する。読み書きの往復が増え、途中で失敗したときに部分的な書き込みが残りやすいので採用しない。

**`view_image`**

- exec で `stat` によりサイズを確認し、`VIEW_IMAGE_MAX_BYTES` 以下なら `base64` で読み出す。先頭のマジックバイトで PNG / JPEG / GIF / WebP を判定し、それ以外はエラーにする。

### D10. 削除では PVC が残らないことを保証する

`delete_workspace` と GC では、SandboxClaim を削除したあと、ownerReference による PVC の削除を待つ。PVC に ownerReference がない場合（手動検証で確認する）は、claim 名に対応する PVC を label または名前で特定して明示的に削除する。最後に PVC が消えたことを確認してから結果を返す。

### D11. MCP Server は `mcp` SDK v2 の `MCPServer` と Streamable HTTP で作り、状態は REST API で返す

- 古い `FastMCP` ベースの記事は使わず、インストールした `mcp` パッケージのソースと公式ドキュメントで現行 API を確認する。
- MCP ツールは `exec_command`、`write_stdin`、`apply_patch`、`view_image`、`delete_workspace` の 5 つ。出力の形式は D9 のとおり Codex に合わせる。binding 不一致やバリデーションエラーは MCP のツールエラーとして返し、エラーの内容にもメールアドレスを含めない。
- ワークスペースの状態は MCP ツールにせず、同じ ASGI アプリに `POST /api/v1/workspace-status` を追加して返す。メールアドレスが URL やアクセスログに残らないよう、`session_id` と `user_email` は JSON の body で受け取る。binding が一致しなければ 403 を返す。今回は認証を付けず、port-forward 経由でのみ使う。
- `/healthz` を用意し、Deployment の probe に使う。Service は ClusterIP とし、検証では `kubectl port-forward` で接続する。
- idle ループと GC ループは、サーバーの lifespan で起動・停止する。停止時は保持しているプロセスの exec 接続を閉じる。

### D12. モジュール構成

```text
src/agent_sandbox_mcp/
  config.py       # 環境変数の読み込み（pydantic-settings など）
  naming.py       # session_id の検証と claim 名の生成
  binding.py      # HMAC の計算と比較、user_hash
  k8s_backend.py  # SandboxClaim / Sandbox / PVC の操作と exec の起動（SDK と kubernetes クライアントを隠蔽）
  processes.py    # exec の接続とバッファ、process_id の管理、yield、出力の切り詰め、最大実行時間
  manager.py      # セッションの取得・作成・Resume・削除、ロック、処理中のツール呼び出しの数、activity の更新
  tools.py        # exec_command / write_stdin / apply_patch / view_image / delete_workspace の処理
  lifecycle.py    # idle Suspend ループと GC ループ
  rest_api.py     # POST /api/v1/workspace-status と /healthz
  server.py       # MCPServer とツール定義、ASGI アプリの組み立て
  logging.py      # 構造化ログ（メールアドレスを出さない）
container/
  Dockerfile
  tools/apply_patch     # Codex 形式のパッチを適用するスクリプト（Python）
  tools/internal_tool.py
```

`k8s_backend` と `processes` の exec 部分をインターフェースとして切り出し、単体テストではフェイク実装に差し替える。`container/tools/apply_patch` は単体で pytest できるようにする。

### D13. 環境変数

| 変数 | 既定値 | 用途 |
| --- | --- | --- |
| `SANDBOX_NAMESPACE` | `agent-sandbox` | 対象 Namespace |
| `SANDBOX_TEMPLATE_NAME` | `agent-sandbox-session` | 参照する SandboxTemplate |
| `SANDBOX_IDLE_TIMEOUT_SECONDS` | `1800` | idle Suspend までの時間 |
| `SANDBOX_IDLE_CHECK_INTERVAL_SECONDS` | `30` | idle 判定の間隔 |
| `SANDBOX_ACTIVITY_HEARTBEAT_SECONDS` | `60` | 実行中の activity 更新間隔 |
| `SANDBOX_WORKSPACE_RETENTION_SECONDS` | `604800` | GC までの時間 |
| `SANDBOX_GC_INTERVAL_SECONDS` | `3600` | GC の間隔 |
| `SANDBOX_SAFETY_NET_MARGIN_SECONDS` | `86400` | `shutdownTime` の安全網の余裕 |
| `SANDBOX_READY_TIMEOUT_SECONDS` | `300` | 作成・Resume の Ready 待ちの上限 |
| `EXEC_DEFAULT_YIELD_TIME_MS` | `10000` | `exec_command` の `yield_time_ms` の既定値 |
| `EXEC_MAX_OUTPUT_TOKENS` | `10000` | `max_output_tokens` の上限（既定値も同じ） |
| `EXEC_OUTPUT_BUFFER_BYTES` | `1048576` | プロセスごとの未読出力のバッファ上限 |
| `EXEC_MAX_PROCESS_SECONDS` | `10800` | プロセスの最大実行時間 |
| `EXEC_MAX_PROCESSES_PER_SESSION` | `8` | セッションあたりの同時実行プロセス数 |
| `VIEW_IMAGE_MAX_BYTES` | `10485760` | `view_image` で返す画像のサイズ上限 |
| `BINDING_HMAC_KEY` または `BINDING_HMAC_KEY_FILE` | （必須） | HMAC の鍵 |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8080` | 待ち受けアドレス |

### D14. Sandbox Pod 用のイメージ

`container/Dockerfile` は Python の slim イメージをベースに、非 root ユーザー（UID 1000 など）を作る。入れるものは次のとおり。

- `bash`、`coreutils`、`procps`（`pkill`）、`util-linux`（`setsid`）、`ripgrep`
- `/opt/tools/apply_patch`（D9）
- `/opt/tools/internal_tool.py`（`USER_EMAIL` を表示する検証用ツール）

`ripgrep` は、Codex が読み取りや検索に `exec_command` で `rg` を使う前提に合わせて入れる。MCP Server 用のイメージはリポジトリ直下の `Dockerfile` で uv を使ってビルドする。どちらも `scripts/build_push.sh` で Terraform の output からイメージ URI を組み立てて Artifact Registry に push する。

### D15. 検証の進め方

- 検証の対象は MCP Server なので、LLM は使わない。単体テストと E2E 検証は、決まった引数でツールと REST API を直接呼び出して判定する。
- 手動検証（MCP Server を書く前）: busybox 相当の SandboxTemplate と SandboxClaim を kubectl で作り、`operatingMode` の切り替え、PVC の保持、`env` 注入、`shutdownTime` / `shutdownPolicy`、削除時の PVC を確認する。あわせて、exec の接続を長時間保持できるか、接続が切れたときに Sandbox 内のプロセスがどうなるかを確認する。結果で D3、D6、D9、D10 を確定させる。
- E2E 検証: `scripts/validate.py` が `mcp` SDK のクライアントで port-forward 先に接続し、spec の 13 項目を順に判定する。idle timeout（例: 120 秒）と retention（例: 300 秒）を短くした設定で MCP Server をデプロイして実行する。結果を `evidence/YYYYMMDD-e2e.md` と JSON に保存する。

## Risks / Trade-offs

- [実クラスタの CRD に `operatingMode` や claim の `env` がない、または仕様が違う] → 手動検証で先に確かめ、Sandbox を直接 patch する、exec 時に環境変数を渡すなどの代替案に切り替える。要件を満たせない場合はユーザーに確認する。
- [Suspend で PVC が消える、または削除で PVC が残る] → 手動検証で ownerReference と挙動を確認し、D10 の明示削除で対処する。Suspend で PVC が消える場合は要件を満たせないので、ユーザーに確認する。
- [`shutdownTime` の安全網が Delete で働き、孤立 PVC が残る、またはワークスペースが予期せず消える] → 安全網の期限を GC より十分後にし、挙動を README に記載する。
- [MCP Server を再起動すると、保持していた exec の接続、出力のバッファ、`process_id` が失われる] → 再起動後に古い `process_id` で `write_stdin` を呼ぶと「存在しない」エラーになる。heartbeat で更新した `last-activity` があるので、再起動直後に Suspend されることはない。Sandbox 内のプロセスが接続の切断後も動き続けるかは手動検証で確認し、1 replica 前提の制限として README に記載する。
- [exec の WebSocket を長時間（2 時間など）保持すると、途中で切れる] → 手動検証と E2E 検証で idle timeout より長いプロセスを実行して確認する。切れる場合は、プロセスを `nohup` で起動して出力と終了コードをファイルに書き、`write_stdin` のポーリングでファイルを読む方式に切り替える（その場合 `tty` と stdin への入力は制限する）。
- [Codex のツール仕様が今後変わる] → 合わせた時点の Codex のコミットを README に記録し、差異を表にしておく。
- [`apply_patch` のスクリプトと Codex の解釈が細部で違う] → Codex の `apply-patch` のテストケースを参考に pytest を書き、差異があれば README に記載する。
- [`user_email` はクライアントの申告で、認証されていない] → 今回は port-forward 経由でのみ公開する。production では MCP の認証から `user_email` を得ることを課題として README に記載する。
- [`env` を指定した claim は WarmPool を使えず cold start が遅い] → 計測して README に記載する。速度よりユーザー分離を優先する。
- [ノード 2 台分のコストが続く] → 検証後に `terraform destroy` するかをユーザーに確認する。

## Migration Plan

新規構築なので、移行作業はない。

作業の順序: Terraform で基盤を構築する → Agent Sandbox を導入する → 実クラスタの仕様を記録する → 手動検証で方式を確定する → MCP Server を実装し単体テストを書く → イメージを build・push してデプロイする → E2E 検証と計測を行う → README と証跡をまとめる → `terraform destroy` するかをユーザーに確認する。

切り戻しは、Namespace 内の SandboxClaim と PVC の削除、`k8s/` のマニフェストの削除、`terraform destroy` で行う。

## Open Questions

- 固定する Agent Sandbox のバージョン。導入時点の最新の安定リリースを選び、README に記録する。
- 検証用の FQDN 許可リストに何を入れるか。Egress 制御の動作確認に使う `github.com` だけを入れ、必要が生じたら最小限を追加して README に記録する。
