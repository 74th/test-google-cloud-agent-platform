## MODIFIED Requirements

### Requirement: Reproducible infrastructure
API有効化、container image repository、専用Service AccountとIAM、Cloud Run service、Custom mode VPC、subnetとGKE secondary ranges、小規模なVPC-native GKE Standard cluster、Agent Runtime、専用Agent Gateway、Registry endpoint egress IAM、およびGKEの認証付きHTTPS入口は再現可能なinfrastructure definitionで宣言されなければならない（SHALL）。Providerが安定したresourceを提供しない部分だけは、対象と結果を検証する冪等な補助commandとして管理してよい（MAY）。

#### Scenario: 新規環境の作成
- **WHEN** 必要な権限を持つoperatorがdocumented variablesでinfrastructure applyと補助commandを実行する
- **THEN** Registry管理、Agent Runtime、Cloud Run認可、GKE認証付き到達経路、およびE2E検証に必要なresourceが再現可能に作成される

## ADDED Requirements

### Requirement: Dedicated Agent Runtime identity
検証用Agent Runtimeは専用identityで稼働し、Registry read、Cloud Run invocation、GKE endpoint access、およびモデル推論に必要な権限を用途別の最小権限bindingとして付与されなければならない（SHALL）。

#### Scenario: Runtime IAM inventory
- **WHEN** Agent Runtimeの実効identityとIAM bindingをinventoryする
- **THEN** Registry mutation権限、owner/editor、Service Account key、および対象外resourceへの実行権限が存在しない

### Requirement: GKE authenticated ingress is isolated
GKEのAgent Runtime向け入口はHTTPSとcaller認証を必須とし、backend MCP Serviceを直接Internetへ公開してはならない（MUST NOT）。cluster-local検証経路とAgent Runtime向け経路は識別可能でなければならない（SHALL）。

#### Scenario: GKE公開面のinventory
- **WHEN** operatorがGKE Service、Gateway／Ingress、Load Balancer、backend、および認可設定を確認する
- **THEN** Agent Runtime向けの認証付き入口だけが外部到達可能で、MCP PodとClusterIP Serviceは直接公開されていない
