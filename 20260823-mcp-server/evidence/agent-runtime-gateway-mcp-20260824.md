# Agent Runtime → Agent Gateway → Cloud Run MCP E2E検証の証跡

日付: 2026-08-24  
プロジェクト: `nnyn-dev`  
Runtime: `projects/776113568960/locations/us-central1/reasoningEngines/826966334750326784`  
Gateway: `projects/nnyn-dev/locations/us-central1/agentGateways/agw-20260822-egress`

## 構築した経路

既存のGoogle-managed Agent GatewayをRuntimeへ関連付け、Gatewayが参照する
project-scoped Registryに、Cloud Run MCP ServerとGoogle control-plane endpointを登録しました。
Runtime effective identityには、次のendpoint/MCP Server単位で
`roles/iap.egressor` を付与しています。

| 対象 | Registry resource | 目的 |
| --- | --- | --- |
| Agent Registry API | 既存 `20260822 managed agw-20260822-agentregistry` endpoint | Registry Service discovery |
| Vertex AI global | 既存 `20260822 managed agw-20260822-aiplatform-global` endpoint | Claude Vertex API |
| Vertex AI regional | 既存 `20260822 managed agw-20260822-aiplatform` endpoint | Vertex control-plane |
| IAM Credentials | `20260823 IAM Credentials control-plane endpoint` | caller SAのkeyless ID token mint |
| Cloud Run MCP | `mcp-20260823-cloud-run` MCP Server | `/mcp` のMCP通信 |

GatewayのTLS inspection用root CAをRuntime imageへ組み込みました。
検証に使用したRuntime image digestは次の通りです。

```text
sha256:327c47dd2f065936d3e5f5af238964a8e297d311e6a16048dcb7a05dacb135e7
```

caller Service Account `mcp-20260823-mcp-server-caller@nnyn-dev.iam.gserviceaccount.com`
にはCloud Run Invokerを付与し、Runtime effective identityにはそのService Accountの
OpenID token creatorを付与しました。Runtime側は、caller SAが設定されている場合に
`impersonated_credentials.Credentials` と `IDTokenCredentials` を使って、対象Cloud Run
audienceのID tokenを生成します。Service Account keyは使用していません。

## 検証の推移

| 段階 | 結果 | 観測 |
| --- | --- | --- |
| Gateway CAなし | FAIL | Registry discoveryが `SSLError` で停止 |
| Gateway CA追加後 | FAIL closed | Registry REST requestはGatewayへ到達したが、control-plane IAPがHTTP 403 |
| Agent Registry endpoint binding追加後 | FAIL | Registry discoveryはHTTP 200、Vertex endpoint binding不足でClaude APIがHTTP 403 |
| Vertex endpoint binding追加後 | FAIL | caller SA token mintの実装不整合で `token_generation` に停止 |
| IAM Credentials endpointと正しいimpersonation実装追加後 | PASS | MCP Tool実行とCloud Run server-side logまで確認 |

## PASS時の実測

Correlation IDは `mcp-83eba0222c5740c280af9054` です。

| 時刻 (UTC) | 経路 | 実測結果 |
| --- | --- | --- |
| 23:52:38 | Runtime → Agent Registry REST | Gateway request HTTP 200、TLS interception、Registry endpoint resourceを記録 |
| 23:52:38 | Runtime → IAM Credentials | `generateIdToken` HTTP 200、IAM Credentials endpoint resource、Gateway allow |
| 23:52:43 / 23:52:46 | Runtime → Vertex Claude | `streamRawPredict` HTTP 200、Vertex endpoint resource、Gateway allow |
| 23:52:43 | Gateway → Cloud Run `/mcp` | HTTP 200、MCP Server resource、Gateway/IAP allow |
| 23:52:45 | MCP `initialize` | HTTP 202、IAP `AuthorizeUser` の `granted=true` |
| 23:52:49 | MCP Tool execution | HTTP 200、IAP `notifications/initialized` の `granted=true` |
| 23:52:49 | Cloud Run application | `mcp_tool_execution`、`hostingTarget=cloud-run`、同じCorrelation ID |

Runtimeの最終応答は、`validate_echo` が `ok: true` で完了したこと、targetが
`cloud-run` であること、上記Correlation IDを返しました。

## 何を証明したか

今回のPASSは、Registryが単にURLを返しただけではありません。次の一連を同一Runtime
invocationで確認しています。

```text
Agent Runtime
  → Registry discovery (Gateway allow)
  → IAM Credentials token mint (Gateway allow)
  → Vertex Claude API (Gateway allow)
  → Cloud Run MCP endpoint (Gateway allow)
  → IAP endpoint authorization (granted=true)
  → MCP initialize / tools / validate_echo
  → Cloud Run correlation log
```

したがって、Agent GatewayがRegistry metadataを使ってproxyおよびegress認可を行い、
未承認のGoogle control-plane経路やendpointをdefault-denyすることを、今回のMCP Serverで
実測できました。

証跡取得ではtoken、秘密鍵、完全なIAM policy、Gateway証明書本文は保存していません。
