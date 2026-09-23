# Spec Delta

## Purpose

GKE Agent Sandbox を検証するための GCP 基盤を、Terraform を使って再現可能な形で構築・破棄する。基盤には GKE Standard クラスタ、gVisor ノードプール、Agent Sandbox コントローラ、イメージリポジトリ、GCS、IAM を含む。

## ADDED Requirements

### Requirement: Terraform で GKE Standard クラスタを構築する
基盤は Terraform で定義しなければならない（SHALL）。GKE クラスタは Autopilot ではなく Standard モードとし、Dataplane V2、FQDN Network Policy、Workload Identity Federation for GKE を有効にしなければならない（SHALL）。対象プロジェクトは tfvars で指定し、既存 VPC を利用しなければならない（SHALL）。

#### Scenario: plan と apply でクラスタが作成される
- **WHEN** オペレータが `terraform plan` の内容を確認してから apply する
- **THEN** Standard モードのクラスタが作成され、`gcloud container clusters describe` で Dataplane V2（`ADVANCED_DATAPATH`）、FQDN Network Policy、Workload Pool が有効になっていることを確認できる

#### Scenario: 既存リソースを変更しない
- **WHEN** オペレータが plan を確認する
- **THEN** plan に既存 VPC、兄弟ディレクトリ、`common/` が所有するリソースの変更や削除が含まれていない

### Requirement: gVisor ノードプールとシステムノードプールを分ける
クラスタには、gVisor（GKE Sandbox）が有効なノードプールと、gVisor が無効なシステム用ノードプールの両方がなければならない（SHALL）。Sandbox の Pod は gVisor ノードでのみ実行しなければならない（SHALL）。

#### Scenario: gVisor の RuntimeClass が使える
- **WHEN** オペレータが `kubectl get runtimeclass` を実行する
- **THEN** `gvisor` RuntimeClass が存在し、gVisor ノードプールのノードに sandbox 用の label と taint が付いている

### Requirement: Agent Sandbox コントローラを導入する
クラスタには Agent Sandbox の `Sandbox` カスタムリソースとコントローラを、バージョンを固定して導入しなければならない（SHALL）。

#### Scenario: Sandbox CRD が利用可能になる
- **WHEN** 導入手順を実行したあとに `kubectl get crd` を実行する
- **THEN** `sandboxes.agents.x-k8s.io` が存在し、コントローラの Pod が Ready になっている

### Requirement: ワークロード用のリポジトリ、バケット、最小権限の IAM を用意する
Terraform で、コンテナイメージ用の Artifact Registry リポジトリと、プロンプト・応答用の GCS バケットを作成しなければならない（SHALL）。Sandbox Pod が使う Kubernetes ServiceAccount の principal には、Vertex AI の利用権限と、そのバケットに限定したオブジェクト読み書き権限だけを付与しなければならない（SHALL）。サービスアカウントの鍵は作成してはならない（MUST NOT）。

#### Scenario: IAM が最小権限になっている
- **WHEN** オペレータが IAM の設定を確認する
- **THEN** KSA principal にはプロジェクトの `roles/aiplatform.user` と、対象バケットの `roles/storage.objectUser` だけが付与されている

### Requirement: 検証後に破棄できる
検証で作成したリソースは、手順に沿って破棄できなければならない（SHALL）。

#### Scenario: destroy で作成したリソースが削除される
- **WHEN** オペレータが破棄手順を実行する
- **THEN** この変更で作成したクラスタ、ノードプール、バケット、リポジトリ、IAM バインディングが削除され、既存 VPC は残る
