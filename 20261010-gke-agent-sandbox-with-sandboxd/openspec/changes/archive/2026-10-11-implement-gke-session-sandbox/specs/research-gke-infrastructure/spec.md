# Spec Delta

## Purpose

実GKE検証用インフラをTerraformで再現可能に管理し、同一projectで進行する他の検証と物理名・state・削除範囲を分離する。

## ADDED Requirements

### Requirement: Isolated Terraform ownership
検証インフラ定義は SHALL `./terraform`に置き、独立したstateを使用する。他の検証やcommonのstateを参照して変更・削除してはならない。

#### Scenario: Independent plan
- **WHEN** 専用tfvarsでplanする
- **THEN** この検証が所有するリソースだけが作成・変更対象になり、project / locationが確認できる

#### Scenario: Scoped destruction
- **WHEN** この検証をdestroyする
- **THEN** 他のクラスタ・共有インフラは削除されず、有効化したproject APIも無効化されない

### Requirement: Research physical names
物理名は SHALL `research-gke-agent-sandbox-with-sandboxd`を基本prefixとし、長さ制約には決定的な省略名を使う。別検証と衝突する汎用名を使ってはならない。

#### Scenario: Long and short names
- **WHEN** クラスタ・VPC・node pool・registry・service accountを定義する
- **THEN** 基本prefixまたは`research-gke-as-sbd`由来の名前と用途suffixが使われ、各APIの命名制約を満たす

### Requirement: Compatible GKE execution environment
検証環境は SHALL GKE Standard、Dataplane V2、FQDN policy、cluster DNS、gVisor実行と永続volumeを提供し、controller / runner用の通常node poolも提供する。

#### Scenario: Provisioned capabilities
- **WHEN** 専用クラスタを構築しbootstrapする
- **THEN** core Sandbox v1beta1、gVisor Pod、専用PVC、共有readOnly volume、FQDN通信制御を検証できる

### Requirement: Explicit deployment inputs and outputs
Terraformは SHALL project、location、ネットワーク範囲を明示入力とし、クラスタ識別情報、network、registry、接続コマンドを出力する。認証情報を出力してはならない。

#### Scenario: Reviewable environment
- **WHEN** tfvarsを指定してapplyを準備する
- **THEN** 同一projectの他検証とのCIDR・物理名の競合を確認でき、接続先を明示できる
