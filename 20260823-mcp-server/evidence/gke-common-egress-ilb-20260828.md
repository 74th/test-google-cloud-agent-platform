# GKE common-egress private route validation（2026-08-28）

## 構築結果

| 層 | 実測値 | 判定 |
| --- | --- | --- |
| GKE cluster | `mcp-20260823-mcp-server-gke` / `RUNNING` / `us-central1-a` | PASS |
| VPC / GKE subnet | `common-agent-gateway-vpc` / `mcp-20260823-mcp-server-subnet` / `10.240.0.0/20` | PASS |
| ClusterIP Service | `mcp-20260823-mcp-server` / `10.242.0.20:80` / `type=ClusterIP` / external IPなし | PASS |
| Pod execution | immutable MCP image / Pod `10.241.0.13` | PASS |
| private DNS | private zone `mcp-20260823-mcp-server-private` attached to `common-agent-gateway-vpc`; `gke.mcp-20260823.internal -> 10.240.0.5` | PASS |
| proxy-only subnet | consumer-owned `mcp-20260823-mcp-server-proxy-only` / `10.244.0.0/23` / `REGIONAL_MANAGED_PROXY` / `ACTIVE` | PASS |
| Internal HTTPS frontend | `INTERNAL_MANAGED` / `10.240.0.5` / `gce-internal` / HTTP disabled | PASS |
| backend NEG health | GKE Ingress annotation reports the MCP NEG `HEALTHY` | PASS |
| TLS | self-managed test certificate for `gke.mcp-20260823.internal`; fingerprint `46:19:0A:86:2A:11:20:3C:AB:DA:19:52:BE:10:AA:23:0B:1C:1B:14:69:F2:5D:D6:51:06:AA:CB:37:71:BB:FC`; certificate body/key not recorded | PASS |

## 到達性試験

in-cluster `trusted-ilb-probe`（Pod、専用TLS Secretの証明書をCAとして使用、`-k`なし）から internal frontendへ MCP `initialize` を送信し、HTTP 200 と MCP server infoを取得した。`mcp-ilb-mcp-smoke` でも同一frontendに対して initialize、tools/list、valid/invalid tools/call が成功した。Correlation ID `mcp-ilb-corr-20260828` を付けた `tools/call` は `hostingTarget=gke` のTool結果と、Podの `mcp_tool_execution` logの両方で確認できた。

この試験は `caller=GKE validation Pod`、`source=GKE Pod network`、`destination=gke.mcp-20260823.internal/10.240.0.5`、`backend=mcp-20260823-mcp-server ClusterIP 10.242.0.20` であり、Agent Runtime E2Eではない。TLS Secretは一時生成し、repository/evidenceへ秘密鍵または証明書本文を保存していない。

## ClusterIP-first の結果

最初に予約した `10.242.0.10` はGKE system Service `kube-dns` が使用していたため、MCP Service作成時に `provided IP is already allocated` となった。予約値を未使用の `10.242.0.20` に変更後、ClusterIP、Service DNS、Pod内MCP smokeは成功した。

ClusterIPそのものはGKE内では動作したが、VPC外のmanaged Agent RuntimeがKubernetes Service CIDRへ到達できることは証明しない。RuntimeのGKE queryは次の結果だった。

```text
HTTP 400 / FAILED_PRECONDITION
stage=registry_discovery
Registry service lookup failed (SSLError)
```

同時刻の `common-egress` Gateway log（`2026-08-28T06:21:16.892925Z`）は、`CONNECT` / `403`、`hostname=240.0.0.2:443`、`matchedRules=default_denied` だった。したがって、ClusterIPがGateway VPC経由で不通だとは断定せず、Gateway egress前段blockerとして扱う。

## Internal HTTPS Load Balancerの結果

GKE Ingressは最初、proxy-only subnet不足で次のエラーになった。

```text
An active proxy-only subnetwork is required in the same region and VPC as the forwarding rule.
```

consumer-owned proxy-only subnet追加後、forwarding rule、regional target HTTPS proxy、private DNS recordが作成され、MCP NEGはHEALTHYになった。TLS検証付きPodからのinitializeもHTTP 200で成功した。

ただし、現在のfrontendにはIAP等のendpoint authorizationを構成していないため、認証なしPodのinitializeも成功する。この結果は「internal network/TLS/backend delivery PASS」であり、「endpoint authorization PASS」または「Agent Runtime E2E PASS」ではない。匿名公開やpublic Load Balancerへのfallbackは行っていない。

## 残課題

- `common-egress` のRegistry discovery `default_denied` を解消するshared-owner側の変更は、このconsumer stateでは実施しない。
- endpoint authorization（IAP等）を追加するまで、GKE governed E2E、Claude Tool selection、negative authorization testはPASSにしない。
- common Gateway/VPC/subnet/Network Attachment、既存Autopilot GKEは変更していない。`terraform destroy`も実行していない。
