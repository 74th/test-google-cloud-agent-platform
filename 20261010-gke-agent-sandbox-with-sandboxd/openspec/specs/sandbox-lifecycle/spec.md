# Sandbox Lifecycle Specification

## Purpose

commandの実行状態とKubernetesの永続情報を使って作業環境を自動停止・再開・期限削除し、競合や障害時にも作業中の環境を誤削除せず消失を通知する。

## Requirements

### Requirement: Minute-based idle suspension
監視は SHALL 60秒ごとに行い、実行中・不明・受付中commandがなく最終終了から300秒経過したらKubernetes APIで停止する。file操作中も停止を保留する。

#### Scenario: Idle boundary
- **WHEN** 最後のcommandが終了し次のcommandが来ない
- **THEN** 通常300〜360秒後に停止開始する。並列commandは最後の1件の終了を起点とする

#### Scenario: Observation is not activity
- **WHEN** 毎分0件確認やhealth / status pollをする
- **THEN** 最新確認時刻だけ更新し、idle起点を延長しない

#### Scenario: No commands after readiness
- **WHEN** 初回作成または再開後にcommandが来ない
- **THEN** 今回のReady時刻から5分を数える

#### Scenario: Unknown runtime
- **WHEN** 状態照会失敗・unknown・受付未解決がある
- **THEN** 停止を保留する。履歴不明後の0件確定ではその確認時刻から5分待つ

### Requirement: Atomic command admission
停止前には SHALL command受付を閉じて実行数を再確認する。停止と新規受付が競合しても実行中commandを終了させず、受付済みIDを二重実行してはならない。

#### Scenario: Command races with suspension
- **WHEN** 停止直前または停止中に新規commandを送る
- **THEN** 先に実行が始まれば停止を取り消し、gate閉鎖後なら停止 / 再開完了後に1回だけ実行する

### Requirement: Suspend resume and expiration
停止は SHALL Podを削除してPVCを保持し、停止完了から604800秒で専用リソースを削除する。期限内commandは自動再開し、接続を再取得する。

#### Scenario: Deadline race
- **WHEN** 期限境界で再開と削除が競合する
- **THEN** 削除開始済みUIDを復活させず、旧世代cleanup後に新世代を作る

#### Scenario: Controller expiry fallback
- **WHEN** workerが停止したまま保持期限を迎える
- **THEN** 設定済み絶対期限によりcontrollerが削除を進め、worker復旧後に残存リソースと通知を照合する

### Requirement: Durable Kubernetes metadata
session ID、実行数、開始 / 終了時刻、0件確認時刻、idle起点、状態確定可否、停止 / 期限時刻は SHALL Kubernetes metadataに保存する。Pod削除後も必要な記録を保持する。

#### Scenario: Annotations and privacy
- **WHEN** 監視を実行しPodを停止する
- **THEN** Sandbox annotationsで時刻とsessionを確認できる。未知を0と書かず、USER_EMAILやSecret値をmetadata / 管理ログへ自動転載しない

### Requirement: Recoverable ownership and cleanup
state変更は SHALL 世代・UID・所有情報を検証し、CAS / 排他と冪等operationで回復する。API到達不能をNotFoundと扱わず、専用リソース消失前に削除完了としてはならない。

#### Scenario: Crash and competing workers
- **WHEN** 作成 / 停止 / 削除中のクラッシュ、Lease喪失、watch切断が起きる
- **THEN** 同じoperationを照合して収束し、二重作成・誤削除を防ぎ、削除遅延はcleanup未完了として報告する

### Requirement: Persistent session repository
SessionRecordと操作Leaseは SHALL 管理API専用のReadWriteOnce PVC上のSQLiteへ保存する。トランザクションとversion条件付き更新で並行request・競合書込みを直列化し、ConfigMapのサイズ制限に依存しない。管理APIのPod再起動後は同じPVCから全sessionを復元する。

#### Scenario: API process restart
- **WHEN** 管理API processまたはPodが再起動する
- **THEN** 同じPVCをmountしてSessionRecord、operation phase、command ID、eventを読み戻し、reconcileを再開する

#### Scenario: Concurrent state changes
- **WHEN** 同一または異なるsessionへの更新が同時に到着する
- **THEN** SQLite transactionが書込みを直列化し、古いversionを使った更新は競合として拒否する

### Requirement: Workspace loss context events
workspace消失は SHALL 世代とevent ID付きで永続通知し、context保存後のackまで再配信する。通常のPod再作成だけでは消失通知を出してはならない。

#### Scenario: Recreated workspace
- **WHEN** 期限削除または外部PVC消失後に新世代を取得する
- **THEN** 空workspaceと通知を返し、共有コードが残る旨を区別する。作成失敗で通知を消費しない

#### Scenario: Crash before acknowledgment
- **WHEN** contextへappend後ack前にBotが落ちる
- **THEN** 同じevent IDを再配信し、呼び出し元が重複排除できる

### Requirement: Finite agent runner lifetime
Sandbox内Agent runnerは SHALL 1 turnごとの追跡commandとして実行し、turn完了で終了する。常駐入力待ちrunnerは初期版で採用しない。

#### Scenario: LLM waiting in runner
- **WHEN** runnerがLLM / tool待機中で、後にturnが完了する
- **THEN** 待機中はcommand実行中として保護し、終了後にidle起点を設定する
