## Why

Agent Platform の Agent Registry が、実際にホストした MCP Server の登録・発見に利用できるかを小さな再現可能な環境で確認したい。まず運用負荷とコストを抑えやすい Cloud Run を検証し、続いて GKE Standard 上の MCP Server でも同じ登録・呼び出し経路が成立するかを比較する。

## What Changes

- Streamable HTTP の `/mcp` エンドポイントと単純な応答 Tool を提供する、ステートレスな検証用 MCP Server とコンテナを追加する。
- `nnyn-dev` に Cloud Run 実行環境を Terraform で構築し、IAM 認証、`min_instance_count = 0`、ログ、および Agent Registry 登録・発見を検証する。
- 専用 Custom VPC と小規模な GKE Standard クラスタを Terraform で構築し、同じ MCP Server をデプロイして Agent Registry 経由の発見と直接実行を検証する。
- 既存リソースと競合しないよう、作成リソース名に `20260823-mcp-server` を含め、専用 Service Account と最小権限の IAM を使用する。
- Cloud Run と GKE の正常系、未認証拒否、Tool 定義の整合性、Cloud Run の scale-to-zero 後の再実行を自動または手順化されたスクリプトで検証する。
- 実行コマンド、構築リソース、実測結果、証跡、コストを伴うリソース、削除手順、および Cloud Run と GKE の比較・結論を Markdown に記録する。証跡のない項目は PASS としない。
- 初期スコープから Agent Gateway と Claude Agent SDK の再構築、Tool の追加・削除・破壊的 schema 変更、traffic split、網羅的障害注入、Cloud Run から GKE 内部 Backend への接続は除外し、Agent Registry と二つのホスティング方式の成立性に集中する。

## Capabilities

### New Capabilities

- `mcp-server-runtime`: 同一の検証用 MCP Server コンテナを Cloud Run と GKE Standard に配置し、認証されたクライアントから MCP Tool を実行できる能力。
- `agent-registry-discovery`: Cloud Run および GKE の MCP Server と Tool を Agent Registry に登録し、検索結果からエンドポイントと Tool 定義を発見できる能力。
- `terraform-poc-environment`: 競合回避、既存環境の保護、最小権限、低コスト、再作成・削除可能性を備えた検証基盤を Terraform で管理する能力。
- `verification-evidence`: 実環境での検証を再現し、結果と証跡をホスティング方式ごとに記録して採用判断を行う能力。

### Modified Capabilities

なし。

## Impact

- MCP Server のソース、依存関係、Dockerfile、Tool specification、テスト用クライアントを新規追加する。
- Terraform 構成として API 有効化、Artifact Registry、Service Account/IAM、Cloud Run、Custom VPC/Subnet、GKE Standard、および Agent Registry 登録に必要なリソースまたは補助手順を追加する。
- GKE 用 Kubernetes manifest と、build・deploy・検証・cleanup の手順またはスクリプトを追加する。
- Google Cloud project `nnyn-dev` に課金対象リソースを作成する。既存 Autopilot cluster を含む既存リソースは変更しない。
- 実装時は利用中の Google Cloud API、Terraform provider、`gcloud` の Agent Registry 対応状況を公式ドキュメントと CLI help で確認する必要がある。
