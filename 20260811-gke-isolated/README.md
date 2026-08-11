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

1. Terraform plan を生成して内容を確認します。この段階では apply は実行されません。スクリプトは state、project、location、repository ID を照合し、GCP 上に state 外の同名 repository があれば import・削除せず停止します。既存の別 repository は読み取り専用で一覧表示されます。

   ```bash
   PROJECT_ID="${PROJECT_ID}" ./scripts/setup-infrastructure.sh
   ```

   表示された plan で、作成対象が `test-isolated`、`us-central1-a`、`test-gke-isolated` であること、既存 repository に変更がないこと、Dataplane V2 と FQDN policy が有効であることを確認します。確認後、保存済み plan を apply します。

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
