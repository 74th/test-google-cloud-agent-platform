# Spec Delta

## Purpose

クラスタ不要のunitと実GKE上のintegration / E2Eを分け、実API・runtime・CSI・networkの組み合わせに対する再現可能な証拠とcleanup手順を提供する。

## ADDED Requirements

### Requirement: Opt-in real cluster tests
通常testは SHALL クラスタへ接続しない。実クラスタtestは明示したproject / contextへcluster内runnerで実行し、runごとにリソースを分離する。

#### Scenario: Unit default
- **WHEN** 通常pytestを実行する
- **THEN** Cloud / Kubernetes認証なしでunitだけが実行される

#### Scenario: Explicit test target
- **WHEN** 実GKE testを指定する
- **THEN** 接続先を照合し、run ID・label・UIDで所有を確認して操作する

### Requirement: Compatibility evidence
検証は SHALL GKE / node image、provider lock、controller / CRD / SDK、runtime digest、StorageClassとfeatureの組合せを記録する。実施していない検証を完了と報告してはならない。

#### Scenario: Pinned runtime smoke test
- **WHEN** core v1beta1、gVisor、tracker、PVCとFQDNのspikeを実行する
- **THEN** process照合・SDK接続 / 切断・PVC所有 / GCの結果とversionを保存する

### Requirement: Behavior acceptance suite
E2Eは SHALL session分離、env / image、永続性、共有readOnly、idle / 期限、イベント、競合・再起動、出力・子processを検証する。短縮TTLだけで本番境界の検証を代替してはならない。

#### Scenario: Lifecycle acceptance
- **WHEN** 作成から実行・停止・再開・削除・新世代取得まで実行する
- **THEN** 実APIとUID / 内容 / イベントで結果を確認し、60 / 300 / 604800秒はunit境界と実300秒idleでも検証する

#### Scenario: Network negative control
- **WHEN** deny宛先への接続を試す
- **THEN** DNSと宛先の対照到達性を確認し、相手障害をpolicy成功と誤認しない

### Requirement: Diagnostics and scoped cleanup
失敗時は SHALL 秘密を含まない状態・events・ログと再実行可能なcleanup情報を保存する。cleanupはrun所有リソースのみ対象にする。

#### Scenario: Failed run cleanup
- **WHEN** testが途中で失敗する
- **THEN** run IDとresource refsを記録し、他検証・共有fixtureを誤削除せず残存リソースを回収できる
