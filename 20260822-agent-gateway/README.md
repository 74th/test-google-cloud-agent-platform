# 20260822 Agent Gateway 外向き通信ポリシー検証

このリポジトリは、Google Cloud Agent Gateway の配下で Claude Agent SDK を使う BYOC エージェントを検証する、再現可能なテスト用構成です。リソースは `nnyn-dev/us-central1` にのみ作成し、Claude の Vertex AI 推論先は `nnyn-dev/global` に固定します。リソース名とラベルには `20260822` を含め、`20260801-agent-hosting` とは独立しています。

セキュリティ境界は Agent-to-Anywhere モードの Agent Gateway です。Gateway は Agent Registry と IAP の egress 認可を使い、登録されていない宛先を既定で拒否し、登録した `https://github.com` endpoint のみを明示的に許可します。個別ホスト向けの deny ルールは作成しません。

## 前提条件

- 課金が有効な Google Cloud プロジェクト `nnyn-dev`。API 有効化、IAM binding、Agent Gateway 作成、Agent Runtime デプロイの権限が必要です。
- Agent Gateway と Agent Registry のコマンドグループを含む `gcloud` 581.0.0 以降。ADC と gcloud アカウントの認証も必要です。
- Terraform 1.8 以降、Google provider 7.20 以降、Docker、`uv`。
- Vertex AI Model Garden で Claude Haiku 4.5 を有効化済みであること。Anthropic API key と Secret Manager secret は使用しません。

クラウド操作の前に認証します。

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project nnyn-dev
uv sync --extra test --extra deploy
```

関連する設定値は [.env.example](.env.example) にも記載しています。

```bash
export PROJECT_ID=nnyn-dev
export LOCATION=us-central1
export VERTEX_PROJECT_ID=nnyn-dev
export VERTEX_REGION=global
export AGENT_GATEWAY_NAME=agw-20260822-egress
```

## 基盤の構築

Agent Gateway の公式 Terraform resource は、今回の検証で使う schema が安定版 provider にまだ含まれていないため、固定した nightly provider で提供されています。provider の選択とバージョンは [terraform/versions.tf](terraform/versions.tf) に記録しています。公式の参考モジュールは [terraform-google-agent-gateway](https://github.com/GoogleCloudPlatform/terraform-google-agent-gateway) です。

```bash
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
cd ..
```

`terraform apply` は API、専用 Artifact Registry、必要最小限の IAM binding、Google 管理の Agent Gateway を作成します。Runtime は Agent Identity を使うため、Runtime 専用 Service Account は作成しません。`20260801-agent-hosting` のリソースは作成・変更しません。

### egress-policy.yaml の位置づけ

[terraform/egress-policy.yaml](terraform/egress-policy.yaml) は Terraform に読み込まれる構築設定ではありません。現在の Agent Gateway Terraform resource にこの YAML を直接投入する schema がないため、`terraform plan` や `terraform apply` はこのファイルを参照しません。

このファイルは、期待する外向き通信ポリシー（既定拒否、`github.com` のみの Web allow、内閣府 endpoint の未列挙）を記録したレビュー用の契約ファイルです。`tests/test_terraform.py` の静的検査と、検証ランナーの `--policy`（既定値はこのファイル）による証跡保存で使用します。実際の Gateway の制御は、下記の Agent Gateway の managed 設定、Agent Registry endpoint 登録、IAP の IAM 認可で行います。

## BYOC エージェントの build と deploy

`terraform apply` の後、`scripts/deploy.sh` が Docker 認証を設定し、専用イメージを build/push し、custom container の Agent Runtime を作成して、Terraform の Agent Gateway resource を `agentToAnywhereConfig` に関連付けます。イメージには `CLAUDE_CODE_USE_VERTEX=1`、`nnyn-dev` の Vertex project、推論リージョン `global`、`claude-haiku-4-5@20251001` を設定します。

このスクリプトは Gateway の root CA を取得して、実際に push する image build に渡します。証明書なしで単独実行する `docker build` はローカルだけの捨て build であり、再現可能な deploy 手順には含めません。

```bash
./scripts/deploy.sh
export AGENT_RESOURCE=projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID
```

Runtime の契約は、`query` 用の `POST /api/reasoning_engine`、`stream_query` 用の `POST /api/stream_reasoning_engine`、および `GET /health` です。SDK に公開する tool は `WebFetch` だけです。URL が指定された場合は回答前に必ず取得し、取得に失敗した場合はその事実を明示して、記憶から内容を補完してはいけません。

## endpoint の登録と GitHub の認可

Agent Gateway 自体にはホストごとの deny list はありません。上記の [terraform/egress-policy.yaml](terraform/egress-policy.yaml) はレビュー用の契約であり、実際の endpoint 登録を行うファイルではありません。ユーザーが指定する Web allow は `github.com` のみです。Agent Platform に必要な Google 管理サービス（`agentregistry.googleapis.com`、`aiplatform.googleapis.com`、`logging.googleapis.com`）は別枠で記録し、任意の Web 宛先として扱いません。

まず既存の Registry を確認します。すでに一覧にある endpoint は再作成しないでください。

```bash
gcloud agent-registry endpoints list --project=nnyn-dev --location=us-central1
```

必要な managed endpoint が存在しない場合だけ、helper に定義した固定 URL と resource 名で登録します。helper が受け付ける Google 管理 endpoint 名は次の 3 つだけです。

```bash
uv run python scripts/gateway.py register-managed --name agentregistry
uv run python scripts/gateway.py register-managed --name aiplatform
uv run python scripts/gateway.py register-managed --name logging
```

GitHub endpoint が存在しない場合に登録し、一覧で確認した endpoint ID と、deploy 済み Agent Runtime の identity principal を使って IAP egressor binding を設定します。identity principal は `deploy.sh` が Runtime を作成した後でなければ確定しません。

```bash
uv run python scripts/gateway.py register-github
gcloud agent-registry endpoints list --project=nnyn-dev --location=us-central1
uv run python scripts/gateway.py allow-github \
  --project=nnyn-dev --location=us-central1 \
  --endpoint=ENDPOINT_ID \
  --principal='principal://agents.global.org-PROJECT_NUMBER.system.id.goog/resources/aiplatform/projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID'
```

未承認の検証対象（`www8.cao.go.jp`）は登録しません。その宛先については、個別 deny policy ではなく、既定拒否を示す Gateway/IAP の判定ログを証跡にします。

## ライブ検証

Gateway の設定 export は呼び出し前に行います。検証ランナーは 2 つの prompt を実行した後に Gateway と IAP のログを収集するため、判定対象の呼び出しに紐づくログを使えます。Agent Gateway のログは monitored resource `networkservices.googleapis.com/Gateway` に記録されます。

```bash
mkdir -p evidence/live
gcloud network-services agent-gateways describe agw-20260822-egress \
  --project=nnyn-dev --location=us-central1 --format=json > evidence/live/gateway.json
export VALIDATION_SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
uv run python scripts/validate.py \
  --agent-resource "$AGENT_RESOURCE" \
  --location us-central1 \
  --collect-after \
  --project nnyn-dev \
  --gateway agw-20260822-egress \
  --since "$VALIDATION_SINCE"
```

Runner は UTC の timestamp directory に、正確な入力、応答、stderr、終了状態、allow/deny に一致したログ、policy のコピー、収集ログ、`summary.json` を保存します。GitHub ケースは、`GitHub` と `74th` の両方に言及する応答と、`github.com` の `allow` 記録が揃った場合だけ合格します。2027 年祝日ケースは、取得失敗を示して祝日一覧を含まない応答と、`www8.cao.go.jp` の `deny` 記録が揃った場合だけ合格します。応答だけでは通信成功の証明になりません。

## 証跡とレポート

完了済みのライブ検証は[日付付きレポート](evidence/20260822-report.md)で確認できます。保存した Gateway policy 契約、2 つの正確な prompt、応答、終了状態、判定に使った Gateway/IAP のログ項目、合否、外部サイトの可用性などの制約を記載しています。access token、ADC の内容、API key などの秘密情報は保存しないでください。

## クリーンアップ（人間による確認が必要）

この検証は自動的にリソースを削除しません。人間が証跡を確認してから、次の手順を実行します。

1. 完全な resource name を指定して、デプロイした Agent Runtime だけを削除します。

   ```bash
   uv run python scripts/delete_agent.py --project=nnyn-dev --location=us-central1 --agent-resource="$AGENT_RESOURCE"
   ```

2. Agent Registry に `20260822-agent-gateway` のリソースが残っていないこと、Gateway 呼び出しが実行中でないことを確認します。
3. このリポジトリの `terraform/` directory で plan を確認してから `terraform destroy` を実行し、この state だけを削除します。`20260801-agent-hosting` や別 workspace から destroy してはいけません。
4. `20260822` の名前と label を使って Artifact Registry、service account、Agent Gateway を再確認します。

deploy に失敗した場合は、`terraform show`、Agent Gateway export、Agent Registry endpoint の状態、Runtime の deploy spec、Gateway log を確認します。よくある原因は Model Garden model の無効化、Agent Identity の設定不備、Artifact Registry reader binding の不足、リージョン不一致、endpoint 未登録、BYOC Gateway root certificate の未信頼です。
