# Tasks

## 1. Terraformによる専用検証インフラ

- [x] 1.1 `./terraform`にprovider / version / 独立backend、変数、tfvars例、state除外設定を追加し、initとvalidateが成功することを確認する。
- [x] 1.2 `research-gke-agent-sandbox-with-sandboxd`と`research-gke-as-sbd`の命名locals・suffix込みvalidationを実装し、各API制約と命名対応表を確認する。
- [x] 1.3 専用VPC / subnet / secondary range / router / NAT / API有効化を定義し、planがcommon・他検証の変更を含まずAPIのdisable_on_destroyがfalseであることを確認する。
- [x] 1.4 GKE Standard、Dataplane V2、FQDN policy、Workload Identity、PD CSI、通常 / gVisor node pool、専用node IAMとregistryを定義し、provider schema・fmt・validateで検証する。
- [x] 1.5 cluster / network / registry / 物理名 / 接続コマンドをoutputsへ追加し、Secretを出力しないこととproject / locationの明示をplanで確認する。
- [x] 1.6 Terraformの入力・独立state・apply / destroy・CIDR / 命名競合の確認手順を文書化し、実行先tfvarsでplanを保存して手順の整合性を確認する。

## 2. クラスタ構築と互換性bootstrap

- [x] 2.1 planのproject / location / リソース範囲を確認して専用クラスタを構築し、物理名・node pool・Dataplane V2 / FQDN featureとTerraform出力の一致を実APIで確認する。
- [x] 2.2 固定versionのAgent Sandbox v1beta1 CRD / controllerを`k8s/`と冪等bootstrap scriptで導入し、再実行でも重複せずcontrollerがReadyになることを確認する。
- [x] 2.3 namespace / RBAC / runtimeClass / StorageClassと共有ROM fixture準備を追加し、gVisor Podと専用PVC bind、別ノード同時readOnly mountを実クラスタで確認する。
- [x] 2.4 最小sandboxd imageと管理runnerを構築し、REST書込とgRPC読出し、SDK公開APIの接続 / 切断契約、Pod IP / Service経路を実GKEで確認する。
- [x] 2.5 tracker復旧用のprocess identity / process group照合prototypeを作り、同一container・gVisor上の照合とPID再利用の区別を検証する。sandboxd stream切断時のprocess group終了を確認し、結果unknown / 出力不完全とする契約をdesign/specへ反映する。
- [x] 2.6 Sandbox停止 / 再開 / 削除とPVC ownerReference / GC / PV reclaimを実測し、controller / SDK / node / imageの互換性記録とbootstrap手順を保存する。

## 3. Python packageと設定・テンプレート

- [x] 3.1 Python 3.11以上の`gke_session_sandbox` package、uv lock、pytest unit / gke marker、CLI入口を追加し、importとクラスタ非接続の通常testを確認する。
- [x] 3.2 session / generation / resource refs / command状態 / event / exceptionの型と設定を実装し、不正型・不正数量・reserved fieldのunit testを通す。
- [x] 3.3 YAML構造化render、container image指定 / override、digest算出を実装し、API呼出し前の未定義変数・reserved metadata拒否をunit testで確認する。
- [x] 3.4 template / creation / command envのmerge、USER_EMAIL挿入、env省略reuse、同一世代変更拒否を実装し、優先順位とSecret / env非露出のunit testを通す。
- [x] 3.5 `templates/`と設定例、async利用例を文書化し、render結果と実行可能な例が公開契約に一致することを確認する。

## 4. Kubernetes永続状態とworkspace管理

- [x] 4.1 管理namespaceのConfigMap Repository、session Lease、resourceVersion CASを実装し、競合・Lease喪失・容量 / 未ackイベント上限のunit testを通す。（初期実装）
- [x] 4.2 generation / UID / operation phase / command予約 / イベントを永続化し、途中クラッシュ・unknown / NotFound区別・watch 410 relistのunit testを通す。
- [x] 4.3 core Sandbox v1beta1 backend、Suspended作成→policy生成→Running、Ready / UID / runtime health待機を実装し、実クラスタCRUDとtimeout診断を確認する。
- [x] 4.4 専用PVCとreadOnly共有PVC、UID付きcleanup、所有衝突拒否を実装し、専用のみ削除され共有PVCが残るintegration testを通す。
- [x] 4.5 `ensure / get / suspend / resume / terminate / list / close`を実装し、同一key同時取得・異なるkey分離・close非削除・古い世代handle拒否をunit / integrationで確認する。
- [x] 4.6 default deny、DNS、FQDN allow、管理client向け8080 / 8081 policyを実装し、egress加算・API token非mount・tracker迂回拒否を実クラスタで確認する。
- [x] 4.7 preflightとmetadata診断、namespace / RBAC / ownershipの運用手順を追加し、未対応CRD / runtimeClass / StorageClassを明示エラーで返すことを確認する。

## 5. Pod内CommandTrackerと実行API

- [x] 5.1 Python supervisorとtracker HTTP API / healthを追加し、sandboxd疎通とtracker起動世代をruntime testで確認する。
- [x] 5.2 command ID受付・重複排除・原子的gate・durable journalを実装し、送信前後クラッシュと重複要求で二重実行しないtestを通す。
- [x] 5.3 sandboxd Start経由のrun / stream / stdout / stderr / exitを実装し、非ゼロexitとcheck指定、無出力長時間commandと並列commandのtestを通す。
- [x] 5.4 stdin / EOF / signal / PTY / timeout / cancelを実装し、SIGTERM→5秒後SIGKILLとprocess group終了確認のruntime testを通す。
- [x] 5.5 tracker再起動のjournal / process照合、running / finished / unknown、呼出元切断後の継続とtracker停止時のgroup終了 / 結果unknownを実装し、gVisor上で誤終了・PID誤採用がないことを確認する。
- [x] 5.6 残存子processの終了・確認とdetached非対応を実装し、shellだけ終了するケースでidleへ進まないruntime testを通す。
- [x] 5.7 tracker clientの自動予約 / 再開、command ID付きエラーと状態再照会を実装し、利用側activity不要・送信結果不明の非再送をintegrationで確認する。
- [x] 5.8 command状態照会・再起動回復・cancel / timeout・サポートしない実行形態を文書化し、例がtestで確認した挙動に一致することを確認する。

## 6. 出力保持とファイル操作

- [x] 6.1 呼び出し元から独立したstream消費、chunk単位のPVC保存とcursor再取得を実装し、client切断後の再取得と有限メモリのruntime testを通す。
- [x] 6.2 各8MiBのbuffered応答上限、command合計64MiB / session合計256MiBの保存上限を実装し、上限 / PVC失敗時の停止・欠落・明示エラーをruntime testで確認する。
- [x] 6.3 出力の終了後7日保持・失効・終了要約保持を実装し、clock注入testで保持境界、OutputExpiredErrorとidle起点保持を確認する。
- [x] 6.4 REST fileのread / write / streaming / list / stat / exists / 明示再帰deleteを実装し、path / symlink traversal、readOnly拒否、転送上限と内部予約のtestを通す。
- [x] 6.5 結果再取得・保存範囲・欠落・容量 / 保持設定とfile APIを文書化し、command ID / cursor付き例をruntime testで確認する。

## 7. API process内reconcilerとライフサイクル

- [x] 7.1 60秒監視、最終command終了から300秒判定、Ready起点fallbackを実装し、0件確認時刻がidle起点を更新しないunit testを通す。
- [x] 7.2 running / unknown / 未確定受付 / file操作の停止保留を実装し、client切断やhealth pollを活動として誤計上しないunit testを通す。
- [x] 7.3 Lease下のgate閉鎖・最終0件確認・停止intentを実装し、停止直前command、Lease喪失、patch失敗時gate回復の競合testを通す。
- [x] 7.4 Suspended完了確認、604800秒期限、shutdownTime / Delete fallback、期限解除再開を実装し、期限境界・deletionTimestamp・接続 / env保持をunit / integrationで確認する。
- [x] 7.5 session ID・実行数・開始 / 終了 / 確認 / idle / 停止 / 期限時刻をannotationsへ投影し、Pod削除後保持・未知非0・秘密非転載をintegrationで確認する。
- [x] 7.6 worker停止 / 再起動、watch切断、複数worker、finalizer遅延、外部Sandbox / PVC消失のreconcileを実装し、二重作成・早期完了・共有誤削除をしないtestを通す。
- [x] 7.7 API processのlifespanでreconciler async taskを起動し、`preflight / reconcile` CLI、設定・診断・復旧手順を追加する。別Deploymentを作らず、API process再起動後に永続Repositoryから監視を再開することをunit / 実GKEで確認する。
- [x] 7.8 セッション正本をConfigMapからAPI専用PVC上のSQLiteへ移行し、SQLite transaction / CAS / leaseとprocess再起動後の復元をtestする。GKE bootstrapにRWO PVCを追加し、管理APIをreplica 1・PVC mountで構成する運用例へ更新する。

## 8. 会話イベントとAgent adapter契約

- [x] 8.1 workspace消失イベント、世代 / event ID、pending取得とackを実装し、新世代作成失敗・append / ack間クラッシュ・通常Pod再作成のunit testを通す。
- [x] 8.2 空workspaceと共有コード保持のcontext messageを実装し、期限 / 明示削除 / 外部消失をintegrationで確認する。
- [x] 8.3 1 turnで終了するAgent runner fixtureとBot向け例を追加し、LLM待機相当では停止せずturn終了後にidleとなるE2Eを通す。
- [x] 8.4 イベントのappend_once / ack、runner寿命、workspaceと会話storeの責務を文書化し、Slack送信・実LLMなしで例の契約を検証する。

## 9. 実GKE受け入れと運用完了

- [x] 9.1 cluster内pytest runner、project / context照合、run ID namespace、失敗artifact・所有UID cleanupを実装し、意図しない接続先拒否と失敗後再cleanupを実GKEで確認する。（2026-10-11に専用GKEでcluster内pytestのidentity・runtime・expiry 3 test成功、意図的失敗artifact採取とNamespace cleanup、誤context拒否を確認。）
- [ ] 9.2 READMEの16シナリオとspecをtestへ対応付け、workspace分離・image / env・共有ROM・file / command操作の実GKE suiteを通して記録する。（対応表[`docs/validation/acceptance-matrix.md`](../../../docs/validation/acceptance-matrix.md)を追加。workspace分離・image / env・file / commandの初期cluster内suiteと共有ROMの別GKE確認は完了。16シナリオ全体のcluster suiteは未完了。）
- [x] 9.3 実300秒idle、短縮保持期限による削除 / 新世代 / context通知、worker停止時controller期限処理を実GKEで確認し、60 / 300 / 604800秒境界unitと結果を保存する。（300秒idleはrun `cf83742286cc`、10 / 60秒保持は`fddcf0db81d4` / `5d0a4542fc74`、reconcilerを停止した15秒保持とcontroller削除・新世代・event ackはcluster pytest run `b39a0715d2b0`で確認。7日間の実時間待ちは対象外、境界はunit testで確認。）
- [ ] 9.4 tracker / worker再起動、unknown、出力上限 / 保存障害、残存子process、停止 / 期限競合の実GKE suiteを通して状態・UID・出力を記録する。（run `9a29229094e8`で出力上限・不完全出力・cursor再取得を追加確認。残るケースは[`acceptance-matrix.md`](../../../docs/validation/acceptance-matrix.md)参照。）
- [x] 9.5 allow / deny / DNS / 他session runtimeアクセスを対照endpointと別ノードで検証し、FQDN / NetworkPolicyの実通信結果を保存する。（DNS / FQDN allow・HTTPS deny・management REST allow・tracker gRPC denyは[`python-sandbox-backend.md`](../../../docs/validation/python-sandbox-backend.md)、別ノード間のsession runtime Pod-IP denyとmanagement positive controlはcluster pytest run `9a29229094e8`。）
- [x] 9.6 検証済みprovider / GKE / controller / CRD / SDK / image digest / StorageClassを固定し、`docs/validation/`とREADMEに結果・制限・実行 / cleanup手順を反映する。
- [x] 9.7 通常unit・Terraform fmt / validate・実GKE suiteとrun cleanupを確認し、専用環境destroy時の残存Cloud / volume / IAMと他検証非変更をplanまたは実APIで記録する。([`destroy-inventory.md`](../../../docs/validation/destroy-inventory.md)に20-resource destroy plan、`disable_on_destroy=false`、共有fixture PV、cluster外diskを記録。destroy自体は実行していない。)
