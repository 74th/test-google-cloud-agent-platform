# common-egress 移行前インベントリ（2026-08-28）

この記録は consumer (`20260823-mcp-server`) の変更前に取得した sanitized
inventory です。証明書本文、token、credential、private key は保存していません。

## Owner output と live API

`terraform -chdir=../common/terraform output -json` と
`gcloud beta network-services agent-gateways describe ... --format=json`
（`agentGatewayCard.rootCertificates` は出力前に除外）の比較結果です。

| 項目 | common owner output | live 値 | 判定 |
| --- | --- | --- | --- |
| project/location/name | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` | 同一 | 一致 |
| governed access path | — | `AGENT_TO_ANYWHERE` | 要求値 |
| protocol | — | `MCP` | 要求値 |
| Registry | — | `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1` | 一致 |
| Network Attachment | `https://www.googleapis.com/compute/v1/projects/nnyn-dev/regions/us-central1/networkAttachments/common-agent-gateway-attachment` | 同一 | 一致 |
| Gateway etag | — | `dJ8MLgd6POm1aIr09nFj08MG6sYT3_r_kQdbTE7p57E` | 記録済み |
| live 時刻 | — | `2026-08-28T03:03:13.066014701Z` | GET/list 成功 |
| TLS inspection root CA | — | count `1`; SHA-256 fingerprint `47:E4:1A:28:F6:64:11:85:A3:5F:B5:D4:EC:2C:CD:3B:32:00:2D:BA:81:C3:74:67:D4:73:81:58:7E:2C:82:9A` | 本文非保存 |

Agent Gateway の list/describe が対象 resource を返し、削除中の operation は観測されなかったため、移行 preflight 上は active と扱う。API の sanitized response に独立した `state` フィールドは返らないため、egress の実効許可は Runtime probe で別途確認する。

## VPC attachment

`gcloud compute network-attachments describe common-agent-gateway-attachment
--region=us-central1 --project=nnyn-dev --format=json` の sanitized 結果:

- network: `projects/nnyn-dev/global/networks/common-agent-gateway-vpc`
- subnet: `projects/nnyn-dev/regions/us-central1/subnetworks/common-agent-gateway-subnet`
- subnet CIDR: `10.243.0.0/28`
- connection preference: `ACCEPT_AUTOMATIC`
- accepted connection: producer project/number `778161432651`, status `ACCEPTED`, same subnet

## 所有境界

common state の resource list は `google_network_services_agent_gateway.shared`、
common VPC、subnet、Network Attachment、および API enablement のみを含む。
consumer はこれらを宣言・import・変更・削除しない。
