# Common Registry ownership migration

検証日: 2026-08-28
Project/region: `nnyn-dev/us-central1`
Scope: common-owned Registry/control-plane 定義の移管。GKE 本体と private
route の検証はこの記録の対象外。

## 変更内容

`common/terraform` が次の Registry Service を管理する。

| 論理名 | Interface | Service ID |
| --- | --- | --- |
| `github` | `https://github.com` | `agent-gateway-20260828-github` |
| `agentregistry` | `https://agentregistry.googleapis.com` | `mcp-20260823-mcp-server-agentregistry` |
| `aiplatform_global` | `https://aiplatform.googleapis.com` | `mcp-20260823-mcp-server-aiplatform-global` |
| `aiplatform_regional` | `https://us-central1-aiplatform.googleapis.com` | `mcp-20260823-mcp-server-aiplatform` |
| `iamcredentials` | `https://iamcredentials.googleapis.com` | `mcp-20260823-mcp-server-iamcredentials` |

GitHub の既存 Service と endpoint binding は common state に import した。
残り4 Service は旧 live resource が存在しなかったため、common-owned resource
として作成した。common apply は `1 added, 0 changed, 0 destroyed` で、追加分は
実測された Runtime `124453171392151552` の
`aiplatform.googleapis.com` endpoint に対する次の resource-scoped binding である。

```text
roles/iap.egressor
principal://agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/124453171392151552
```

GitHub endpoint の同じ Runtime binding も common state に存在する。`allUsers`、
project-wide Owner/Editor、wildcard host は使用していない。

## Ownership boundary

- `20260822-agent-gateway` から GitHub Service、endpoint data source、GitHub
  endpoint IAM の3 state instanceを除外し、Terraform 定義も削除した。
- `20260823-mcp-server` から4 control-plane Service、endpoint data source、
  endpoint IAM、outputs を除外した。Cloud Run/GKE の consumer-specific
  Service と MCP server IAM は残した。
- consumer の共通リソース削除は実行していない。common の Gateway、VPC、subnet、
  Network Attachment、Authz Extension/Policy は変更していない。

## Verification

実行した確認:

```bash
terraform -chdir=terraform validate
RUN_TERRAFORM_PLAN=1 TF_PLAN_PATH=/tmp/common-final.tfplan ./scripts/validate.sh
terraform -chdir=terraform plan -refresh-only -input=false
openspec validate enable-common-egress-registry-and-private-gke --strict
```

結果:

- common refresh-only plan: `No changes`
- scope guard、unit/static tests: PASS
- OpenSpec strict validation: PASS
- common Gateway ID: `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
- Gateway protocol: `MCP`
- Gateway access path: `AGENT_TO_ANYWHERE`
- Registry scope: `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1`
- Network Attachment: `common-agent-gateway-attachment`
- Authz Extension: `common-egress-iap-authz`, `ENFORCE`, fail-closed
- Authz Policy: `common-egress-iap-policy`

consumer refresh-only plan では common-owned Service/IAM の差分は出なかった。
通常 plan は consumer の既存 Runtime image default と live digest の差分を1件示したが、
これは今回の移管対象外であり apply していない。

## Remaining blocker / next step

Runtime の bounded probe は HTTP 400 で終了した。現時点で `240.0.0.2:443` と
Registry/control-plane destination の対応を一意に証明できず、GKE や CA を原因と
断定していない。`aiplatform.googleapis.com` の Authz deny は実測できたため、global
endpoint の Runtime bindingだけを追加した。regional Vertex と IAM Credentials は
同一 probe で必要性を再確認してから追加する。

GKE private DNS、Internal HTTPS Load Balancer、origin TLS、endpoint authorization、
ClusterIP、Pod execution は後続作業とする。匿名 HTTP、TLS verification bypass、
public frontend、`terraform destroy` は使用しない。
