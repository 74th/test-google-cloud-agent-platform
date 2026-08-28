## Why

Agent Gateway と IAP Authz Extension はプロジェクト内で共有する必要があり、個別検証環境が Gateway を作成・所有する従来の構成は `common` の共有 Gateway と両立しない。共有 Gateway を consumer として利用する構成へ切り替えた上で、過去に実施した egress の許可・拒否・TLS inspection 検証を、Gateway 所有権を変えずに再実行できるようにする。

## What Changes

- この consumer の Terraform とデプロイ設定を、`common/terraform` が出力する fully qualified `agent_gateway_id` を明示入力として受け取り、共有 `common-egress` を Agent Runtime の Agent-to-Anywhere egress に関連付ける構成へ変更する。
- consumer から Gateway、VPC、PSC Network Attachment、IAP Authz Extension、AuthzPolicy の作成・更新・import・削除を除外し、consumer 所有の Runtime、Artifact Registry、Runtime identity、Agent Registry endpoint の IAM、および検証用アプリケーションだけを管理する。
- Gateway の実行時 read-back とログを共通 Gateway ID に対して収集し、Claude Haiku 4.5 の基本呼び出し、`github.com` の許可、`www8.cao.go.jp` の default-deny、TLS inspection CA の信頼を再検証する。
- 各ライブ検証で caller、Runtime effective identity、Gateway ID、宛先、Gateway/IAP 判断、endpoint authorization、アプリケーション側の取得ログを相関可能な証跡として保存する。Agent Runtime MCP E2E は、必要な Registry discovery と MCP 実行証跡が揃う場合にだけ成功と判定する。
- common の Terraform apply、共有 Gateway のポリシー変更、既存 Autopilot GKE の変更、`terraform destroy` はこの変更の実装・検証範囲外とする。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `agent-gateway-egress-validation`: 検証 consumer が専用 Gateway を新規作成する要件を、common-owned Gateway の明示的な入力・非所有利用と、その Gateway に対する再現可能な egress 検証へ変更する。

## Impact

- `terraform/`、デプロイ／Gateway evidence scripts、テスト、README、evidence report の入力契約と実行手順に影響する。
- `../common/terraform` の `agent_gateway_id` output、Google Cloud project `nnyn-dev` の既存 `common-egress`、Claude Haiku 4.5、Agent Platform、Agent Registry/IAP、GitHub、内閣府サイトを利用する。
- 共有 Gateway の lifecycle と Authz 拡張機能は `common` の state および運用 runbook に留まり、この consumer はそれらを変更しない。
