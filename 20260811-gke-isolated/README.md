# GKE 隔離環境での Claude Agent SDK 検証

このディレクトリでは、単一ゾーンの GKE Dataplane V2 クラスタと、Workload Identity Federation for GKE を使用する `test` Deployment を構築します。IAM role は KSA principal に直接付与し、ワークロード専用の Google サービスアカウントや長期サービスアカウント鍵は作成しません。通常リソースと外向き通信制御は、意図的に別のフェーズで適用します。

## 前提条件

実行者の環境には `gcloud`、`terraform`、`kubectl`、`docker` と、有効な Google Cloud ログインが必要です。対象プロジェクトには既存の `default` VPC と、`us-central1` の `default` subnet が必要です。また、プロジェクトで `claude-haiku-4-5@20251001` の Vertex AI 利用権限が必要です。

以下のコマンドで対象プロジェクトを設定します。

```bash
export PROJECT_ID="$(gcloud config get-value project)"
```

Terraform だけを実行する場合に利用できる `terraform/terraform.tfvars.example` も用意しています。内容は `project_id = "nnyn-dev"` です。

## 再現手順

1. Terraform plan を生成して内容を確認します。このコマンドでは apply は実行されません。

   ```bash
   PROJECT_ID="${PROJECT_ID}" ./scripts/setup-infrastructure.sh
   ```

   表示されたリソースと保存された `.work/gke-isolated.tfplan` を確認します。クラスタ名が `test-isolated`、場所が `us-central1-a`、subnet が `default`、Dataplane V2 と FQDN policy が有効、`e2-standard-2` のノードが1台であることを確認してください。確認後、保存済みの plan を apply します。

   ```bash
   APPLY=1 PROJECT_ID="${PROJECT_ID}" ./scripts/setup-infrastructure.sh
   ```

2. イメージを build・push し、annotation のない KSA と Deployment だけを適用します。スクリプトは通常リソースに対して client/server dry-run を実行し、rollout 完了まで待機します。

   ```bash
   ./scripts/deploy-workload.sh
   ```

3. 通信制御を適用していない状態で基準動作を確認します。次の3つの確認がすべて成功してから policy を追加します。

   ```bash
   ./scripts/test-before-network-policy.sh
   ```

4. 標準の default-deny・DNS・metadata policy と GKE FQDN policy を適用します。スクリプトは両方の dry-run を実行し、適用された selector とルールを表示します。

   ```bash
   ./scripts/apply-network-policy.sh
   ```

5. 新しい `kubectl exec` 接続を使い、許可された3つの操作と、遮断されるべき接続を確認します。

   ```bash
   ./scripts/test-after-network-policy.sh
   ```

期待する結果は、GitHub keys の取得成功、Claude Agent SDK の応答、BigQuery の出力（`ROWS: ...` または明示的な `NO_ROWS: ...`）です。policy 適用後は `checkip.amazonaws.com` への接続が有限時間内に失敗し、応答本文を取得できないことが必要です。Workload Identity 用には GKE Dataplane V2 の metadata endpoint（`169.254.169.252:987/988` と `169.254.169.254:80/8080`）だけを許可します。

## 手動確認

```bash
kubectl exec deploy/test -- curl --fail --location https://github.com/74th.keys
kubectl exec deploy/test -- python claude_agent_sdk.py "https://github.com/74th の要約して"
kubectl exec deploy/test -- python test_bq.py
kubectl exec deploy/test -- curl --connect-timeout 3 --max-time 10 http://checkip.amazonaws.com
```

最後のコマンドは FQDN policy 適用後に失敗することが期待されます。policy の動作を確認するときは、`kubectl get pods -l app=test,component=isolated-claude-agent` で新しい Pod 名を取得してください。

## トラブルシューティングと観測した endpoint

Claude または BigQuery が policy 適用後だけ失敗する場合は、コマンドのエラーを記録し、クライアントが実際に使用した正確な endpoint の DNS を観測してください。その正確な FQDN だけを `k8s/fqdn-network-policy.yaml` に追加し、基準テスト、policy の再適用、適用後テストの順に再実行します。Claude の GitHub 要約はコンテナ内で `github.com` を取得してから Claude Agent SDK に内容を渡すため、`api.github.com` や `claude.ai` のような補助 endpoint は許可していません。allowlist を `0.0.0.0/0`、`*.com`、または広範囲な `*.googleapis.com` に置き換えてはいけません。

## ロールバックと削除

ワークロードを残したまま、通信制御を解除して基準状態へ戻すには次を実行します。

```bash
kubectl delete -f k8s/fqdn-network-policy.yaml
kubectl delete -f k8s/network-policy.yaml
```

ワークロードだけを削除するには次を実行します。

```bash
kubectl delete deployment/test serviceaccount/test
```

この環境は課金対象リソースを作成します。不要になったことを確認した後、plan を確認してから `terraform -chdir=terraform destroy -var="project_id=${PROJECT_ID}"` を実行できます。destroy は意図的にスクリプトから自動実行しません。
