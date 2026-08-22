# BYOC query operation verification

Gemini Enterprise Agent Platform の BYOC コンテナに対して、`query`、`async_query`、`stream_query`、`async_stream_query` の配送、応答時刻、コンテナログを検証します。コンテナは単項要求を約10秒後に `OK`、ストリーム要求を約5秒後に `Streaming OK`、約10秒後に `OK` として返します。

## 前提条件

Python 3.12、[uv](https://docs.astral.sh/uv/)、Docker、Google Cloud CLI、Application Default Credentials が必要です。クラウド検証では対象プロジェクトへの Agent Platform、Artifact Registry、Cloud Storage、Cloud Logging の権限が必要です。

長時間ジョブでは、実行サービスアカウントに `roles/serviceusage.serviceUsageConsumer`（`serviceusage.services.use`）と、対象バケットの `roles/storage.objectAdmin` が必要です。Terraform が専用サービスアカウント `byoc-query-runtime` へこの2つを宣言します。実行前の診断は GCS オブジェクト権限と Service Usage 権限を別々に記録します。

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
export REPOSITORY=byoc-query-verification TAG="${TAG:-manual-$(date -u +%Y%m%dT%H%M%SZ)}"
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

`run_query_job` は最大7日間の実行を想定した探索的検証です。BYOC へ到達しない結果も有効な証跡です。CLI は試行 ID、対象エージェント、ジョブ名、開始時刻、監視期限、SDK が返した実入力・実出力 GCS URI、ログ検索範囲を同じ JSON Lines ファイルへ保存します。

SDK が作成する入力オブジェクトの本文は `{"input":{"verification_id":"...","delay_seconds":10}}` です。`delay_seconds` は省略時10秒、15分超のゲートでは960秒を指定します。ルート `POST /` は操作名がないこの形式を `query` として処理し、通常の `/api/reasoning_engine` は既存の操作名必須契約を維持します。

実行中の標準出力には、各Google API呼び出しの `api_call` JSON Lines が出ます。`phase=before` が呼び出し前、`phase=after` が完了後で、`call_id` で対応付けられます。完了時は `response` にSDK応答の全文、失敗時は `error` に例外の全文を出します。API応答に機密情報が含まれる可能性があるため、標準出力を共有ログへそのまま保存しないでください。結果ファイルには従来どおり機密情報を除いた証跡だけが保存されます。

```bash
uv run byoc-query-job --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" \
  --output-gcs-uri "gs://YOUR_BUCKET/query-jobs/output.json" \
  --result results/query-job.jsonl
```

短時間ゲートは次のように実行します。`--cancel-on-timeout` を付けない限り、期限超過時もキャンセルせず、判定不能として証跡を保存します。

```bash
uv run byoc-query-job --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" \
  --output-gcs-uri "gs://YOUR_BUCKET/query-jobs/short-gate.json" \
  --delay-seconds 10 --result results/query-job-short-gate.jsonl
```

短時間ゲートの `job_terminal_state=success`、`POST /` の200、出力オブジェクト、`job-container` と `proxy-container` の対応ログを確認できた後、15分超の試験を開始します。

```bash
uv run byoc-query-job --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "$(jq -r .resource_name results/deployment.json)" \
  --output-gcs-uri "gs://YOUR_BUCKET/query-jobs/long-960.json" \
  --delay-seconds 960 --result results/query-job-960.jsonl
```

結果の `evaluation` 行には次の5段階が保存されます。

| 段階 | 成功条件 |
| --- | --- |
| `gcs_input` | 実入力オブジェクトの存在と proxy の入力取得エラーがないこと |
| `http_delivery` | 対象時間範囲の `POST /` 受信ログ |
| `processing` | 同じ request ID／検証マーカーの処理完了ログ |
| `job_terminal_state` | ジョブの成功終端状態 |
| `gcs_output` | SDK が返した URI の出力オブジェクト存在（内容は取得しない） |

総合結果は、5段階すべて成功なら `動作確認`、ルート到達後に失敗または出力欠落があれば `配送確認・動作未確認`、proxy の入力取得拒否なら `GCS入力取得失敗`、十分なログ検索でルート受信がなければ `未到達`、権限・期限・関連付け不足があれば `判定不能` です。結果には Cloud Logging の検索フィルター、対象リソース、時間範囲、ジョブ状態遷移を含め、ログ本文や入力本文、認証情報は保存しません。REST `:asyncQuery` の GCS 入力方式は SDK 経路とは別に記録して比較します。

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

## 2026-08-22 の長時間ジョブ検証結果

2026-08-21 の「未到達」は、proxy が GCS 入力を取得する前に実行サービスアカウントの `serviceusage.services.use` 権限で拒否されていたものと再評価しました。Terraform で `byoc-query-runtime` に `roles/serviceusage.serviceUsageConsumer` を追加し、対象バケットの `roles/storage.objectAdmin` と合わせて確認した後、同じ検証イメージで再実行しました。

短時間ゲート（`delay_seconds=10`）は、GCS 入力取得、`POST /` の HTTP 200、`SUCCESS` 終端、15バイトの JSON 出力、`proxy-container` と `job-container` の対応ログをすべて確認できました。その成功をゲートとして実行した960秒ジョブも次の結果になりました。

| 段階 | 結果 |
| --- | --- |
| GCS入力取得 | 成功。実入力 URI を確認 |
| HTTP配送 | `job-container` の `POST /` が HTTP 200 |
| アプリ処理 | 検証マーカーの `query_completed` を960秒後に確認 |
| operation | `SUCCESS`。キャンセルなし |
| GCS出力 | 実出力 URIのオブジェクトが存在（15 bytes、JSON） |

960秒ジョブは UTC 09:15:41 に処理を開始し、09:31:41 に `{"output":"OK"}` を出力して完了しました。SDK経路と REST `:asyncQuery` 経路の比較も両方 `SUCCESS` となり、同じ入力形式で `/` に配送され、同じ15バイトの JSON 出力を生成しました。詳細な非機密証跡は [960秒ジョブの結果](results/query-job-long-running-960-20260822.jsonl)、REST比較は [結果文書](results/rest-async-compare-20260822.md) を参照してください。

検証終了後、今回作成した検証用エージェントと一時GCSオブジェクトは削除しました。

## 後片付け

対象名を明示してエージェントを削除してから Terraform 管理リソースを削除します。

```bash
uv run python -m scripts.delete_agent --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-resource "projects/.../locations/.../reasoningEngines/..."
cd terraform && terraform destroy
```

`terraform destroy` の plan を確認し、意図した検証専用の Artifact Registry、サービスアカウント、GCS バケットだけであることを確認してください。
