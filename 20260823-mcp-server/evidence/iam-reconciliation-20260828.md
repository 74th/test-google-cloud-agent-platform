# consumer IAM 責務分離証跡（2026-08-28）

この証跡は `common-egress` の共有所有権を変更せず、consumer Runtime の各認証責務を分離して確認した結果です。token、秘密鍵、証明書本文、完全な IAM policy は保存していません。

Runtime の effective identity は次の1つです。

`principal://agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528`

| 責務 | 付与先と権限 | 実測した主体・範囲 | 判定 |
| --- | --- | --- | --- |
| Registry discovery | `nnyn-dev` の `roles/agentregistry.viewer` | 上記 Runtime principal のみ。URLの任意入力はclientで拒否 | PASS |
| Agent Registry / Vertex / IAM Credentials egress | 各 consumer-owned Registry endpoint の `roles/iap.egressor` | 同じ Runtime principal。4 control-plane endpoint と Cloud Run MCP Server の resource scope | PASS |
| Vertex API | `nnyn-dev` の `roles/aiplatform.user` | 上記 Runtime principal のみ。Claude の Vertex 呼び出し責務と egress を別 binding で管理 | PASS |
| Cloud Run Invoker | Cloud Run `mcp-20260823-mcp-server-run` の `roles/run.invoker` | `mcp-20260823-mcp-server-caller` と専用 test invoker。`allUsers` なし | PASS |
| ID token mint | caller Service Account の `roles/iam.serviceAccountOpenIdTokenCreator` | 上記 Runtime principal → `mcp-20260823-mcp-server-caller` のみ | PASS |
| Runtime image pull | `mcp-20260823-mcp-server-agent` repository の `roles/artifactregistry.reader` | Vertex AI Reasoning Engine Service Agent `service-776113568960@gcp-sa-aiplatform-re.iam.gserviceaccount.com` | PASS |

## 再現コマンドと結果

```text
terraform -chdir=terraform state list
terraform -chdir=terraform plan -refresh-only -no-color -detailed-exitcode \
  -var='agent_gateway_id=projects/nnyn-dev/locations/us-central1/agentGateways/common-egress' \
  -var='container_image=<reviewed digest>' \
  -var='agent_runtime_image=<reviewed digest>'
```

結果は `No changes. Your infrastructure still matches the configuration.` でした。

```text
gcloud projects get-iam-policy nnyn-dev \
  --flatten='bindings[].members' \
  --filter='bindings.members:reasoningEngines' \
  --format='table(bindings.role,bindings.members)'
gcloud iam service-accounts get-iam-policy \
  mcp-20260823-mcp-server-caller@nnyn-dev.iam.gserviceaccount.com
gcloud run services get-iam-policy mcp-20260823-mcp-server-run \
  --region=us-central1 --project=nnyn-dev
gcloud artifacts repositories get-iam-policy mcp-20260823-mcp-server-agent \
  --location=us-central1 --project=nnyn-dev
```

Project-level `roles/agentregistry.viewer` と `roles/aiplatform.user` は Google API の discovery/model authorization に必要な consumer binding として、Runtime principal を明示して別々に管理しています。Gateway egress は project IAM ではなく Registry endpoint/MCP Server resource binding だけです。Cloud Run Invoker、ID token mint、Artifact Registry pull はそれぞれ異なる主体と resource scope であり、互いの権限を代用しません。

この文書の構成・IAM read-back 判定は invocationではないため `correlation_id=N/A (inventory/read-back)` です。Runtime probeの実行結果と相関情報の有無は [`common-egress-runtime-blocker-20260828.md`](common-egress-runtime-blocker-20260828.md) に分離しています。
