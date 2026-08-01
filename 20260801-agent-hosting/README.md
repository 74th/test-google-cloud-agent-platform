# Claude Agent SDK を Agent Platform へデプロイする時刻表エージェント

`workspace/.claude/skills/bus-schedule/SKILL.md` が時刻表の唯一の参照元です。コンテナは Google Cloud Agent Platform のカスタムコンテナ契約を実装し、Claude Agent SDK がこのスキルを読み取ります。

## 前提条件

- Python 3.12、Docker、Google Cloud CLI
- `gcloud auth application-default login` 済みの Google Cloud 認証
- Terraform を実行できる権限。Terraform は Vertex AI／Artifact Registry API、Agent Platform コンテナ専用のサービスアカウント、Vertex AI 推論権限、および `us-central1` の Docker Artifact Registry リポジトリを作成する
- Vertex AI Model Garden で有効化済みの Claude Haiku 4.5

Google Cloud Agent Platform はカスタムコンテナに `0.0.0.0:8080` の待受けを求めます。本実装は、SDK 標準呼び出し用の `query`／`stream_query` と `/api/reasoning_engine`／`/api/stream_reasoning_engine` を公開します。詳細は [ランタイム契約](https://cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/runtime-contract) と [コンテナイメージのデプロイ](https://cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/deploy-an-agent) を参照してください。

## ローカル検証

```bash
uv sync --extra test --extra client --extra deploy
uv run pytest
docker build -t kanazawa-timetable-agent .
docker run --rm -p 8080:8080 -e ANTHROPIC_API_KEY kanazawa-timetable-agent
```

コンテナが起動したら、別の端末で以下を実行します。

```bash
curl -X POST localhost:8080/api/reasoning_engine \
  -H 'Content-Type: application/json' \
  -d '{"class_method":"query","input":{"message":"次のバスは何時？"}}'
```

時刻表を決定的に検証するには、アダプターの時計を JST の対象時刻へ固定してテストします。例えば 08:30 JST は次の便が 08:35 発・09:00 着の兼六・ひがし茶屋コースであり、回答には金沢テスト病院経由・約25分の注意を含めます。最終便後のケースも固定時計で「以降の便なし」を確認してください。

## デプロイとロールバック

このエージェントはサービスアカウントの Application Default Credentials を使い、Vertex AI の `claude-haiku-4-5@20251001` を明示して Claude Agent SDK を実行します。API キーと Secret Manager は使用しません。Claude Code の Vertex AI 設定は [公式ガイド](https://code.claude.com/docs/en/google-vertex-ai) に従います。

まず Terraform で専用の実行サービスアカウントと Docker Artifact Registry リポジトリ `agent-hosting-20260801` を作成します。この ID は Artifact Registry の命名規則に従い英字で開始します。このアカウントには Vertex AI 推論に必要な `roles/aiplatform.user` のみを付与します。Agent Runtime のサービスエージェントには、このテスト用リポジトリの読み取り権限だけを付与します。

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
cd ..
```

Terraform はこの実行サービスアカウントに `roles/aiplatform.user` を付与し、`agent-hosting-20260801` リポジトリを作成します。Claude API キーと Secret Manager の権限は作成しません。

デプロイスクリプトはローカルの Docker でイメージをビルドし、`gcloud auth configure-docker` で Artifact Registry の認証を設定してから push します。Cloud Build は使用しません。

値を含めない [`.env.example`](.env.example) を参考に残りの環境変数を設定します。

```bash
export PROJECT_ID=nnyn-dev
export LOCATION=us-central1
export VERTEX_PROJECT_ID=nnyn-dev
export VERTEX_REGION=global
./scripts/deploy.sh
```

`VERTEX_REGION=global` は Haiku 4.5 の通常の推論先です。グローバルエンドポイントで利用できない場合は、コンテナが `us-east5` を Haiku 用のフォールバック先として使用します。Agent Platform のホスティング先 `LOCATION=us-central1` とは独立した設定です。

出力された完全なリソース名を保存し、ローカルのライブスモークテストを実行します。

```bash
export AGENT_RESOURCE='projects/.../locations/.../reasoningEngines/...'
python scripts/invoke_agent.py --location "$LOCATION" '次のバスは何時？'
```

ロールバック（削除）は次のとおりです。

```bash
python scripts/delete_agent.py --project "$PROJECT_ID" --location "$LOCATION" --agent-resource "$AGENT_RESOURCE"
```

デプロイ先はサービスの underlying API を認証付きで呼び出します。エンドポイント形式は [デプロイ済みエージェントの利用](https://cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/use-an-agent) の仕様に従います。
