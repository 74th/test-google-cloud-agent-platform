# Agent Runtimeと既存Gatewayのapply証跡

日付: 2026-08-24  
プロジェクト: `nnyn-dev`

## 構成判断

Googleでは、projectとgoverned directionごとにactiveなAgent Gatewayを1つだけ利用できます。
重複していたexperimentの `mcp-20260823-egress` Gateway、
`mcp-20260823-mcp-server-iap-policy`、`mcp-20260823-mcp-server-iap-authz` resourceは削除しました。
既存の `agw-20260822-egress` GatewayはactiveなままIDで参照しています。このTerraform stateでは管理していません。

## applyしたresource

- Runtime: `projects/776113568960/locations/us-central1/reasoningEngines/826966334750326784`
- Runtime display name: `mcp-20260823-runtime`
- Runtime identity type: `AGENT_IDENTITY`
- Effective identity: `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/826966334750326784`
- Gateway attachment: `projects/nnyn-dev/locations/us-central1/agentGateways/agw-20260822-egress`
- 最終検証Runtime image: `sha256:327c47dd2f065936d3e5f5af238964a8e297d311e6a16048dcb7a05dacb135e7`

最初のRuntime作成でimage read errorが返ったため、Google managed Agent Platform Service
Agentにrepository単位の `roles/artifactregistry.reader` を付与しました。その後、Runtimeの作成に成功しました。

Runtime effective identityには、Registry viewer、Registry/Vertex/IAM Credentialsの
control-plane endpoint egress、caller Service AccountのOpenID token creator、Cloud Runの
MCP-server単位 `roles/iap.egressor` bindingを付与しました。Cloud RunのInvokerはcaller
Service Accountだけに付与し、project-wideのowner/editorやService Account keyは作成していません。

GatewayのTLS inspection用root CAをRuntime imageへ組み込みました。caller Service Accountが
設定されている場合、RuntimeはそのService Accountをkeylessにimpersonateして対象audienceの
ID tokenを生成します。

## 初期Runtime invocation

初期のRuntime queryは、Gateway root CAがimageにないため、Agent Registry REST APIの
`registry_discovery` 段階でsanitizedな `SSLError` によりfail closedしました。

その後、Gateway root CAを組み込んだimageではRegistry REST requestがGatewayまで到達しましたが、
Agent Registry control-plane endpointのIAP policyがHTTP 403を返しました。control-plane
endpointのRuntime bindingを追加し、さらにVertex AI global/regional endpointとIAM Credentials
endpointをRegistryに登録してRuntime principalをbindingしました。

## 最終E2E結果

追加構成後、Cloud Run objectiveのRuntime queryは成功しました。Correlation IDは
`mcp-83eba0222c5740c280af9054` です。Registry discovery、IAM Credentialsの
`generateIdToken`、Vertex Claude API、Cloud Run `/mcp`、IAP authorization、Cloud Runの
`mcp_tool_execution` logを確認しました。詳細なallow証跡は
[`agent-runtime-gateway-mcp-20260824.md`](agent-runtime-gateway-mcp-20260824.md) に記録しています。

この証跡が示すのは、resource作成とIAM構成だけでなく、既存Agent Gatewayを経由したCloud Run
MCP Tool executionのPASSです。GKE HTTPS front doorとGKE Agent Runtime E2Eは別の未実施項目です。
