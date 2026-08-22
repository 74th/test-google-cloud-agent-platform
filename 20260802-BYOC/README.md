# BYOC query operation verification

Gemini Enterprise Agent Platform の BYOC コンテナに対して、`query`、`async_query`、`stream_query`、`async_stream_query` の配送、応答時刻、コンテナログを検証します。コンテナは単項要求を約10秒後に `OK`、ストリーム要求を約5秒後に `Streaming OK`、約10秒後に `OK` として返します。

## 前提条件

Python 3.12、[uv](https://docs.astral.sh/uv/)、Docker、Google Cloud CLI、Application Default Credentials が必要です。クラウド検証では対象プロジェクトへの Agent Platform、Artifact Registry、Cloud Storage、Cloud Logging の権限が必要です。

```bash
uv sync --group dev
uv run pytest -q
uv run byoc-runtime
```

別ターミナルでローカルのルート単項要求と4操作を実行します。標準出力は試行 ID、応答順序、経過時間を含む JSON Lines です。

```bash
curl --fail --silent --show-error --write-out '\nstatus=%{http_code}\n' \
  -H 'content-type: application/json' \
  -d '{"class_method":"query","input":{"verification_id":"local-root-smoke"}}' \
  http://127.0.0.1:8080/
# {"output":"OK"}
# status=200

uv run byoc-verify --target local --operation all
```

ルート要求では `path=/` の `http_received`、`query_started`、`query_completed`、`http_completed` が同じ `request_id` で出ることを確認します。ログ確認時は本文やヘッダーを表示せず、イベント名・パス・操作名・検証 ID だけを抽出します。例えばローカル標準出力を保存した場合は次のように確認できます。

```bash
rg '"event": "(http_received|query_started|query_completed|http_completed)"' runtime.log \
  | jq -c 'with_entries(select(.key | IN("timestamp","event","request_id","path","method","class_method","verification_id","status")))'
```

```bash
uv run byoc-verify --target local --operation all
```

## コンテナ検証

```bash
docker build -t byoc-query-verification .
docker run --rm --name byoc-query-verification-smoke -p 18080:8080 byoc-query-verification
uv run byoc-verify --target local --base-url http://127.0.0.1:18080 --operation all
```

コンテナ標準出力の `http_received`、`query_started`、`query_chunk`（ストリームのみ）、`query_completed`、`http_completed` を同じ `request_id` と `verification_id` で照合してください。ログ本文には入力本文・Authorization ヘッダー・トークンを記録しません。停止後に確認する場合も、`docker logs ... | jq` で上記の許可フィールドだけを表示します。

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

作成コマンドは `results/deployment.json` にエージェントリソース名と operation schema を保存します。Agent Platform のカスタムコンテナ契約（`0.0.0.0:8080`、ルートおよび既存 API パス、`classMethods` のルーティング）は [公式ランタイム契約](https://cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract) を確認してください（確認日: 2026-08-02）。

デプロイ後は以下で REST 経路を検証します。

```bash
uv run byoc-verify --target deployed --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" --operation all \
  | tee results/deployed-operations.jsonl
```

SDK と REST の差異を調べる場合は、SDK の `remote_agent.query` / `async_query` / `stream_query` / `async_stream_query` とこの REST CLI を同じ `verification_id` の形式で別ファイルへ記録し、Cloud Logging の同じ ID と照合します。

## 長時間ジョブ

`run_query_job` は最大7日間の実行を想定した探索的検証です。BYOC へ到達しない結果も有効な証跡です。CLI は試行 ID、対象エージェント、ジョブ名、開始時刻、監視期限、GCS URI、ログ検索範囲を同じ JSON Lines ファイルへ保存します。

```bash
uv run byoc-query-job --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" \
  --output-gcs-uri "gs://YOUR_BUCKET/query-jobs/output.json" \
  --result results/query-job.jsonl
```

必要に応じて `--timeout-seconds`、`--interval-seconds`、`--log-grace-seconds` を指定します。結果の `evaluation` 行には次の4段階が保存されます。

| 段階 | 成功条件 |
| --- | --- |
| `http_delivery` | 対象時間範囲の `POST /` 受信ログ |
| `processing` | 同じ request ID／検証マーカーの処理完了ログ |
| `job_terminal_state` | ジョブの成功終端状態 |
| `gcs_output` | 指定 URI の出力オブジェクト存在（内容は取得しない） |

総合結果は、4段階すべて成功なら `動作確認`、ルート到達後に失敗または出力欠落があれば `配送確認・動作未確認`、十分なログ検索でルート受信がなければ `未到達`、権限・期限・関連付け不足があれば `判定不能` です。結果には Cloud Logging の検索フィルター、対象リソース、時間範囲、ジョブ状態遷移を含め、ログ本文や入力本文、認証情報は保存しません。REST `:asyncQuery` の GCS 入力方式は SDK 経路とは別に記録して比較します。

## 2026-08-02 の検証結果

対象は `us-central1` にデプロイした検証専用の BYOC エージェントです。REST `:query` と `:streamQuery`、および Cloud Logging の同じ `verification_id` を照合しました。SDK バージョンは `google-cloud-aiplatform 1.163.0`、公式ドキュメント確認日は 2026-08-02 です。

| 操作 | 結果 | クライアント観測 |
| --- | --- | --- |
| `query` | 成功、`OK` | 約11秒 |
| `async_query` | 成功、`OK` | 約11秒 |
| `stream_query` | 成功、`Streaming OK` → `OK` | 約6秒 → 約11秒 |
| `async_stream_query` | 成功、`Streaming OK` → `OK` | 約6秒 → 約11秒 |

長時間ジョブは `run_query_job` がジョブ名を返し、60秒間の `check_query_job` では一貫して `RUNNING` でした。出力先には入力ファイルだけが作成され、検証マーカーを持つコンテナ受信ログは確認できませんでした。期限内にジョブが完了していないため、到達性の判定は **「判定不能」** とします。これは同期4操作の成功とは別経路の観測結果であり、BYOC コンテナへの長時間ジョブ配送を確認できたことを意味しません。

## 2026-08-21 のルートエンドポイント検証結果

新しいルート対応イメージを検証専用エージェントへデプロイし、通常4操作はすべて成功しました。長時間ジョブは専用 GCS 出力先へ1試行だけ開始し、監視期限まで `RUNNING`、期限後にキャンセル要求を行いました。ログ取り込み猶予後の対象 Agent resource・時間範囲検索で `POST /` 受信ログはなく、GCS 指定オブジェクトもありませんでした。

段階別結果は `http_delivery=failure`、`processing=unknown`、`job_terminal_state=unknown`、`gcs_output=failure` で、総合結果は **「未到達」** です。検索処理と GCS API は成功したため、前回の「判定不能」から、今回の検索条件では「ジョブ開始済みだがルート配送を確認できない」へ判定を狭められました。これは処理完了や出力生成の成功を意味しません。機密情報を含まない詳細は `results/query-job-root-endpoint-20260821.md` を参照してください。

## 後片付け

対象名を明示してエージェントを削除してから Terraform 管理リソースを削除します。

```bash
uv run python -m scripts.delete_agent --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "projects/.../locations/.../reasoningEngines/..."
cd terraform && terraform destroy
```

`terraform destroy` の plan を確認し、意図した検証専用の Artifact Registry、サービスアカウント、GCS バケットだけであることを確認してください。
