# Spec Delta

## Purpose

Bot側の安定したセッションキーを隔離されたGKE作業環境へ対応付け、テンプレート・環境変数・永続volume・通信制御を一貫して提供する。

## ADDED Requirements

### Requirement: Session identity and generation
同じtenant / sessionキーには SHALL 使用可能なworkspaceを最大1世代だけ割り当てる。APIはasyncで提供し、core Sandbox v1beta1を使用する。

#### Scenario: Concurrent acquisition
- **WHEN** 同じキーへ同時にworkspace取得を要求する
- **THEN** Sandboxと専用PVCは1組になり、異なるキーのファイルは分離される

#### Scenario: Ownership conflict
- **WHEN** 同名リソースのUIDまたは所有情報が一致しない
- **THEN** 採用・上書き・削除せず所有エラーを返す

#### Scenario: Old handle
- **WHEN** 削除済み世代のhandleでcommandを送る
- **THEN** 新世代へ暗黙転送せず世代エラーを返す

### Requirement: Template images and environment
作成時は SHALL YAMLの指定container imageと追加envを利用し、reserved fieldを保護する。同一世代のenv設定変更は拒否し、再開時は同じenvを保持する。

#### Scenario: Image and user email
- **WHEN** 自作imageとUSER_EMAILを指定して作成する
- **THEN** 指定image内のcommandがUSER_EMAILを取得できる。優先順位はimage ENV < template env < creation env < command envとなる

#### Scenario: Validation and reuse
- **WHEN** 未定義変数・不正型・reserved env上書き、または既存世代に異なるenvを指定する
- **THEN** API変更前に検証エラーまたは設定競合エラーを返す。env省略の再取得は既存設定を使う

### Requirement: Workspace persistence and shared code
専用workspaceは SHALL サスペンドで保持・終了で削除する。共有PVCはreadOnlyでmountし、セッション終了でも削除してはならない。

#### Scenario: Suspend and resume
- **WHEN** ファイル保存後に停止し再開する
- **THEN** Pod UIDは変わるが専用PVC UIDと作業ファイルは保持され、メモリやprocessの復元は保証しない

#### Scenario: Multiple readers
- **WHEN** 複数ノードのSandboxが共有コードを読む
- **THEN** 同時読出しが成功し、書込みは拒否され、1セッション終了後も共有PVCは残る

### Requirement: File operation contract
ファイル操作は SHALL bytes / streaming転送、listing / metadata / 存在確認、明示的な再帰削除を提供し、workspace外へのpath / symlink traversalを拒否する。

#### Scenario: Shared runtime files
- **WHEN** RESTでファイルを書きcommandから読む
- **THEN** 同じworkspaceの内容を取得できる

#### Scenario: Invalid paths and transfer limits
- **WHEN** root外path、readOnly領域への書込み、上限を超えるbuffered転送を要求する
- **THEN** 明示エラーを返す。サスペンドと転送が競合して途中削除されない

### Requirement: Network and runtime isolation
Podは SHALL gVisorとnon-rootで実行し、API tokenを自動mountしない。外部通信は設定FQDN / portに限定し、runtime操作は管理client / API process内reconcilerだけから許可する。

#### Scenario: Actual policy enforcement
- **WHEN** allow / deny宛先と他セッションからruntimeへ通信する
- **THEN** 必要なDNSと許可宛先だけ成功し、非許可通信は拒否される。user commandはtrackerを迂回しない

#### Scenario: Unsupported cluster
- **WHEN** 必要なCRD・StorageClass・runtimeClassがない
- **THEN** capabilityエラーを返し、未対応機能を有効と報告しない
