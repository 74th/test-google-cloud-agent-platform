# common側Agent Gateway対応依頼

## 目的

consumer側で構築したGKE MCP Serverを、common所有の
`common-egress` Agent Gateway経由でAgent Runtimeから利用できる状態にする。

consumer側では、GKEをcommon GatewayのVPCと同じVPC上に再構築し、次の2段階を確認済みです。

1. GKE内の `ClusterIP` Service
2. ClusterIPをbackendにした `INTERNAL_MANAGED` Internal HTTPS Load Balancer

現在の未解決点は、Agent RuntimeのRegistry discoveryがGatewayの
`default_denied` で拒否されることです。

## 現在の構成

| 項目 | 値 |
| --- | --- |
| Project | `nnyn-dev` |
| Agent Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528` |
| Runtime identity | `AGENT_IDENTITY` / effective identityは上記Runtime principal |
| Agent Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Gateway direction/protocol | `AGENT_TO_ANYWHERE` / `MCP` |
| Registry location | `us-central1` |
| GKE cluster | `mcp-20260823-mcp-server-gke` / `us-central1-a` |
| GKE VPC/subnet | `common-agent-gateway-vpc` / `mcp-20260823-mcp-server-subnet` |
| GKE ClusterIP | `10.242.0.20:80` |
| Internal HTTPS frontend | `gke.mcp-20260823.internal` / `10.240.0.5` |
| GKE proxy-only subnet | `mcp-20260823-mcp-server-proxy-only` / `10.244.0.0/23` |
| GKE Registry Service | `mcp-20260823-gke` |
| GKE Registry interface | `https://gke.mcp-20260823.internal/mcp` |

詳細なconsumer側証跡は
[`gke-common-egress-ilb-20260828.md`](../evidence/gke-common-egress-ilb-20260828.md) を参照してください。

## 観測済み事象

### Runtime query

Agent Runtimeへ、GKE targetのqueryを送信すると次の結果になります。

```text
HTTP 400 / FAILED_PRECONDITION
stage=registry_discovery
Registry service lookup failed (SSLError)
```

### Gateway log

同時刻の `common-egress` Gateway request logは次の内容です。

```text
timestamp=2026-08-28T06:21:16.892925Z
requestMethod=CONNECT
status=403
enforcedGatewaySecurityPolicy.hostname=240.0.0.2:443
matchedRules[0].action=DENIED
matchedRules[0].name=default_denied
```

このため、consumer側では今回の失敗を「GKEのClusterIPまたはInternal LBが到達不能」とは断定していません。RuntimeからGatewayへTLS接続し、Gatewayの拒否を受けた後にRuntime側で `SSLError` として返された可能性を含め、common側で判定してください。

## CAについての確認

consumer Runtime imageにはGateway Root CAをBuildKit secret経由で導入済みです。

- image: `us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server-agent/agent-runtime@sha256:48c06e1bd9b248d702d6491b21dbe52a01adfdada0400725341042a9617feb23`
- image内 `/usr/local/share/ca-certificates/agent-gateway.crt`：存在
- image内CAの `openssl verify`：`OK`
- live `common-egress` Root CA fingerprintとimage内CA fingerprint：一致

したがって、まずCA不足ではなく、GatewayのCONNECT先判定とegress policyを確認してください。CAを再配布する場合も、証明書本文や秘密情報をログ/evidenceへ出力しないでください。

## common側に依頼したいこと

### 1. Gatewayが実際に判定している宛先の確認

次の点をlive API/logで確認してください。

- `240.0.0.2:443` が何を表す宛先か
- Agent Registry discoveryのCONNECTが、想定したRegistry endpointに対応しているか
- `default_denied` が、Registry endpoint未登録・host未許可・identity未許可・protocol不一致のどれで発生しているか
- `common-egress` に別のallow rule/authz policy/extensionが必要か
- GatewayのNetwork Attachmentが、consumer GKE subnetおよびInternal LBのVPC pathを利用できる状態か

### 2. Registry discoveryに必要なcommon側許可の確認

consumer側のRuntime effective identityと、次のconsumer-owned Registry resourceを対象に、必要な許可が満たされているか確認してください。

- Agent Registry control-plane endpoint
- GKE MCP Server `mcp-20260823-gke`
- 必要な場合のVertex AI regional/global endpoint
- 必要な場合のIAM Credentials endpoint

consumer側ではRuntime principalにresource-scoped `roles/iap.egressor`を付与しています。common側では、このbindingだけでは不十分なのか、Gateway側に別の認可条件があるのかを切り分けてください。

### 3. 最小変更でのallow設計

追加変更が必要な場合は、次を満たす最小の変更案を提示してください。

- `common-egress` のdefault-denyを維持する
- 許可対象を必要なRegistry/control-plane endpointと、必要なGKE MCP endpointに限定する
- `allUsers`、project-wide owner/editor、広範囲のpublic allowを追加しない
- consumer Terraform stateへcommon resourceをimportさせない
- common VPC、common subnet、Network Attachmentをconsumer側で管理させない
- 変更前後のGateway ID、etag、direction、protocol、Registry、Network Attachmentをread-backできる
- allow/denyがGateway logで判定できる

変更する場合は、対象resource、IAM principal、host、port、protocol、適用範囲、rollback方法を先に示してください。

### 4. private GKE routeの確認

Gateway側の許可後、次のprivate pathが利用可能か確認してください。

```text
Agent Runtime
  -> common-egress
  -> Network Attachment
  -> common-agent-gateway-vpc
  -> gke.mcp-20260823.internal (10.240.0.5)
  -> Internal HTTPS Load Balancer
  -> ClusterIP 10.242.0.20:80
  -> GKE MCP Pod
```

必要な確認項目は次のとおりです。

- private DNS `gke.mcp-20260823.internal` の解決
- internal frontend `10.240.0.5` への到達
- TLS hostname/certificate検証
- Internal HTTPS LBのNEG/backend health
- ClusterIP `10.242.0.20` とPodへのbackend delivery
- Internet-facing frontendが存在しないこと

## common側の完了条件

次のいずれかを、非機密の証跡付きで返してください。

### 成功の場合

- RuntimeのRegistry discoveryが成功
- Gateway logにallow判定がある
- GKE Registry Serviceの解決hostが正しい
- Internal HTTPS LBへの接続が成功
- endpoint authorizationが成功
- GKE MCP Podのserver-side execution logがある
- Runtime invocation、Gateway、Registry Service、frontend、Pod executionが同じcorrelation IDで追跡できる

### blockerの場合

- `default_denied` の正確なenforcement layer
- 必要なcommon-owned resourceまたはpolicy
- 変更が必要なownerと承認境界
- consumer側で変更してはいけない理由
- 再試行に必要な最小変更案
- 変更しない場合の明確なFAIL/SKIP判定

## 禁止事項

- consumer側で`common-egress`、common VPC、common subnet、Network AttachmentをTerraform管理しない
- 既存Autopilot GKEを変更しない
- public Load Balancer、匿名HTTP、認証なしの外部fallbackを追加しない
- Gateway CA、token、private key、credentialをログやMarkdownへ貼り付けない
- Registry discovery成功だけで接続認可やMCP実行成功と判定しない
- Operator-sideまたはin-cluster smokeをAgent Runtime E2Eと呼ばない
- `terraform destroy`を実行しない

## 参照

- [GKE private route証跡](../evidence/gke-common-egress-ilb-20260828.md)
- [common-egress Runtime blocker](../evidence/common-egress-runtime-blocker-20260828.md)
- [Runtime image read-back](../evidence/migration-apply-readback-20260828.md)
- [consumer runbook](runbook.md)
