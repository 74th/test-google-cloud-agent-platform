# terraform-poc-environment Specification

## Purpose

Google Cloud 上の検証環境を既存リソースから分離し、低コストかつ再現可能な Terraform 構成として安全に作成・確認・削除できるようにする。

## Requirements

### Requirement: Scoped and collision-resistant resources
検証用に新規作成する Google Cloud resource は project `nnyn-dev` に配置し、resource 名または provider の長さ制約がある場合は対応する label に `20260823-mcp-server` の識別子を含めなければならない（SHALL）。構成は既存 Autopilot cluster および他の既存 resource を変更または削除してはならない（MUST NOT）。

#### Scenario: Terraform plan のスコープ確認
- **WHEN** operator が clean state から Terraform plan を生成する
- **THEN** plan は検証用と識別できる resource の作成のみを示し、既存 Autopilot cluster の変更または削除を含まない

### Requirement: Reproducible infrastructure
API 有効化、container image repository、専用 Service Account と IAM、Cloud Run service、Custom mode VPC、subnet と GKE secondary ranges、および小規模な VPC-native GKE Standard cluster は Terraform で宣言されなければならない（SHALL）。Provider が Agent Registry resource を提供しない部分だけは、冪等な補助 command として管理してよい（MAY）。

#### Scenario: 新規環境の作成
- **WHEN** 必要な権限を持つ operator が documented variables で Terraform apply と補助 command を実行する
- **THEN** Cloud Run と GKE Standard の検証に必要な resource と Agent Registry entry が再現可能に作成される

### Requirement: Least privilege and bounded cost
workload ごとに専用 Service Account を使用し、IAM role、Cloud Run instance 上限、および GKE node 数・machine type は検証に必要な最小範囲に制限されなければならない（SHALL）。課金対象 resource とコスト抑制上の選択は文書化されなければならない（MUST）。

#### Scenario: セキュリティとコスト設定の確認
- **WHEN** 作成済み resource と IAM binding を inventory する
- **THEN** default Compute Engine Service Account への依存がなく、専用 identity、Cloud Run の上限、GKE の小規模 node 構成、および課金対象 resource 一覧を確認できる

### Requirement: Safe teardown
検証環境は対象を明示した手順で削除可能であり、削除前に対象 resource を確認できなければならない（SHALL）。

#### Scenario: Cleanup plan の確認
- **WHEN** operator が cleanup の事前確認を実行する
- **THEN** 削除対象は `20260823-mcp-server` 検証 resource に限定され、既存 resource は対象に含まれない
