# BYOC query operation verification

Gemini Enterprise Agent Platform の BYOC コンテナに対して、`query`、`async_query`、`stream_query`、`async_stream_query` の配送、応答時刻、コンテナログを検証します。コンテナは単項要求を約10秒後に `OK`、ストリーム要求を約5秒後に `Streaming OK`、約10秒後に `OK` として返します。

## 前提条件

Python 3.12、[uv](https://docs.astral.sh/uv/)、Docker、Google Cloud CLI、Application Default Credentials が必要です。クラウド検証では対象プロジェクトへの Agent Platform、Artifact Registry、Cloud Storage、Cloud Logging の権限が必要です。

```bash
uv sync --group dev
uv run pytest -q
uv run byoc-runtime
```

別ターミナルでローカルの4操作を実行します。標準出力は試行 ID、応答順序、経過時間を含む JSON Lines です。

```bash
uv run byoc-verify --target local --operation all
```

## コンテナ検証

```bash
docker build -t byoc-query-verification .
docker run --rm -p 8080:8080 byoc-query-verification
uv run byoc-verify --target local --operation all
```

コンテナ標準出力の `http_received`、`query_started`、`query_chunk`（ストリームのみ）、`query_completed`、`http_completed` を同じ `verification_id` で照合してください。ログ本文には入力本文・Authorization ヘッダー・トークンを記録しません。

## デプロイ

環境固有値や資格情報はリポジトリへ保存しません。

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply

cd ..
export PROJECT_ID=your-project-id LOCATION=us-central1
export REPOSITORY=byoc-query-verification TAG="$(git rev-parse --short HEAD)"
IMAGE_URI="$(./scripts/build_push.sh)"
uv run python -m scripts.deploy_agent \
  --project "$PROJECT_ID" --location "$LOCATION" --image-uri "$IMAGE_URI" \
  --service-account "byoc-query-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
```

作成コマンドは `results/deployment.json` にエージェントリソース名と operation schema を保存します。Agent Platform のカスタムコンテナ契約（`0.0.0.0:8080`、2つの API パス、`classMethods` のルーティング）は [公式ランタイム契約](https://cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract) を確認してください（確認日: 2026-08-02）。

デプロイ後は以下で REST 経路を検証します。

```bash
uv run byoc-verify --target deployed --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" --operation all \
  | tee results/deployed-operations.jsonl
```

SDK と REST の差異を調べる場合は、SDK の `remote_agent.query` / `async_query` / `stream_query` / `async_stream_query` とこの REST CLI を同じ `verification_id` の形式で別ファイルへ記録し、Cloud Logging の同じ ID と照合します。

## 長時間ジョブ

`run_query_job` は最大7日間の実行を想定した探索的検証です。BYOC へ到達しない結果も有効な証跡です。

```bash
uv run byoc-query-job --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" \
  --output-gcs-uri "gs://YOUR_BUCKET/query-jobs/output.json" \
  --result results/query-job.jsonl
```

結果は `到達確認`（受信ログあり）、`未到達`（ジョブ開始済みかつマーカーの受信ログなし）、`判定不能`（ログ権限・期限などの証跡不足）として JSON Lines に保存されます。GCS 出力と、開始1分前からログ取り込み猶予後までの Cloud Logging を追加確認してください。REST `:asyncQuery` の GCS 入力方式は SDK 経路とは別に記録して比較します。

## 2026-08-02 の検証結果

対象は `us-central1` にデプロイした検証専用の BYOC エージェントです。REST `:query` と `:streamQuery`、および Cloud Logging の同じ `verification_id` を照合しました。SDK バージョンは `google-cloud-aiplatform 1.163.0`、公式ドキュメント確認日は 2026-08-02 です。

| 操作 | 結果 | クライアント観測 |
| --- | --- | --- |
| `query` | 成功、`OK` | 約11秒 |
| `async_query` | 成功、`OK` | 約11秒 |
| `stream_query` | 成功、`Streaming OK` → `OK` | 約6秒 → 約11秒 |
| `async_stream_query` | 成功、`Streaming OK` → `OK` | 約6秒 → 約11秒 |

長時間ジョブは `run_query_job` がジョブ名を返し、60秒間の `check_query_job` では一貫して `RUNNING` でした。出力先には入力ファイルだけが作成され、検証マーカーを持つコンテナ受信ログは確認できませんでした。期限内にジョブが完了していないため、到達性の判定は **「判定不能」** とします。これは同期4操作の成功とは別経路の観測結果であり、BYOC コンテナへの長時間ジョブ配送を確認できたことを意味しません。

## 後片付け

対象名を明示してエージェントを削除してから Terraform 管理リソースを削除します。

```bash
uv run python -m scripts.delete_agent --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "projects/.../locations/.../reasoningEngines/..."
cd terraform && terraform destroy
```

`terraform destroy` の plan を確認し、意図した検証専用の Artifact Registry、サービスアカウント、GCS バケットだけであることを確認してください。
