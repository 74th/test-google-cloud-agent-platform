# Spec Delta

## Purpose

MCP Server と GKE Agent Sandbox を検証するための GCP 基盤と Kubernetes リソースを、以前の検証と同じ構成で、再現可能な形で構築・破棄する。

## ADDED Requirements

### Requirement: Terraform で GKE Standard クラスタを構築する
GCP のリソース（API、GKE クラスタ、ノードプール、Artifact Registry、IAM）は `terraform/` の Terraform で定義しなければならない（SHALL）。クラスタは `us-central1-a` のゾーンクラスタ `agent-sandbox-mcp` とし、Standard モードで、Dataplane V2（`ADVANCED_DATAPATH`）、FQDN Network Policy、Workload Identity を有効にしなければならない（SHALL）。対象プロジェクトは tfvars で指定し、既存 VPC `default` を利用しなければならない（SHALL）。`gcloud` による手作業のリソース作成は行ってはならない（MUST NOT）。やむを得ず行う場合は、理由と手順を README に記載しなければならない（SHALL）。

#### Scenario: plan と apply でクラスタが作成される
- **WHEN** オペレータが `terraform plan` の内容を確認してから apply する
- **THEN** `gcloud container clusters describe agent-sandbox-mcp` で Standard モード、`ADVANCED_DATAPATH`、FQDN Network Policy、Workload Pool が有効になっていることを確認できる

#### Scenario: 既存リソースを変更しない
- **WHEN** オペレータが plan を確認する
- **THEN** plan に既存 VPC、兄弟ディレクトリ、`common/` が所有するリソースの変更や削除が含まれていない

### Requirement: gVisor ノードプールとシステムノードプールを分ける
クラスタには、gVisor が無効な `system-pool`（`e2-standard-2` × 1）と、gVisor が有効な `sandbox-pool`（`e2-standard-4` × 1、`GKE_METADATA`）がなければならない（SHALL）。マシンタイプとノード数はこれより大きくしてはならない（MUST NOT）。Sandbox Pod は gVisor ノードでのみ実行しなければならない（SHALL）。MCP Server の Pod は gVisor ノードでなくてよい。

#### Scenario: gVisor の RuntimeClass が使える
- **WHEN** オペレータが `kubectl get runtimeclass gvisor` を実行する
- **THEN** `gvisor` RuntimeClass が存在し、`sandbox-pool` のノードに `sandbox.gke.io/runtime=gvisor` の label と taint が付いている

### Requirement: Agent Sandbox コントローラを導入する
クラスタには、Sandbox、SandboxClaim、SandboxTemplate、SandboxWarmPool の CRD とコントローラを、バージョンを固定して導入しなければならない（SHALL）。GKE のマネージド機能で有効化できる場合はそれを優先し、できない場合はバージョン固定の導入スクリプトでリリース manifest を適用しなければならない（SHALL）。

#### Scenario: CRD とコントローラが利用可能になる
- **WHEN** 導入手順を実行したあとに `kubectl get crd | grep agents` を実行する
- **THEN** 4 種類の CRD が存在し、コントローラの Pod が Ready になっている

### Requirement: Kubernetes リソースはマニフェストで管理する
Namespace `agent-sandbox`、Sandbox Pod 用と MCP Server 用の KSA、RBAC、NetworkPolicy、SandboxTemplate、MCP Server の Deployment / Service（MCP の Streamable HTTP と状態取得用の REST API を同じポートで公開する）は `k8s/` 配下のマニフェストとして `kubectl` で適用しなければならない（SHALL）。Terraform の kubernetes provider でこれらを管理してはならない（MUST NOT）。

#### Scenario: マニフェストを適用できる
- **WHEN** オペレータが `kubectl apply -f k8s/` 相当の手順を実行する
- **THEN** Namespace、KSA、RBAC、NetworkPolicy、SandboxTemplate、MCP Server が作成される

### Requirement: Sandbox Pod は非 root で gVisor 上に起動する
SandboxTemplate から作られる Pod は、`runtimeClassName: gvisor` と gVisor ノード用の nodeSelector・toleration を持ち、非 root ユーザーで実行し、`fsGroup` により `/workspace` に書き込めなければならない（SHALL）。`/workspace` には `standard-rwo` の 1Gi の PVC をマウントしなければならない（SHALL）。

#### Scenario: 非 root で workspace に書き込める
- **WHEN** Sandbox Pod 内で `id -u` と `touch /workspace/x` を実行する
- **THEN** UID は 0 以外で、ファイルの作成に成功する

### Requirement: MCP Server の権限を最小にする
MCP Server の KSA には、Namespace `agent-sandbox` 内の Sandbox 関連リソース、PVC、Pod の参照と exec、および binding 用 Secret の参照に必要な RBAC だけを付与しなければならない（SHALL）。Google Cloud の権限が不要な場合は IAM を付与してはならない（MUST NOT）。サービスアカウントの鍵や GSA は作成してはならない（MUST NOT）。

#### Scenario: Namespace 外のリソースを操作できない
- **WHEN** MCP Server の KSA で別 Namespace の Pod を一覧しようとする
- **THEN** `kubectl auth can-i --as=system:serviceaccount:agent-sandbox:mcp-server` が `no` を返す

### Requirement: 設定は Terraform の output から渡す
クラスタ名、ゾーン、イメージリポジトリなどの設定は Terraform の output から `.env` を作り、検証スクリプトとイメージのビルドスクリプトに渡さなければならない（SHALL）。

#### Scenario: output から .env を作れる
- **WHEN** オペレータが README の手順で `.env` を生成する
- **THEN** `.env` にクラスタ名、ゾーン、イメージリポジトリが含まれる

### Requirement: 検証後に破棄できる
この変更で作成したリソースは `terraform destroy` で破棄できなければならない（SHALL）。破棄はユーザーの承認を得てから実行しなければならない（SHALL）。

#### Scenario: destroy で作成したリソースが削除される
- **WHEN** ユーザーの承認後にオペレータが破棄手順を実行する
- **THEN** この変更で作成したクラスタ、ノードプール、リポジトリが削除され、既存 VPC は残る
