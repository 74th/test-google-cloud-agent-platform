# Agent Registry MCP Server 検証結果

## 2026-08-28 migration status

The shared `common-egress` Gateway was inventoried on 2026-08-28 and remains
owned by `common`. This repository no longer creates or owns an Agent Gateway.
Its Terraform requires the reviewed shared `agent_gateway_id` as an explicit
input from `common`; the reviewed consumer plan was applied as a no-op on
2026-08-28. The historical results below describe the 2026-08-23/24 old-Gateway
run and are not
evidence that the new shared-Gateway E2E has passed.

## 20260823 governed Agent Runtime change status

この変更では、Cloud Run と GKE の MCP endpoint を Agent Runtime 上の
Claude Agent SDK から Registry 管理下で利用し、Registry discovery、Agent
Gateway egress、endpoint authorization、MCP Tool execution を分離して検証
します。runtime image は `claude-agent-sdk==0.1.9` を固定し、URL は prompt
や環境変数から受け付けず、固定した Registry Service ID から毎 invocation
解決します。credential は短期 audience-bound ID token とし、token/key/API
key はログや evidence に保存しません。

local SDK contract、Cloud Run/GKE backend、Registry metadata validation、旧
Gateway を使った Agent Runtime baseline、consumer 固有 Registry/MCP server IAM、
Cloud Run endpoint egress binding、および旧 Gateway 経由の Cloud Run MCP E2E は
完了しています。共通 control-plane Registry Service は [`common`](../common/README.md)
が所有し、Runtime 固有の common endpoint egress binding はこの consumer
workspace が所有します。
`common-egress` 移行後の Cloud Run E2E は完了し、GKE E2E は未完了です。
Google Cloud の project/direction 単位の Gateway 排他制約に合わせ、専用
`mcp-20260823-egress` は削除し、既存 Gateway は Terraform で管理せず参照だけ
しています。今回の consumer Runtime は
`projects/776113568960/locations/us-central1/reasoningEngines/8548154799411953664`
で、effective identity は Runtime resource principal です。関連付け先は
完全修飾された `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
です。

GKEについては、ClusterIP backend、private DNS、proxy-only subnet、および
`gce-internal` Internal HTTPS Load Balancer frontendまで構築し、GKE Podから
trusted TLS経由のMCP実行を確認しました。Cloud RunのAgent Runtime queryは
common endpoint IAM binding移管後に成功し、Gateway、Cloud Run、Claude Tool、
MCP executionの相関を確認しました。GKEについてはendpoint authorization、
Claude Tool selection、RuntimeからPodまでの相関は未確認で、
`gke_mcp_hostname` と `gke_auth_audience` を必須 prerequisite とし、認証付きE2Eを
匿名公開やplain HTTPへフォールバックして完了扱いにしません。詳細は
[`evidence/gke-common-egress-ilb-20260828.md`](evidence/gke-common-egress-ilb-20260828.md)、
[`evidence/backend-validation-20260824.md`](evidence/backend-validation-20260824.md)、
[`evidence/gke-prerequisite-20260823.md`](evidence/gke-prerequisite-20260823.md) を参照してください。

その後、GKE Gateway APIをStandard channelで有効化し、`gke-l7-rilb` の
regional `INTERNAL_MANAGED` Gatewayを追加しました。`NamedAddress` の静的VIP
`10.240.0.6`、HTTPRoute、HealthCheckPolicy、Gateway専用ClusterIPを使った
VPC内HTTP診断では、通常のGKE Podから `initialize` と `tools/call` がHTTP 200に
なり、Podのserver-side logまで相関できました。これはprivate HTTPの経路診断で
あり、IAP、endpoint authorization、Agent Runtime E2EのPASSではありません。
詳細は [`evidence/gke-gateway-api-http-diagnostic-20260829.md`](evidence/gke-gateway-api-http-diagnostic-20260829.md) を参照してください。

Google Cloud Agent Registry から MCP Server を発見し、Cloud Run と GKE Standard の両方で実行できることを検証した記録です。

検証日: 2026-08-23  
プロジェクト: `nnyn-dev`  
リージョン: `us-central1`

## 結論

今回の stateless MCP Server には Cloud Run が適しています。IAMによる認証、Agent Registryからの発見、`common-egress` Agent Gateway経由のMCP実行を、Claude Tool eventとserver-side logの相関付きで確認でき、最小インスタンス数を `0` に設定できます。旧 baseline は historical comparison として分離しています。

GKE Standard でも cluster-local と内部 HTTPS/Gateway API の経路検証は成功しましたが、専用 VPC、サブネット、Pod/Service secondary range、クラスタ、ノードプール、Kubernetes workload が必要です。Agent Runtime 向けの認証付き E2E は、publicly trusted origin certificate と IAP/equivalent authorization が未準備のため未完了です。

## 今回検証した連携方式

Agent RegistryはMCP requestを中継するproxyではなく、MCP ServerとToolのメタデータを管理・発見するcontrol planeです。従来のruntime-only検証では、Registryで実行先URLを発見した後、clientがそのURLへ直接接続しました。

```text
MCP Serverをデプロイ
        ↓
scripts/registry.shでAgent Registryへ手動登録
        ↓
Agent RegistryでServer／Toolを検索
        ↓
検索結果のinterface URLへclientが直接接続
        ↓
initialize → tools/list → tools/call
```

今回の Agent Runtime 経路は次の構成です。RuntimeはURLを入力から受け取らず、固定Service ID `mcp-20260823-cloud-run` をAgent Registry REST APIから解決します。Registry discovery は `common-egress` 経由で実行され、2026-08-29 の再検証では Gateway allow、Cloud Run authorization、Claude Tool selection、MCP executionを同一 correlation IDで確認しました。詳細は [`evidence/cloud-run-common-egress-validation-20260829.md`](evidence/cloud-run-common-egress-validation-20260829.md) を参照してください。2026-08-28 の `240.0.0.2:443` `default_denied` は移管前の historical blockerです。

```text
Agent Runtime query
        ↓
Agent Registry REST discovery
        ↓ (Agent Gateway経由)
common-egress → Cloud Run MCP endpoint
        ↓
metadata validation → IAM Credentials endpoint → audience token
        ↓
Claude Agent SDK → MCP initialize / tools / validate_echo
```

Cloud Run と GKE のどちらも、Agent Registry への登録は [`scripts/registry.sh`](scripts/registry.sh) から `gcloud agent-registry services create/update` を実行しました。MCP Server の表示名、説明、interface URL、`JSONRPC` protocol binding、Tool spec はこの登録処理で渡しています。

従来の backend 回帰では、Cloud Run は operator の専用 invoker identity、GKE は同一クラスタ内の Node.js 検証 Pod から実行しました。旧 Gateway の結果は historical baseline として分離しています。今回の `common-egress` 検証ではCloud Runは相関付きでPASS、GKEはGateway `ALLOWED` 後のILB HTTP 503で停止しました。詳細は [`evidence/gke-common-egress-validation-20260829.md`](evidence/gke-common-egress-validation-20260829.md) を参照してください。

### Cloud Runに必要な追加認証

Cloud RunはAgent Gatewayを通過するだけでは呼び出せません。今回のCloud Run経路では、次の認証・認可を別々に構成しました。

1. Agent Runtimeのeffective identityに、RegistryのCloud Run MCP Server resource単位で `roles/iap.egressor` を付与する。これはAgent GatewayがMCP endpointへのegressを許可するための権限です。
2. Cloud Run Serviceには、専用caller Service Accountだけに `roles/run.invoker` を付与する。`allUsers` は付与しません。
3. Runtimeのeffective identityには、caller Service Accountに対する `roles/iam.serviceAccountOpenIdTokenCreator` を付与する。RuntimeはService Account keyを使わず、keyless impersonationでcaller Service AccountとしてID tokenを発行します。
4. 発行するID tokenのaudienceをCloud Run Service URIと完全一致させ、MCP requestのAuthorization headerに付与する。Cloud Run側がこのtokenとInvoker権限を検証してからMCP処理を開始します。

したがって、Cloud Runについては専用のLoad Balancerを準備しなくても、Cloud Runが提供するHTTPS endpointをAgent Gatewayから利用できます。必要なのは、Gatewayのegress認可とCloud Run側のIAM認証の両方です。Gatewayの許可はCloud Runの `roles/run.invoker` を代替しません。

GKEのDeployment Manifestには、MCP Server／ToolをAgent Registryへ登録するためのメタデータやannotationは記述していません。Manifest内のannotationはWorkload Identity用だけです。したがって、今回確認したのは「GKE上のMCP Serverを手動でAgent Registryに登録して利用する方式」であり、Manifestを監視するcontrollerなどによる自動登録方式ではありません。

## 構成

- Node.js 20 の MCP Server
- Streamable HTTP を使用する `/mcp` エンドポイント
- ヘルスチェック用 `/healthz`
- 検証用 Tool: `validate_echo`
- Tool spec: [`toolspec.json`](toolspec.json)
- Agent Registry の登録・検索: [`scripts/registry.sh`](scripts/registry.sh)
- Terraform: [`terraform/`](terraform/)
- Kubernetes manifest template: [`k8s/mcp.yaml.tmpl`](k8s/mcp.yaml.tmpl)

`validate_echo` は入力値を検証し、決定的なレスポンスを返します。Tool 名、説明、入力スキーマは MCP Server と Agent Registry に登録する Tool spec で一致させています。

## 検証結果

| 項目 | 結果 | 概要 |
| --- | --- | --- |
| ローカル MCP protocol | PASS | `initialize`、`tools/list`、正常な `tools/call`、不正入力を確認 |
| Tool spec 整合性 | PASS | `npm run check:tool-spec` とコンテナ経由のチェックに成功 |
| Docker build / smoke test | PASS | 非 root コンテナで起動・MCP smoke test に成功 |
| Terraform backend apply (historical) | HISTORICAL PASS | Cloud Run、専用 GKE Standard、VPC、Registry Service を experiment prefix で構築。今回の common-egress migration stateとは別の旧backend結果 |
| Agent Gateway 構成 | PASS (inventory) | `common-egress` の owner output/live API、属性、Network Attachment、CA fingerprintを確認。共有resourceはconsumer state外 |
| Agent Runtime 作成 | PASS | `mcp-20260823-runtime`、`AGENT_IDENTITY`、immutable image digest を適用 |
| Runtime IAM | PASS | common endpoint の Runtime-specific egress、MCP server egress、repository-scoped Artifact Registry reader、caller SA token creator を consumer 側で管理 |
| Cloud Run Registry egress binding | PASS | Runtime effective identity に MCP-server-scoped `roles/iap.egressor` を付与 |
| Cloud Run 認証済み baseline (historical) | HISTORICAL PASS | 2026-08-23 の専用 invoker 検証で `initialize`、`tools/list`、`validate_echo` が HTTP 200 |
| Cloud Run 未認証実行 (historical) | HISTORICAL PASS | 2026-08-24 の再検証で MCP 応答前に HTTP 403 で拒否 |
| Cloud Run scaling (historical) | HISTORICAL PASS | `min=0`、`max=3`。idle 時の instance count `0` を観測 |
| Agent Runtime Registry discovery (`common-egress`) | PASS | Runtimeが `mcp-20260823-cloud-run` と Cloud Run host を解決。旧 `240.0.0.2:443` blockerは解消 |
| Agent Runtime Claude / Cloud Run E2E (`common-egress`) | PASS | Claude Tool event、Gateway `ALLOWED`、Cloud Run HTTP 200、server-side MCP logを correlation IDで相関。詳細は [`evidence/cloud-run-common-egress-validation-20260829.md`](evidence/cloud-run-common-egress-validation-20260829.md) |
| Cloud Run authorization negatives (`common-egress`) | PARTIAL | tokenなし HTTP 403 と unauthorized operator credential HTTP 401、および application log不在を確認。wrong audience / separate unauthorized ID tokenは mint権限不足でSKIP。詳細は [`evidence/cloud-run-common-egress-negative-20260829.md`](evidence/cloud-run-common-egress-negative-20260829.md) |
| GKE Standard 構築 (historical) | HISTORICAL PASS | 専用 VPC、secondary range、`e2-small` 1ノードで Ready |
| GKE cluster-local MCP 実行 (historical) | HISTORICAL PASS | Deployment rollout、validation Job、Pod 内 smoke test に成功 |
| GKE Gateway API private HTTP routing | PASS (diagnostic only) | `gke-l7-rilb` / `HTTPRoute` / NEG / Gateway専用ClusterIPを経由したPod-side MCP 200。認証付きE2Eではない |
| Agent Runtime → `common-egress` → Gateway API HTTP | FAIL (routing diagnostic) | 明示的な`gke-http-diagnostic` targetでHTTPを許可して再build後に実行。GatewayはHTTP requestを受け`ALLOWED`したがHTTP 400でorigin delivery前に停止し、Runtimeは`tool_execution`、GKE Pod実行logなし。詳細は [`evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md`](evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md) |
| GKE Gateway API through `common-egress` | FAIL before origin execution | HTTPS listener `10.240.0.6:443` は `Programmed=True`、Gateway/Authz は `ALLOWED`。private test CAのorigin TLSでHTTP 503、GKE application executionなし。詳細は [`evidence/gke-gateway-api-common-egress-20260829.md`](evidence/gke-gateway-api-common-egress-20260829.md) |
| GKE Agent Runtime 向け HTTPS | SKIP | trusted certificate、IAP OAuth client/secret、IAP audienceが未準備 |
| GKE Agent Runtime / Claude E2E | FAIL | HTTPS ILB経路はGateway `ALLOWED`後にorigin private CAでHTTP 503。Claude Tool/server-side executionなし |
| Cloud Run cold / warm latency | SKIP | operator の ID token mint 権限が一時的に拒否され、測定を実施せず |

Cloud Run の IAM には専用 invoker/caller Service Account のみを付与し、`allUsers` は付与していません。既存 Gateway は Terraform で管理せず、Runtime の関連付け先として参照しています。GKE 検証では既存の Autopilot クラスタを変更していません。

今後追加する検証も、対象、構成、実施手順、実測結果、証跡、未確認事項、cleanup状態をこのREADMEへ追記します。設定から推測した結果はPASSにせず、実行できなかった項目は理由を添えてSKIPまたは未確認として残します。

## Agent Registry 検証

Agent Registry の CLI で `JSONRPC` protocol binding を指定して、次の3つの consumer Service を登録しました。

| 実行基盤 | Registry Service | Interface |
| --- | --- | --- |
| Cloud Run | `mcp-20260823-cloud-run` | Cloud Run の `/mcp` URL |
| GKE | `mcp-20260823-gke` | `https://gke.mcp-20260823.internal/mcp` |
| GKE Gateway API HTTP diagnostic | `mcp-20260823-gke-http-diagnostic` | `http://gke-gateway-http.mcp-20260823.internal/mcp` |

`gcloud agent-registry mcp-servers search` で3件が検索でき、各結果に interface と `validate_echo` の metadata が含まれることを確認しました。

### GKEで実施した検証手順

1. Terraformで専用VPC、subnet、Pod/Service secondary range、GKE Standardクラスタ、node pool、Service Accountを作成しました。
2. Cloud Runと同じimmutable image digestを、Deploymentとvalidation Jobへ設定しました。
3. `ClusterIP` Serviceを作成し、MCP endpointのbackendをクラスタ内の `10.242.0.20:80` に固定しました。
4. `kubectl rollout status` でDeploymentがReadyになることを確認しました。
5. validation Jobで同じcontainer imageの `node scripts/local-smoke.mjs` を実行し、MCP Serverへ直接接続して `initialize`、`tools/list`、正常なTool call、不正入力を確認しました。
6. `gce-internal` Internal HTTPS Load Balancer、private DNS、TLS Secretを作成し、Registryには `https://gke.mcp-20260823.internal/mcp` を登録しました。
7. Agent Registry検索結果にGKE用Server、interface、`validate_echo` が含まれることを確認しました。
8. root CAを信頼する一時PodからILBへTLS 1.3で接続し、同じNode.js clientからMCP flowが成功することを確認しました。
9. GKE Gateway API Standard channel、`gke-l7-rilb`、`NamedAddress` VIP、HTTPRoute、HealthCheckPolicyを追加し、HTTP診断で同じPodへの到達を確認しました。
10. Gateway APIにHTTPS listenerを追加し、consumer TerraformのDNSを一時的にGateway VIPへ向けて、common-egress経由のAgent Runtime queryを実施しました。Gateway/Authzは`ALLOWED`でしたが、private origin CAでHTTP 503となり、実行証跡はありませんでした。検証後DNSは既存ILBへ復元しました。
11. HTTPS-only検証を変更せず、明示的な`gke-http-diagnostic` Registry ServiceとHTTP許可ターゲットを追加し、Runtimeからcommon-egressへHTTP requestを送信しました。Gatewayは`ALLOWED`後HTTP 400を返し、origin `serverIp`とGKE Pod execution logはありませんでした。詳細は [`evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md`](evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md) です。

この検証により、Kubernetes上での起動確認、Agent Registryの検索確認、ILB/Gateway APIからClusterIP backendへの到達確認を分離して記録しています。Agent RuntimeからGateway APIへの到達は、HTTPSではGatewayの`ALLOWED`後にHTTP 503、明示的HTTP診断では`ALLOWED`後にHTTP 400で停止しており、どちらもGKE E2E成功とは扱いません。

この一時Pod／JobはClaude Agent SDKではなく、MCP protocolだけを確認するNode.js smoke clientです。Agent Runtime上のClaude Agent SDKはGKE targetと明示的なHTTP diagnostic targetで呼び出しましたが、Gatewayの`ALLOWED`後にそれぞれHTTP 503/400となり、Runtime経由のremote Tool executionは成立していません。

GKE側には `ClusterIP` Serviceをbackendとする `gce-internal` Internal HTTPS
Load Balancerと、比較用のGKE Gateway API regional internal ALBを構築しました。
GKE内のTLS検証付きMCP callは成功しましたが、`common-egress` からの
`initialize` はGatewayの `ALLOWED` 後にHTTP 503で停止しています。endpoint
authorization、Claude Tool selection、RuntimeからPodまでの相関は未確認で、
GKEのILB/backend smokeとGateway API HTTP診断をAgent Runtime E2Eとは呼びません。

```text
同一GKEクラスタ／namespace

Node.js validation Pod / Job
        ↓ http://mcp-20260823-mcp-server/mcp
ClusterIP Service :80
        ↓
MCP Server Pod :8080
```

### GKEのClusterIPとAgent Runtimeからの到達性

今回のGKE `ClusterIP` は、GKEクラスタ内部のPodからのみ到達できるbackendです。Managed Agent RuntimeからGKEのClusterIPへ到達する経路は確認できていないため、`ClusterIP` のままではAgent Runtime → Agent Gateway → GKE MCP Serverの実通信は成立しません。今回のGKE cluster-local結果はhistorical PASSであり、あくまで同一クラスタ内のNode.js検証Podからの接続です。

`ClusterIP` を単純に `LoadBalancer` Serviceへ変更すればネットワーク入口は作れますが、TLS、認証、audience、Gatewayのegress許可を別途構成しない限り、Agent Runtime向けの安全な接続経路を証明したことにはなりません。今回想定する構成は、`ClusterIP` Serviceをbackendとして保持し、GKE GatewayまたはIngressで認証付きHTTPSの外部front doorを作る方式です。

```text
Agent Runtime
      ↓ HTTPS / Agent Gateway / egress authorization
GKE HTTPS front door (trusted TLS + IAP or equivalent authorization)
      ↓
ClusterIP Service
      ↓
MCP Server Pod
```

このfront doorには、承認済みDNS名、Agent Gatewayが信頼できるpublicly trusted TLS certificate、認証audience、caller identityの認可が必要です。Internal Load Balancerは構築済みで、GKE内のTLS検証付きMCP callは成功しましたが、Managed Agent RuntimeからはGateway `ALLOWED` 後にHTTP 503となっています。現在の`.internal`向けself-managed private CAはAgent Gatewayのorigin TLS要件を満たさないため、Runtime側のGateway Root CA追加では解決しません。今回追加したGateway APIのHTTP listenerはVPC内ルーティング診断専用であり、認証付きE2Eの代替ではありません。詳細は [`evidence/gke-gateway-origin-cert-blocker-20260829.md`](evidence/gke-gateway-origin-cert-blocker-20260829.md) と [`evidence/gke-gateway-api-http-diagnostic-20260829.md`](evidence/gke-gateway-api-http-diagnostic-20260829.md) を参照してください。

### 確認できたこと／未確認のこと

| 範囲 | 状態 | 内容 |
| --- | --- | --- |
| GKE上でのMCP Server起動 | 確認済み | Deployment、readiness probe、非root実行、immutable image |
| クラスタ内通信 | 確認済み | ClusterIPとKubernetes DNSを使ったPodからの接続 |
| MCP protocol | 確認済み | `initialize`、`tools/list`、正常／異常Tool call |
| Agent Registry手動登録 | 確認済み | `gcloud`によるcreate/update、Tool spec、interface登録 |
| Registry発見後の実行 | 確認済み | 検索結果のURLを使ったin-cluster実行 |
| Agent RuntimeからCloud Runへの通信 (`common-egress`) | PASS | Registry discovery、Gateway `ALLOWED`、Cloud Run HTTP 200、Claude Tool、server-side MCP executionを同一correlation IDで確認 |
| Agent RuntimeからGKEへの通信 (`common-egress`) | FAIL | Registry discoveryとGateway `ALLOWED`後、unsupported private origin CAのためILB origin deliveryがHTTP 503。GKE application executionなし |
| Claude Agent SDKとの連携 (`common-egress`, GKE) | FAIL | Runtime queryは `tool_execution` で停止し、remote Tool eventなし |
| ManifestベースのMCPメタデータ登録 | 未確認 | MCP固有annotation、CRD、controllerによる登録は使用していない |
| GKE endpointの外部公開 | 確認済み | `INTERNAL_MANAGED` HTTPS frontendとGateway API HTTP frontend、private DNS、HEALTHY NEG。public exposureなし |
| 本番可用性 | 未確認 | regional cluster、複数replica、PDB、autoscaling、障害試験は対象外 |
| 負荷・長時間接続 | 未確認 | 負荷試験、session互換性、timeout調整は対象外 |

## 実行方法

### ローカル

```sh
npm ci
npm test
npm run check:tool-spec
npm run smoke
```

Docker を使った確認は [`docs/runbook.md`](docs/runbook.md) の Local checks を参照してください。

### Google Cloud

Cloud Run と GKE の構築、immutable image digest の指定、Agent Registry 登録、検証コマンドは [`docs/runbook.md`](docs/runbook.md) にまとめています。

検証結果の詳細は [`docs/validation-report.md`](docs/validation-report.md)、個別の sanitized evidence は [`evidence/`](evidence/) を参照してください。

## 次の検証

Cloud Runではtokenなしとoperator credentialの拒否を確認済みです。wrong audience／別identity tokenはmint経路がないためSKIP、egress bindingを一時除去した診断はGateway denyにならず未解決として記録しています。GKEは承認済みhostname、DNS、trusted certificate、IAP audienceが揃うまでAgent Runtime E2Eを実施しません。Agent Runtime E2EはSDK Tool eventとserver-side execution evidenceを同じ correlation IDで揃えた場合だけPASSと判定します。

## 次回、同じ手動登録方式で構築するもの

### 共通

- `/mcp` と `/healthz` を提供するstateless MCP Server
- versionまたはdigestを固定したcontainer image
- runtimeの `tools/list` と一致するversion管理されたTool spec
- runtimeとTool specの名前、説明、input schemaを比較するチェック
- Agent RegistryのAPI、利用location、CLI command surfaceの事前確認
- Registry Serviceをcreate/update/search/describe/deleteできる運用スクリプト
- 検証結果を保存するevidenceと、tokenなどを除去するルール

### Cloud Run

- Artifact Registry repository
- 専用runtime Service Account
- IAM認証を有効にしたCloud Run Service
- 検証client用invoker Service Accountと最小限の `roles/run.invoker`
- Cloud Run URLをaudienceにしたID token取得方法
- `min=0`、上限instance数、timeout、concurrencyなどのscaling設定
- 未認証requestが拒否されることを確認するテスト

### GKE

- VPC-native GKEで使用するVPC、subnet、Pod/Service secondary range
- GKE cluster、node pool、node用Service Account
- Workload Identityとworkload用Google/Kubernetes Service Account
- immutable imageを指定したDeployment
- `/healthz` を使うreadiness probeとnon-root security context
- クラスタ内検証用の `ClusterIP` Service
- Agent Runtime用には、ClusterIPをbackendとする認証付きHTTPS Gateway／Ingress／Load Balancer。Gateway APIを採用する場合は `gke-l7-rilb`、IAP、trusted TLS、exact audienceを構成する
- 経路だけを切り分ける場合は、VPC内限定のGateway API HTTP listenerを診断専用として使えるが、Agent Runtime認証付きE2EのPASSにはしない
- Registry検索前にもruntime単体を確認できるvalidation Job
- Registryで発見したURLを使って再検証する一時PodまたはJob
- namespace、workload、Registry entry、Terraform resourceを安全に削除する手順

## 同じ方式で気にするべきこと

- Agent Registryへの登録成功は、endpointへの到達成功を意味しません。検索とMCP実行を別々に検証します。
- Registryに登録するURLは、実際のconsumerから到達できる必要があります。今回のGKE URLはcluster-localなので、クラスタ外のAgent Runtimeからは利用できません。
- 今回のGKE PASSは同一クラスタ内のNode.js clientからの結果です。Agent RuntimeやClaude Agent SDKから到達できることの証跡としては扱いません。
- Deployment、Service、Registryのinterface URL、Tool specは独立した設定です。Service名、namespace、port、`/mcp` pathのずれを検出する必要があります。
- Tool定義のsourceがruntimeとRegistryで分かれるとdriftします。`tools/list` と `toolspec.json` の自動比較を継続します。
- Registryへの反映には短いprojection delayがありました。登録直後の検索はretryを前提にします。
- Cloud RunはIAM認証を通過してからMCP protocolが処理されます。ID tokenのaudience、tokenを生成する主体、`roles/run.invoker` を切り分けます。
- GKEではnodeのArtifact Registry読取権限と、workloadがGoogle APIを使う場合のWorkload Identity権限を混同しないようにします。
- cluster-local endpointを外部consumerへ提供する場合は、ClusterIPをbackendとしてIngress／Gateway、TLS、認証、NetworkPolicy、DNSを別途設計・検証します。単なるService type変更だけでは、認証付きAgent Runtime経路の要件を満たしません。
- mutable tagではなく同一image digestをCloud Run、Deployment、validation Jobで共有し、比較対象の実装を固定します。
- Terraform planと削除planを確認し、検証用prefix／labelを持つ新規資源だけを対象にします。共有APIや既存クラスタを巻き込まないようにします。
- 証跡にはID token、credential、Service Account keyなどを保存しません。

## 現在の環境と削除方針

2026-08-24 時点で、検証資源は evidence review 前のため保持しています。今回、明示的に削除したのは重複していた次の Gateway 関連 resource です。

- `mcp-20260823-egress`
- `mcp-20260823-mcp-server-iap-policy`
- `mcp-20260823-mcp-server-iap-authz`

現在保持している主な experiment resource は Cloud Run、Artifact Registry repository、GKE Standard cluster/node pool、専用 VPC、Service Account/IAM、Agent Registry Service、Agent Runtime、Kubernetes namespace/workload です。`common-egress` はこの Terraform state の管理対象外であり、consumer cleanupから除外します。

既存の Autopilot クラスタ、default VPC、既存 Artifact Registry repository、他の Agent Registry Service、既存 Gateway は削除対象にしていません。安全な削除手順は [`docs/teardown.md`](docs/teardown.md) を参照してください。Google Cloud API の有効化状態は、意図的に維持しています。

## 制約と本番化前の確認事項

- GKE の比較は single-zone、`e2-small` 1ノードです。本番 HA や upgrade の検証ではありません。
- Kubernetes ManifestにMCPメタデータを記述する宣言的登録／自動検出方式は未検証です。
- `common-egress` 移行後のCloud RunはAgent Runtime、Gateway、Claude Tool、server-side executionを相関付きで確認済みです。GKEは同Gatewayのegress `ALLOWED` 後に旧ILBおよびGateway API HTTPSの`initialize`がHTTP 503、明示的なHTTP diagnosticがHTTP 400で停止し、endpoint authorizationとRuntime-to-Pod executionは未確認です。GKE Gateway APIではGKE PodからのHTTP/HTTPS routingのみ別途PASSになっています。詳細は [`evidence/gke-common-egress-validation-20260829.md`](evidence/gke-common-egress-validation-20260829.md)、[`evidence/gke-gateway-api-http-diagnostic-20260829.md`](evidence/gke-gateway-api-http-diagnostic-20260829.md)、[`evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md`](evidence/gke-gateway-api-http-runtime-diagnostic-20260829.md)、[`evidence/gke-gateway-api-common-egress-20260829.md`](evidence/gke-gateway-api-common-egress-20260829.md) を参照してください。
- Cloud Run の cold / warm latency は未測定です。安定した ID token mint 権限で再測定してください。
- 本番では regional GKE、SLO、rollout/rollback、容量、認証・ネットワーク設計を追加で決める必要があります。
- Agent Registry の接続元が必要とするネットワーク到達性と認証方式を、本番利用者に合わせて再確認してください。
