# GKE 隔離環境での Claude Agent SDK 検証

このディレクトリでは、単一ゾーンの GKE Dataplane V2 クラスタと、Workload Identity Federation for GKE を使用する `test` Deployment を構築します。IAM role は KSA principal に直接付与し、ワークロード専用の Google サービスアカウントや長期サービスアカウント鍵は作成しません。通常リソース、通信制御、deny logging は別のフェーズで適用します。

## 前提条件

実行者の環境には `gcloud`、`terraform`、`kubectl`、`docker` と、有効な Google Cloud ログインが必要です。対象プロジェクトには既存の `default` VPC と、`us-central1` の `default` subnet が必要です。また、プロジェクトで `claude-haiku-4-5@20251001` の Vertex AI 利用権限が必要です。

ログ検証を実行するオペレータには、対象プロジェクトの `roles/logging.viewer`（または `logging.logEntries.list` を含む同等の権限）が必要です。この権限は Pod の KSA principal には付与しません。

```bash
export PROJECT_ID="$(gcloud config get-value project)"
```

Terraform の既定 Artifact Registry ID は検証環境固有の `test-gke-isolated` です。`image_repository` と `image_uri` の output を build、push、deploy で使用し、repository URL をスクリプトやマニフェストへハードコードしません。

## 再現手順

1. Terraform plan を生成して内容を確認します。この段階では apply は実行されません。スクリプトは state、project、location、repository ID を照合し、対象 VPC に関連付く Cloud DNS Policy と Terraform state の所有関係も preflight します。state 外の DNS Policy がある場合は重複作成・自動 import をせず停止します。GCP 上に state 外の同名 repository がある場合も import・削除せず停止します。既存の別 repository は読み取り専用で一覧表示されます。

   ```bash
   PROJECT_ID="${PROJECT_ID}" ./scripts/setup-infrastructure.sh
   ```

   表示された plan で、`dns.googleapis.com` と `google_dns_policy.gke_dns_logging`（`gke-dns-logging`、対象 VPC、`enable_logging=true`）が追加されること、既存 VPC、IAM、NetworkPolicy logging、Log Router sink / exclusion に変更がないことを確認します。併せて作成対象が `test-isolated`、`us-central1-a`、`test-gke-isolated` であること、既存 repository に変更がないこと、Dataplane V2 と FQDN policy が有効であることを確認します。確認後、保存済み plan を apply します。

   ```bash
   APPLY=1 PROJECT_ID="${PROJECT_ID}" ./scripts/setup-infrastructure.sh
   ```

2. イメージを build・push し、KSA と Deployment だけを適用します。イメージ URI は Terraform output から組み立てます。

   ```bash
   ./scripts/deploy-workload.sh
   ```

3. 通信制御を適用していない状態で基準動作を確認します。

   ```bash
   ./scripts/test-before-network-policy.sh
   ```

4. `NetworkLogging/default` を先に適用し、deny のみをログ出力する設定を確認してから、標準 NetworkPolicy と FQDNNetworkPolicy を適用します。client-side/server-side dry-run、取得、describe の設定エラー検査も行います。

   ```bash
   ./scripts/apply-network-policy.sh
   ```

   設定値は `cluster.deny.log=true`、`cluster.deny.delegate=false`、`cluster.allow.log=false`、`cluster.allow.delegate=false` です。

5. 許可通信と未許可通信を再確認します。GitHub、Vertex AI、BigQuery は成功し、`checkip.amazonaws.com:80` は有限時間内に失敗することが期待されます。

   ```bash
   ./scripts/test-after-network-policy.sh
   ```

6. 同じ Pod から拒否通信を発生させ、Cloud Logging の `policy-action` ログを有限時間 polling して接続試行と照合します。開始時刻、Pod 名、Pod 内 DNS の IPv4、egress、deny、TCP、port 80 を query に使用します。既定の待機時間は300秒で、`LOG_TIMEOUT_SECONDS` と `POLL_INTERVAL_SECONDS` で調整できます。

   ```bash
   ./scripts/test-network-policy-logging.sh
   ```

   成功時は次の field を表示・検証します。

   `src.pod_name`、`dest_ip`、`dest_port`、`protocol`、`direction`、`disposition`、`count`

7. DNS Query Logging の実ログと deny log を同じ Pod・問い合わせ名・時刻窓で検証します。既定の `checkip.amazonaws.com` は DNS 解決後の TCP/80 が未許可となるため、DNS の `rdata` に含まれる応答 IP と `policy-action` の destination IP を自動で比較します。FQDN、timeout、polling 間隔は環境変数で変更できます。

   ```bash
   TEST_FQDN=checkip.amazonaws.com \
   LOG_TIMEOUT_SECONDS=300 POLL_INTERVAL_SECONDS=10 \
   ./scripts/test-dns-query-logging.sh
   ```

   成功時は対象 Pod、DNS の timestamp / `queryName` / `sourceIP` / `responseCode` / `rdata`、deny の timestamp / destination IP / port と、両者の IP が一致したことを表示します。DNS cache で新しい entry が作られない場合は、別の解決可能な FQDN または TTL 経過後に再試行します。

## Cloud Logging の検索

Logs Explorer では、対象 project、cluster、Pod、開始時刻を適宜置き換えて次を検索できます。

```text
resource.type="k8s_node"
resource.labels.cluster_name="test-isolated"
logName="projects/PROJECT_ID/logs/policy-action"
jsonPayload.direction="egress"
jsonPayload.disposition="deny"
jsonPayload.src_pod_name="POD_NAME"
jsonPayload.dest_port=80
```

CLI では専用スクリプトが使用する query を確認するか、次のように検索します。

```bash
gcloud logging read \
  'resource.type="k8s_node" AND resource.labels.cluster_name="test-isolated" AND logName="projects/PROJECT_ID/logs/policy-action" AND jsonPayload.direction="egress" AND jsonPayload.disposition="deny" AND jsonPayload.dest_port=80' \
  --project="${PROJECT_ID}" --limit=20 --format=json
```

Cloud Logging の反映には遅延があり、deny log は複数の試行を `count` に集約することがあります。そのため専用スクリプトは一試行一レコードや件数を要求せず、開始時刻以降の一致レコード、必須 field、名前解決済み宛先 IP の一致を確認します。暗黙 deny には単独の拒否 NetworkPolicy 名が存在しないため、Pod、時刻、宛先、方向、disposition で対応付けます。

DNS Query Logging は次のように `resource.type="dns_query"` と `queryName` で検索できます。Logs Explorer では project と開始時刻を対象環境に置き換えてください。

```text
resource.type="dns_query"
timestamp>="2026-08-11T00:00:00Z"
jsonPayload.queryName:"checkip.amazonaws.com"
```

CLI では次の検索例を使用します。

```bash
gcloud logging read \
  'resource.type="dns_query" AND timestamp>="START_TIME" AND jsonPayload.queryName:"checkip.amazonaws.com"' \
  --project="${PROJECT_ID}" --limit=20 --format=json
```

`dns_query` entry には Kubernetes の namespace、Pod 名、container 名が直接付与されないため、resource label でそれらを絞り込むことはできません。Pod から問い合わせを発生させた UTC 時刻、`queryName`、`sourceIP`、`rdata` の応答 IP、`policy-action` の deny timestamp / destination IP / port を同じ時間窓で比較します。`sourceIP` は常に Pod IP とは限らず、NodeLocal DNSCache など DNS 転送経路の node / component を示す場合があります。

DNS cache や Cloud Logging の取り込み遅延により、アプリケーション接続と `dns_query` entry は一対一にならないことがあります。Policy は VPC 全体に適用されるため、query log の保存量と Cloud Logging の課金が増える可能性があります。Shared VPC では DNS Policy と `dns_query` log が host project 側に記録され得るため、service project だけでなく host project も確認します。今回の構成では外部 sink、独自 logging bucket、広範な Log Router exclusion は追加しません。

Deny logging は Cloud Logging の保存量と課金を増やします。allow logging は無効にして不要なログを抑えています。検証後に logging を無効化する場合は次を実行します。

```bash
kubectl patch networklogging/default --type=merge \
  -p '{"spec":{"cluster":{"deny":{"log":false}}}}'
kubectl get networklogging/default -o yaml
```

## 検証結果の記録欄

実行時には、実際の UTC 時刻、Pod 名、名前解決結果、許可通信の結果、拒否ログの必須 field をこの節へ追記します。成功したログの `count` は集約により1以上です。

2026-08-11 に `nnyn-dev` で実行した結果：

- Terraform apply：15リソースを追加。`test-gke-isolated` と `test-isolated` を作成し、既存の `claude-agent` repository は変更しなかった。
- 制限前：GitHub keys、Vertex AI 経由の Claude Agent SDK、BigQuery（`ROWS: 25`）が成功した。
- NetworkLogging：client/server dry-run、取得、describe が成功し、deny logging 有効・allow logging 無効・delegate 無効を確認した。
- 制限後：GitHub、Vertex AI、BigQuery が成功し、`checkip.amazonaws.com:80` は timeout して拒否された。
- deny log：`test-778b4d8589-nnk2f`、`dest_ip=98.90.98.64`、`dest_port=80`、`protocol=tcp`、`direction=egress`、`disposition=deny`、`count=1` を確認した。宛先IPは接続直前の Pod 内 DNS 解決結果に含まれていた。
- 環境は依頼により保持した。destroy plan は `test-gke-isolated` と Terraform 管理の15リソースだけを対象とし、既存の別 repository は対象外であることを確認したが、destroy apply は実行していない。

この変更の Cloud DNS Query Logging 検証結果（2026-08-11 UTC）：

- Terraform apply：`dns.googleapis.com` と `gke-dns-logging` の2リソースだけを追加し、`default` VPC に対して `enable_logging=true`、Terraform state 所有、重複 policy なしを確認した。再度の preflight と plan は `No changes` になった。
- DNS query log：開始時刻 `2026-08-11T04:20:18Z`、対象 Pod `default/test-778b4d8589-nnk2f`、`queryName=checkip.amazonaws.com.`、`sourceIP=10.128.0.38`、`responseCode=NOERROR`、`rdata` に `18.213.84.152`、`54.80.128.83`、`98.84.197.236` などを確認した。Pod IP は `10.72.0.15` であり、`sourceIP` が Pod IP とは限らないことも確認した。
- DNS / deny 相関：`policy-action` の `2026-08-11T04:20:24.676485476Z`、`destinationIP=98.84.197.236`、port `80`、TCP、deny、`count=1` と DNS `rdata` の IP が一致し、`scripts/test-dns-query-logging.sh` が成功した。
- 既存境界：GitHub、Vertex AI、BigQuery（`ROWS: 25`）は成功し、未許可 `checkip.amazonaws.com:80` は拒否された。Terraform state に追加 IAM role / sink はなく、Cloud Logging sink は既定の `_Required` / `_Default` のみで、既存 FQDN allowlist と NetworkPolicy logging は変更していない。

## 手動確認

```bash
kubectl exec deploy/test -- curl --fail --location https://github.com/74th.keys
kubectl exec deploy/test -- python claude_agent_sdk.py "https://github.com/74th の要約して"
kubectl exec deploy/test -- python test_bq.py
kubectl exec deploy/test -- curl --connect-timeout 3 --max-time 10 http://checkip.amazonaws.com
```

最後のコマンドは FQDN policy 適用後に失敗することが期待されます。policy の動作を確認するときは、`kubectl get pods -l app=test,component=isolated-claude-agent` で新しい Pod 名を取得してください。

## ロールバックと削除

ワークロードを残したまま通信制御を解除するには次を実行します。

```bash
kubectl delete -f k8s/fqdn-network-policy.yaml
kubectl delete -f k8s/network-policy.yaml
```

Terraform 管理リソースを削除する場合は、cleanup スクリプトが state の `google_artifact_registry_repository.agent`、project、location、repository ID を照合し、destroy plan に他の Artifact Registry repository がないことを確認します。state 外の repository は import・削除しません。

```bash
PROJECT_ID="${PROJECT_ID}" ./scripts/cleanup-infrastructure.sh
APPLY=1 PROJECT_ID="${PROJECT_ID}" ./scripts/cleanup-infrastructure.sh
```

apply 後に Terraform state が空であり、既存の別 repository が保持されることを確認します。この環境は課金対象リソースを作成するため、検証終了後は確認済み destroy plan を適用してください。

DNS Query Logging だけを戻す場合は、まず対象 VPC の DNS Policy が `google_dns_policy.gke_dns_logging` として Terraform state に所有されていることを確認し、保存 plan の差分が `gke-dns-logging` の `enable_logging=false` または同 resource の削除だけであることをレビューしてから apply します。既存の GKE、VPC、NetworkPolicy logging、Log Router sink / exclusion、IAM は変更しません。state 外の DNS Policy が見つかった場合は自動 import・削除せず停止します。

```bash
terraform -chdir=terraform plan -var="project_id=${PROJECT_ID}" 
# 上の plan をレビュー後、DNS Policy の変更だけを含む保存 plan を apply する
terraform -chdir=terraform apply ../.work/gke-isolated.tfplan
```
