# Design

## Context

現状はREADMEの仕様案とOpenSpec scaffoldのみで、Python package、runtime、Terraform、testは未実装。動機はproposalのWhyを参照する。隣接`20260811-gke-isolated/terraform`にはDataplane V2 / FQDN policyの例があるが、既存default VPCや汎用物理名を使っているため、この検証用にコピーして共有stateを操作することはしない。

READMEの契約を5 capabilityのspecへ分ける。core APIは`agents.x-k8s.io/v1beta1`、controller候補はv1.0.6。GKE version、controller release、Terraform provider versionは別々にlock / 記録する。

## Goals / Non-Goals

**Goals:**

- 利用側はcommand送信だけで活動管理でき、Pod内trackerとcluster内デーモンが独立して継続する。
- 全変更をこのproject内に閉じ、Cloud / Kubernetes / runtimeそれぞれの所有・回復・検証境界を明確にする。
- 実GKEの証拠を伴う完了判定と、段階的に適用できるTerraform / bootstrapを提供する。

**Non-Goals:**

- セッションごとのVPC作成、隣接検証・commonの変更、既存リソースの暗黙import。
- SlackBot本体の実装、常駐Agent runner、WarmPool、メモリsnapshot、SQL Repository。
- 実行不明commandのexactly-once完了保証。受付重複排除と不明状態の保留を提供する。

## Decisions

### 1. Terraformの配置・命名・state

`terraform/`へ`versions.tf`、`providers.tf`、`variables.tf`、`locals.tf`、`services.tf`、`network.tf`、`gke.tf`、`iam.tf`、`registry.tf`、`outputs.tf`、`terraform.tfvars.example`を追加する。stateはこのディレクトリの独立したlocal backendで開始し、git管理しない。remote backendへ移す場合も専用keyを使う。lockfileはgit管理する。

project_id、region / zone、subnet / Pod / Service / control-plane CIDR、authorized control-plane accessを入力にする。API有効化は`disable_on_destroy=false`。project IAMはmember単位にし、既存binding全体を置換しない。

| 用途 | 物理名の基本案 |
| --- | --- |
| GKE cluster | `research-gke-agent-sandbox-with-sandboxd` |
| VPC / subnet | 基本prefix + `-vpc` / `-subnet` |
| 通常 / gVisor node pool | `research-gke-as-sbd-system` / `research-gke-as-sbd-gvisor` |
| node用IAM service account ID | `research-gke-as-sbd-node` |
| Artifact Registry | 基本prefix + `-images` |
| router / NAT | 基本prefix + `-router` / `-nat` |
| secondary range | `research-gke-as-sbd-pods` / `research-gke-as-sbd-services` |

`name_prefix`の既定は基本prefixとし、制限のあるIDには`short_name_prefix`（既定`research-gke-as-sbd`）を使う。suffix込みでvalidationし、単純な末尾切捨てによる衝突を避ける。すべて実API制限を確認し、対応表をoutputsと運用手順へ記録する。service account IDには6〜30文字制約がある。[Google IAM命名仕様](https://docs.cloud.google.com/iam/docs/service-accounts-create)

同一projectで別の本検証を並行する場合はprefix / short prefix / state / CIDRを一緒に変更する。現時点でprojectやCIDRを固定しない。

### 2. 専用GKEとbootstrapを分離

専用VPC / subnetを作り、VPC-native GKE Standard、Dataplane V2、FQDN policy、cluster DNS、Workload Identity、PD CSIを設定する。private nodeのegressは専用Cloud NATで提供する。control-planeアクセスは実行元から到達できる方式と明示したauthorized networksで設定する。通常node poolへcontroller / デーモン / runnerを置き、gVisor poolへruntimeを置く。

TerraformはCloudリソースまでを管理し、クラスタ内は`k8s/`と冪等bootstrap scriptで導入する。初回planで未導入CRDをKubernetes providerがdiscoverできない問題を避けるため、CloudとCRDを同一stateの1回applyへ混在させない。GKEの正式なgVisor provider fieldは導入providerのschemaで確認する。deprecated fieldを無条件に採用しない。[Google provider GKE resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_cluster.html)

controller / CRD、namespace、RBAC、StorageClass、共有readOnly fixture、デーモン、test Jobをbootstrapする。共通コード用の初期fixtureは事前投入したdiskのROMを第一案とし、再利用可能なsnapshot / clone作成手順を用意する。Filestore等のRWXをreadOnly mountするprofileも拡張可能にするが、初期受け入れでは1つの実動作profileを固定する。

### 3. asyncライブラリとcore Sandbox adapter

`src/gke_session_sandbox/`へmodels、config / renderer、backend、repository、manager、runtime client、reconciler、CLIを分ける。Python 3.11以上、uvとpytestを使う。SDK公開APIの再利用を検証し、足りない機能はadapter内のKubernetes client / generated process stub / HTTP clientで実装する。SDK private APIは使わない。

YAMLを構造化し型付き値を挿入する。template container imageと設定override、creation env、process envの優先順位はspec / READMEに従う。既存世代へのenv変更は拒否する。Secret参照はrender結果に値を展開しない。

core Sandboxを最初はSuspendedで作り、policy完成後にRunningへpatchする。`Ready=True`のobservedGeneration、Pod UID、REST / tracker healthを待つ。専用PVC / policy所有情報を記録し、reclaim / controller GCはspikeで検証する。file APIはsandboxd REST、command APIはtrackerに接続する。

### 4. Pod内CommandTracker

`runtime/`へsupervisor、tracker HTTP API、command journal、output storeとimage定義を置く。ツール・sandboxd・trackerは同じcontainer / PID namespaceで実行する。外向きのfileは8080、trackerは8081、process gRPCはPod内9090。NetworkPolicyは管理clientからの8080 / 8081だけ許可する。

trackerがsandboxd Start streamを継続消費し、command ID / runtime instance / process ID / process開始識別情報を記録する。runも同じStart経路から出力を集約する。受付gate、状態snapshot、cursor付き出力、stdin / signal / PTYを提供する。gateと受付・実行数変更は同じ排他単位で扱う。

journal / outputは専用PVCへ保存し、原子的更新と再起動時のreplayで回復する。process groupが残ればrunning、確定不能ならunknown。shell終了と子process終了を区別し、detachedは非対応。trackerが停止してもsandboxdとcommandが継続し得るため、stream復旧不能をfinishedと扱わない。PID再利用・同一Pod内の照合はgVisor spikeの必須項目。

subscriber queueは有限にし、読み手に関係なくstreamを消費する。出力上限・書込み失敗時は停止を試み、欠落と原因を別journalに記録する。PVC全体の書込み失敗時に終了journalも保存できなければunknownとして扱い、管理デーモンにもエラーを残す。メモリ無制限化や黙った成功扱いへ切り替えない。

### 5. ConfigMap / Leaseと監視デーモン

管理namespaceのセッション別ConfigMapを正本とし、session LeaseとresourceVersion CASを組み合わせる。generation / UID / operation phase / command予約 / eventを保持する。全リソース更新は所有UIDを検証する。Lease喪失時は書込みを止め、競合patchと中断operationはrelistから回復する。

監視デーモンは60秒ごとにtracker状態を照会し、最新確認時刻と最終終了時刻を別々に保存する。0件確認でidle起点を動かさない。unknown、未解決受付、file操作は停止を保留する。停止前はLease下でgateを閉じ、0件を再確認する。閉じたgateの回復もoperationとして記録する。

停止完了時刻から7日期限を保存し、SandboxのshutdownTime / Deleteをfallbackとして設定する。再開は期限解除とRunningを同一patchにし、Pod接続 / tracker instanceを再取得する。期限削除はLease外のcontrollerとも競合するため、deletionTimestamp / UIDを最新確認し、削除開始済みを復活させない。

annotationsはREADMEの仮prefixを設定可能にして実装する。Sandbox本体へ投影し、Pod templateの毎分更新はしない。終了後の状態と未ackイベントはConfigMapへ残す。容量・イベント数は検証可能な上限を設け、超過時は新世代作成を止める。

### 6. Bot連携と実GKEの完了判定

Bot interfaceはensure、command / file、pending events / ackまでとする。Sandbox内SDKを使う場合のrunnerは1 turnごとに終了する。実LLMを使わないrunner fixtureで寿命の契約を検証し、Slack送信やAPIキーなしでも基礎受け入れを完了可能にする。

Unitはclock / API adapterを注入して境界・競合を検証し、integration / E2Eはcluster内Jobから実API / runtimeへ接続する。READMEの16シナリオをtest caseへ対応付ける。実300秒idleと短縮保持期限のE2Eを行い、7日待機の代わりに604800秒境界unitと実controller deadline処理を合わせて検証する。

project / location、versions / digests、plan、CR / Pod / PVC UID、通信の対照結果、failure / cleanup情報を`docs/validation/`へ保存する。秘密値を除外する。未実施taskを完了にせず、quota・API権限・接続・runtime互換性の障害を証拠として残す。

## Risks / Trade-offs

- [trackerの標準process一覧RPCがない] → 追加trackerとprocess journalを実装し、復元不能をunknownとして保持。status RPCがある前提へ変更しない。
- [gVisorでprocess照合が成立しない] → 実spikeで先に検証する。契約を満たせない場合は実装を進めて完了扱いせず、設計変更を相談する。
- [追加trackerの出力保存によるPVC容量消費] → command / session上限、7日保持、明示エラー、streamの継続消費。
- [ConfigMapとSandboxに分散transactionがない] → durable intent、CAS、Lease、UID、phaseごとの冪等reconcile。
- [Cloud / cluster構築コストとquota] → node台数とmachine typeを入力化し、planで可視化、専用fixtureとcleanup手順を残す。
- [隣接検証への影響] → 独立state、専用network、明示prefix、member IAM、API非無効化、run所有cleanup。
- [Pod内の同一権限でjournalを編集できる] → tracker用ファイルを別権限で保護し、user commandにmetadata書込み権限を与えない。プロセス状態との照合なしにjournalを信頼しない。

## Migration Plan

1. 実装artifactをreview後、Terraformのfmt / validate / planと接続先確認を行う。
2. 専用インフラを構築し、CRD / controller / 最小runtimeをbootstrapして互換性spikeを実行する。
3. library / tracker / デーモンを導入し、unitと実GKE受け入れを段階的に実行する。
4. versions / digestsと結果を固定し、運用手順をREADMEへ反映する。
5. rollbackは新規command受付を停止し、run所有Kubernetesリソースを回収、専用Terraform環境をdestroyする。共有コードfixtureとstateの扱いを明記し、common / 他検証を対象に含めない。

## Open Questions

- 実行先project / zone、利用可能quota、CIDR、control-plane到達用networkはapply入力として確定する。現在の計画で既存projectやrangeは選択していない。
- provider / controller / SDK / image digestの最終lockは明示した互換性検証で決める。specのv1beta1契約を変えない範囲で選択する。
