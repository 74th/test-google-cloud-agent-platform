## Purpose

複数の検証が衝突せず再利用できるよう、共有 Agent Gateway と接続ネットワークの所有権、参照契約、および安全な移行境界を一元化する。

## ADDED Requirements

### Requirement: 独立した共有基盤
システムは、Google Cloud プロジェクト `nnyn-dev` の `us-central1` に、共有 Agent Gateway 専用の VPC、subnet、および Agent Gateway を `common` の独立した Terraform state から管理しなければならない（SHALL）。この state は検証固有リソースを管理してはならず（MUST NOT）、既存の検証用 state を暗黙に参照してはならない（MUST NOT）。

#### Scenario: common の新規 state を適用する
- **WHEN** 操作者が前提条件を満たした空の `common` Terraform state に対して plan と apply を実行する
- **THEN** 専用 VPC、`us-central1` の専用 subnet、および共有 Agent Gateway が `nnyn-dev` に作成される
- **AND** 検証固有の Agent Runtime、MCP server、GKE、Cloud Run、または Artifact Registry は作成されない

#### Scenario: state の管理範囲を検査する
- **WHEN** 操作者が `common` の Terraform state と構成を検査する
- **THEN** 管理対象の実体リソースは共有ネットワークと共有 Agent Gateway の責務に限定される
- **AND** `20260822-agent-gateway` および `20260823-mcp-server` の state とは独立している

### Requirement: VPC 接続 Agent Gateway
共有 Agent Gateway は専用 subnet を持つ専用 VPC に接続されなければならない（SHALL）。ネットワーク接続は Terraform 構成とデプロイ後の Google Cloud API 応答の両方から確認可能でなければならない（MUST）。

#### Scenario: Gateway のネットワーク接続を確認する
- **WHEN** 操作者が作成済み Agent Gateway を Google Cloud API で取得する
- **THEN** 応答は `common` が管理する専用 VPC またはその接続識別子を示す
- **AND** 対応する subnet は `nnyn-dev/us-central1` に存在する

#### Scenario: 未接続 Gateway を拒否する
- **WHEN** Terraform の静的検査または plan が Gateway と専用ネットワークの接続を示さない
- **THEN** 検証は失敗し、その構成を共有 Gateway として承認しない

### Requirement: 安定した利用者向け参照契約
共有基盤は、少なくとも Agent Gateway の完全修飾リソース ID、VPC ID、および subnet ID を機械可読な Terraform output として公開しなければならない（SHALL）。利用側は Gateway を自身の state で作成せず、この完全修飾 ID を明示的な入力として参照しなければならない（MUST）。

#### Scenario: 利用側が共有 Gateway を参照する
- **WHEN** 利用側の構成へ `common` の Agent Gateway output を入力する
- **THEN** 利用側は `projects/nnyn-dev/locations/us-central1/agentGateways/<name>` 形式の ID を使用する
- **AND** 利用側の構成と state は Agent Gateway リソースを所有しない

#### Scenario: output を検査する
- **WHEN** 操作者が `common` の Terraform output を JSON 形式で取得する
- **THEN** Gateway、VPC、および subnet の各識別子を曖昧さなく取得できる

### Requirement: 既存 Gateway 所有権の安全な移行
システムは、`20260822-agent-gateway` と `20260823-mcp-server` の既存 Terraform state、依存リソース、および plan を移行前に個別に確認できる手順を提供しなければならない（SHALL）。`terraform destroy` は対象と plan を人間が確認して明示承認するまで実行してはならず（MUST NOT）、共有 Gateway の作成は既存の同方向 Gateway が削除されたことを確認した後でなければならない（MUST）。

#### Scenario: 承認前の移行確認
- **WHEN** 操作者が移行手順を開始するが destroy を明示承認していない
- **THEN** 手順は state、依存関係、destroy plan、および現在の Gateway を読み取り専用で収集するところで停止する
- **AND** クラウドリソースは削除されない

#### Scenario: 承認後に既存環境を削除する
- **WHEN** 人間が各対象と destroy plan を確認し、対象 state の destroy を明示承認する
- **THEN** 操作者は `20260822-agent-gateway` と `20260823-mcp-server` を state ごとに分けて destroy できる
- **AND** 各 destroy 後に対象 state と残存クラウドリソースを確認する

#### Scenario: 旧 Gateway 管理コードを除去する
- **WHEN** 承認済み destroy と残存確認が完了する
- **THEN** 検証固有 Terraform から Agent Gateway の作成、削除、および旧固定 ID への結合が除去される
- **AND** 利用側 Terraform はこの移行作業では再 apply されない

### Requirement: 共有基盤の事前検証と変更保護
システムは、実装時点の公式 Google Cloud API および Terraform provider schema が VPC 接続 Agent Gateway をサポートすることを実装前に確認し、その利用バージョンと接続フィールドを記録しなければならない（SHALL）。共有基盤の apply または destroy は、対象を限定した plan と人間の明示承認なしに実行してはならない（MUST NOT）。

#### Scenario: provider 能力を確認する
- **WHEN** 実装者が Terraform コードを書き始める
- **THEN** 公式 API/provider schema から Agent Gateway の VPC 接続方法と必要な関連リソースを確認する
- **AND** 未対応または不明な場合は推測した属性で apply せず、再現可能な代替経路または blocker を記録する

#### Scenario: 共有基盤の apply 前確認
- **WHEN** `common` の Terraform plan が共有基盤の作成または変更を提案する
- **THEN** 操作者は project、region、state、リソース名、ネットワーク範囲、および変更対象を確認できる
- **AND** 明示承認がなければ apply は実行されない

#### Scenario: 共有基盤の cleanup
- **WHEN** 共有基盤が不要になった後に cleanup を検討する
- **THEN** destroy plan と利用者の有無を確認し、人間が明示承認するまで `common` の Terraform destroy は実行されない
