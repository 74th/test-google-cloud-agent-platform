# common: 共有 Agent Gateway 基盤

`common` は、実験間で共有する Agent Gateway の**基盤を作成・所有する**
Terraform root です。個別の Agent Runtime、Agent Registry Service、MCP
endpoint、GKE、Cloud Run はここでは管理しません。

## 管理対象

プロジェクト `nnyn-dev`、リージョン `us-central1` に、次の common-owned
resource を作成・維持します。

- `common-agent-gateway-vpc` と専用 `/28` subnet
- `common-agent-gateway-attachment`（PSC Network Attachment）
- `common-egress`（`AGENT_TO_ANYWHERE`、`MCP`）
- IAP Authz Extension と、それを `common-egress` にのみ関連付ける
  AuthzPolicy
- 上記に必要な API enablement state

この Terraform state は `common/terraform` に閉じています。利用側は common
resource を import したり、更新・削除したりしません。

## 利用側との契約

consumer は remote state を読む代わりに、デプロイ時に common の output を
明示入力として受け取ります。最低限必要なのは次です。

```bash
terraform -chdir=terraform output -raw agent_gateway_id
```

出力される fully qualified Gateway ID を、consumer の Agent Runtime 設定へ
渡してください。VPC、subnet、Network Attachment、AuthzPolicy の ID は
consumer の所有物ではありません。

consumer が所有するものは、Agent Runtime、Agent Registry Service、Runtime
identity と resource-scoped IAM、private DNS、MCP endpoint、GKE/Cloud Run、
endpoint authorization、およびアプリケーション実行ログです。

## 検証の担当境界

common は、Terraform plan の範囲、Gateway/Network Attachment の read-back、
Authz resource の作成後 read-back、ならびに non-secret evidence を担当します。
common での apply は、レビュー済み plan と明示承認を必要とします。

Agent Gateway 自体の機能・認可・TLS inspection・許可/拒否の負例検証は
[`20260822-agent-gateway`](../20260822-agent-gateway/README.md) が担当します。
共有 Gateway を利用する consumer は、その検証方針と evidence 形式に従って
Gateway log を収集します。common 側の Registry discovery 成功、Gateway
`ALLOWED`、または private route 到達だけを Agent Runtime MCP E2E の成功とは
扱いません。

GKE endpoint の private routing、origin TLS、endpoint authorization、Pod 上の
MCP execution は consumer/GKE 側の検証対象です。

## 運用

事前確認、plan review、適用、read-back、rollback の手順は
[docs/runbook.md](docs/runbook.md) を参照してください。通常の確認は次で行います。

```bash
terraform -chdir=terraform init
./scripts/validate.sh
RUN_TERRAFORM_PLAN=1 ./scripts/validate.sh
```

`terraform destroy`、consumer resource の import、既存 Autopilot GKE の変更、
匿名 HTTP、TLS verification bypass は common の運用範囲外です。
