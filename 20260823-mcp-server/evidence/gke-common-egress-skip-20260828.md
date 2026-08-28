# common-egress GKE phase initial SKIP（2026-08-28）

これはprivate-front-door構築前の初期判定であり、最新結果は
[`gke-common-egress-ilb-20260828.md`](gke-common-egress-ilb-20260828.md) に記録する。
GKEのAgent Runtime E2E自体は現在も未完了だが、private route prerequisitesの一部は
その後consumer stateに構築された。

| prerequisite | 実測・状態 | 判定 |
| --- | --- | --- |
| consumer GKE phase | `enable_gke=false`。既存 `asia-northeast1` Autopilot は unrelated | 初期SKIP（後に構築） |
| private DNS | 承認済み consumer zone/record なし | 初期時点で未構築（後にPASS） |
| trusted internal HTTPS Load Balancer | internal frontend/backend/certificate なし | 初期時点で未構築（後にPASS） |
| endpoint authorization | GKE front door の audience/identity binding なし | 未構築 |
| backend exposure | 既存の検証 backend は Kubernetes `ClusterIP`。Internetへ公開していない | 安全側で保持 |
| Runtime route | `common-egress` から internal frontend への到達を Agent Runtime で実証していない | SKIP（継続） |

GKEのClusterIP/in-cluster Node.js smokeとRegistry metadataは、Agent Runtime、Gateway VPC routing、front-door authorization、Pod executionを同じ correlation IDで証明するものではありません。private routeを追加する場合は、common resourcesを変更しない consumer-only plan、DNS/TLS/audienceの承認、scope guard、個別のread-backが先に必要です。匿名LoadBalancer、public HTTP、既存Autopilot変更へのfallbackは採用しません。
