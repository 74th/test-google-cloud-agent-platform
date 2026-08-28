## ADDED Requirements

### Requirement: 共有 Gateway の明示入力と非所有利用
システムは、common-owned Agent Gateway の fully qualified ID を consumer の明示入力として受け取り、その ID を Agent Runtime の Agent-to-Anywhere egress に使用しなければならない（SHALL）。consumer は、Gateway、VPC、subnet、PSC Network Attachment、IAP Authz Extension、AuthzPolicy を作成、更新、import、または削除してはならない（MUST NOT）。入力 ID が空、形式不正、または `nnyn-dev/us-central1` の Agent Gateway を示さない場合、consumer の plan またはデプロイは Gateway を新規作成せずに失敗しなければならない（MUST）。

#### Scenario: common output を用いる consumer 構築
- **WHEN** 操作者が `common/terraform` の `agent_gateway_id` output を consumer の文書化された入力へ渡して Infrastructure as Code を適用する
- **THEN** consumer-owned Runtime と検証リソースだけが作成または更新され、Runtime は指定された Gateway ID を参照する
- **AND** plan と state に consumer-owned Gateway、VPC、Network Attachment、Authz Extension、AuthzPolicy が含まれない

#### Scenario: Gateway 入力が無効である
- **WHEN** 操作者が空、形式不正、または対象プロジェクト・リージョン外の Gateway ID を渡して plan またはデプロイを実行する
- **THEN** 操作は Gateway を作成または変更せずに失敗し、必要な common output を指定するよう報告する

### Requirement: 共有 Gateway に対する完全な egress 検証証跡
システムは、共有 Gateway を用いるライブ検証ごとに、認証済み caller、Runtime effective identity、fully qualified Gateway ID、対象 URL と宛先ホスト、Agent Runtime 呼び出し結果、Gateway または IAP の許可・拒否判断、アプリケーション側の取得ログを同一の検証識別子または時刻範囲で相関可能な形で保存しなければならない（SHALL）。Registry discovery、Gateway `ALLOWED`、private route 到達、または operator 側 smoke test だけを Agent Runtime MCP E2E 成功として扱ってはならない（MUST NOT）。

#### Scenario: GitHub 許可検証の証跡
- **WHEN** 操作者が共有 Gateway 配下のデプロイ済みエージェントへ GitHub 検証指示を送信する
- **THEN** 保存される証跡は caller、Runtime effective identity、Gateway ID、`github.com`、Agent Runtime の結果、許可判断、およびアプリケーション取得ログを相関できる

#### Scenario: 内閣府 default-deny 検証の証跡
- **WHEN** 操作者が共有 Gateway 配下のデプロイ済みエージェントへ未許可の内閣府 URL の検証指示を送信する
- **THEN** 保存される証跡は caller、Runtime effective identity、Gateway ID、`www8.cao.go.jp`、Agent Runtime の結果、default-deny 判断、およびアプリケーション取得失敗ログを相関できる

## MODIFIED Requirements

### Requirement: 再現可能で独立した検証環境
システムは、Google Cloud プロジェクト `nnyn-dev` の `us-central1` に、BYOC エージェント、実行サービスアカウント、および検証に必要な consumer-owned 関連リソースを Infrastructure as Code から作成または更新できなければならない（SHALL）。システムは `common/terraform` が所有し出力した fully qualified Agent Gateway ID を明示入力として使用しなければならず（MUST）、Agent Gateway またはその VPC、subnet、PSC Network Attachment、IAP Authz Extension、AuthzPolicy を新規作成、更新、import、または削除してはならない（MUST NOT）。作成する consumer-owned リソース名は `20260801-agent-hosting` のリソース名と重複してはならない（MUST NOT）。

#### Scenario: 空の環境への構築
- **WHEN** 操作者が文書化された前提条件を満たし、common の `agent_gateway_id` output を入力して Infrastructure as Code を適用する
- **THEN** 検証に必要な consumer-owned リソースが新しい名前で作成または更新され、デプロイに必要な識別子が出力される
- **AND** Agent Runtime は入力された Gateway ID を参照し、consumer の plan に Gateway または common-owned network/Authz resource の作成・変更・import・削除がない

#### Scenario: Gateway 入力が無効である
- **WHEN** 操作者が空、形式不正、または対象プロジェクト・リージョン外の Gateway ID を渡して plan またはデプロイを実行する
- **THEN** 操作は Gateway を作成または変更せずに失敗し、必要な common output を指定するよう報告する

#### Scenario: 検証環境の削除
- **WHEN** 操作者が文書化されたクリーンアップ手順を確認する
- **THEN** 手順は consumer-owned リソースと common-owned Gateway の所有境界を明示し、`terraform destroy` または共有 Gateway の削除を自動実行しない
