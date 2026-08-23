# Agent Registry MCP Server 検証結果

Google Cloud Agent Registry から MCP Server を発見し、Cloud Run と GKE Standard の両方で実行できることを検証した記録です。

検証日: 2026-08-23  
プロジェクト: `nnyn-dev`  
リージョン: `us-central1`

## 結論

今回の stateless MCP Server には Cloud Run が適しています。IAM による認証、Agent Registry からの発見、MCP の実行を確認でき、最小インスタンス数を `0` に設定できます。

GKE Standard でも検証は成功しましたが、専用 VPC、サブネット、Pod/Service secondary range、クラスタ、ノードプール、Kubernetes workload が必要です。クラスタ内到達性や Kubernetes のネットワークポリシー、既存の共有サービスが必要な場合に選択するのが妥当です。

## 今回検証した連携方式

Agent Registry は MCP request を中継する proxy ではなく、MCP Server と Tool のメタデータを検索する discovery plane として使用しました。Registry で実行先 URL を発見した後、client がその URL に直接接続します。

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

Cloud Run と GKE のどちらも、Agent Registry への登録は [`scripts/registry.sh`](scripts/registry.sh) から `gcloud agent-registry services create/update` を実行しました。MCP Server の表示名、説明、interface URL、`JSONRPC` protocol binding、Tool spec はこの登録処理で渡しています。

Cloud Runの発見後実行はローカルoperatorが専用invoker identityのID tokenを取得して行い、GKEの発見後実行は同一クラスタ内のNode.js検証Podが行いました。どちらもAgent RuntimeまたはClaude Agent SDKからの実行ではありません。

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
| Terraform Cloud Run phase | PASS | `15 to add, 0 to change, 0 to destroy`。既存資源への変更なし |
| Cloud Run 認証済み実行 | PASS | `initialize`、`tools/list`、`validate_echo` が HTTP 200 |
| Cloud Run 未認証実行 | PASS | MCP 応答前に HTTP 403 で拒否 |
| Cloud Run scaling | PASS | `min=0`、`max=3`。idle 時の instance count `0` を観測 |
| Cloud Run Agent Registry | PASS | ローカルoperatorが登録・検索・発見URLへのIAM認証付き直接実行に成功 |
| GKE Standard 構築 | PASS | 専用 VPC、secondary range、`e2-small` 1ノードで Ready |
| GKE MCP 実行 | PASS | Deployment rollout、validation Job、Pod 内 smoke test に成功 |
| GKE Agent Registry | PASS | cluster-local URLを発見し、同一クラスタ内のNode.js検証Podから実行に成功 |
| Cloud Run cold / warm latency | SKIP | operator の ID token mint 権限が一時的に拒否され、測定を実施せず |

Cloud Run の IAM には専用 invoker Service Account のみを付与し、`allUsers` は付与していません。GKE 検証では既存の Autopilot クラスタを変更していません。

今後追加する検証も、対象、構成、実施手順、実測結果、証跡、未確認事項、cleanup状態をこのREADMEへ追記します。設定から推測した結果はPASSにせず、実行できなかった項目は理由を添えてSKIPまたは未確認として残します。

## Agent Registry 検証

Agent Registry の CLI で `JSONRPC` protocol binding を指定して、次の2つの Service を登録しました。

| 実行基盤 | Registry Service | Interface |
| --- | --- | --- |
| Cloud Run | `mcp-20260823-cloud-run` | Cloud Run の `/mcp` URL |
| GKE | `mcp-20260823-gke` | `http://mcp-20260823-mcp-server/mcp` |

`gcloud agent-registry mcp-servers search` で両方が検索でき、各結果に interface と `validate_echo` の metadata が含まれることを確認しました。

### GKEで実施した検証手順

1. Terraformで専用VPC、subnet、Pod/Service secondary range、GKE Standardクラスタ、node pool、Service Accountを作成しました。
2. Cloud Runと同じimmutable image digestを、Deploymentとvalidation Jobへ設定しました。
3. `ClusterIP` Serviceを作成し、MCP endpointをクラスタ内の `http://mcp-20260823-mcp-server/mcp` で公開しました。
4. `kubectl rollout status` でDeploymentがReadyになることを確認しました。
5. validation Jobで同じcontainer imageの `node scripts/local-smoke.mjs` を実行し、MCP Serverへ直接接続して `initialize`、`tools/list`、正常なTool call、不正入力を確認しました。
6. `scripts/registry.sh apply gke` でcluster-local URLと [`toolspec.json`](toolspec.json) をAgent Registryへ手動登録しました。
7. Agent Registry検索結果にGKE用Server、interface、`validate_echo` が含まれることを確認しました。
8. 検索結果のcluster-local URLを別の一時Podへ渡し、同じNode.js smoke clientからMCP flowが成功することを確認しました。

この検証により、Kubernetes上での起動確認とAgent Registryの検索確認を分離しつつ、「Registryに登録したURLが実際のMCP Serverへ到達すること」まで確認しています。

この一時Pod／JobはClaude Agent SDKではなく、MCP protocolだけを確認するリポジトリ内のNode.js smoke clientです。Agent Runtime上のClaude Agent SDKは使用しておらず、既存のAgent Runtime、Agent Gateway、Claude Agent SDK検証環境にも変更を加えていません。

また、GKE側にInternal Load Balancer、Ingress、Gatewayは構築していません。通信は同一namespace内の一時Pod／Jobから、Kubernetes DNSと `ClusterIP` Serviceを経由してMCP Server Podへ到達するクラスタ内通信だけです。

```text
同一GKEクラスタ／namespace

Node.js validation Pod / Job
        ↓ http://mcp-20260823-mcp-server/mcp
ClusterIP Service :80
        ↓
MCP Server Pod :8080
```

### 確認できたこと／未確認のこと

| 範囲 | 状態 | 内容 |
| --- | --- | --- |
| GKE上でのMCP Server起動 | 確認済み | Deployment、readiness probe、非root実行、immutable image |
| クラスタ内通信 | 確認済み | ClusterIPとKubernetes DNSを使ったPodからの接続 |
| MCP protocol | 確認済み | `initialize`、`tools/list`、正常／異常Tool call |
| Agent Registry手動登録 | 確認済み | `gcloud`によるcreate/update、Tool spec、interface登録 |
| Registry発見後の実行 | 確認済み | 検索結果のURLを使ったin-cluster実行 |
| Agent RuntimeからCloud Runへの通信 | 未確認 | Cloud Runはローカルoperatorから呼び出しておりAgent Runtimeは使用していない |
| Agent RuntimeからGKEへの通信 | 未確認 | GKE外のAgent Runtimeからcluster-local URLへ接続していない |
| Claude Agent SDKとの連携 | 未確認 | Claude Agent SDKは起動しておらず、検証PodはNode.js smoke client |
| ManifestベースのMCPメタデータ登録 | 未確認 | MCP固有annotation、CRD、controllerによる登録は使用していない |
| GKE endpointの外部公開 | 未確認 | Ingress、Gateway、Load Balancer、TLSは構築していない |
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

Agent Registryによる接続先管理、Agent Gatewayによるdefault-denyの外向き認可、Cloud Run／GKE endpoint側の認可、およびAgent Runtime上のClaude Agent SDKによるTool実行は、OpenSpec change [`validate-agent-runtime-mcp-access-control`](openspec/changes/validate-agent-runtime-mcp-access-control/proposal.md) で計画しています。この項目はProposal作成済み・実装前であり、現時点のPASSには含めません。

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
- 実行元から到達可能なService。今回と同じ方式なら `ClusterIP`
- Registry検索前にもruntime単体を確認できるvalidation Job
- Registryで発見したURLを使って再検証する一時PodまたはJob
- namespace、workload、Registry entry、Terraform resourceを安全に削除する手順

## 同じ方式で気にするべきこと

- Agent Registryへの登録成功は、endpointへの到達成功を意味しません。検索とMCP実行を別々に検証します。
- Registryに登録するURLは、実際のconsumerから到達できる必要があります。今回のGKE URLはcluster-localなので、クラスタ外のclientからは利用できません。
- 今回のGKE PASSは同一クラスタ内のNode.js clientからの結果です。Agent RuntimeやClaude Agent SDKから到達できることの証跡としては扱いません。
- Deployment、Service、Registryのinterface URL、Tool specは独立した設定です。Service名、namespace、port、`/mcp` pathのずれを検出する必要があります。
- Tool定義のsourceがruntimeとRegistryで分かれるとdriftします。`tools/list` と `toolspec.json` の自動比較を継続します。
- Registryへの反映には短いprojection delayがありました。登録直後の検索はretryを前提にします。
- Cloud RunはIAM認証を通過してからMCP protocolが処理されます。ID tokenのaudience、tokenを生成する主体、`roles/run.invoker` を切り分けます。
- GKEではnodeのArtifact Registry読取権限と、workloadがGoogle APIを使う場合のWorkload Identity権限を混同しないようにします。
- cluster-local endpointを外部consumerへ提供する場合は、Ingress／Gateway、TLS、認証、NetworkPolicy、DNSを別途設計・検証します。
- mutable tagではなく同一image digestをCloud Run、Deployment、validation Jobで共有し、比較対象の実装を固定します。
- Terraform planと削除planを確認し、検証用prefix／labelを持つ新規資源だけを対象にします。共有APIや既存クラスタを巻き込まないようにします。
- 証跡にはID token、credential、Service Account keyなどを保存しません。

## 環境の削除

検証後、次の検証用資源は削除済みです。

- Cloud Run Service
- Artifact Registry repository
- GKE Standard cluster / node pool
- 専用 VPC / subnet / secondary ranges
- 検証用 Service Account と IAM binding
- Agent Registry の検証用 Service
- Kubernetes namespace と workload

既存の Autopilot クラスタ、default VPC、既存 Artifact Registry repository、他の Agent Registry Service は削除対象にしていません。安全な削除手順は [`docs/teardown.md`](docs/teardown.md) を参照してください。Google Cloud API の有効化状態は、意図的に維持しています。

## 制約と本番化前の確認事項

- GKE の比較は single-zone、`e2-small` 1ノードです。本番 HA や upgrade の検証ではありません。
- Kubernetes ManifestにMCPメタデータを記述する宣言的登録／自動検出方式は未検証です。
- Agent Runtime上のClaude Agent SDKからGKE MCP Serverへ接続する経路は未検証です。
- Cloud Run の cold / warm latency は未測定です。安定した ID token mint 権限で再測定してください。
- 本番では regional GKE、SLO、rollout/rollback、容量、認証・ネットワーク設計を追加で決める必要があります。
- Agent Registry の接続元が必要とするネットワーク到達性と認証方式を、本番利用者に合わせて再確認してください。
