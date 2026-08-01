## Why

計画している Streamlit チャット UI を追加する前に、Google Cloud Agent Platform 上でエージェントをホストする経路を、小さくデプロイ可能な形で検証する必要がある。これにより UI の懸念からコンテナのデプロイとリクエスト／レスポンス連携を切り離し、Claude Agent SDK のエージェントがプロジェクト提供の知識を利用できることを確認する。

## What Changes

- Google Cloud Agent Platform でホスト可能な、コンテナ化された Claude Agent SDK サービスを追加する。
- 金沢さくら台三丁目と金沢みらい駅の架空路線を対象とする日本語のテスト用バス時刻表スキルを追加し、約25分かかる病院経由便への注意も含める。
- Google Cloud プロジェクト `nnyn-dev` を対象とするデプロイ自動化を追加する。
- Terraform により、Agent Platform 上の Claude Agent SDK コンテナ専用のサービスアカウント、Vertex AI 推論用の最小権限 IAM バインディング、`us-central1` のテスト用 Docker Artifact Registry リポジトリを管理する。
- コンテナイメージはローカル Docker でビルドして Artifact Registry へ push し、Cloud Build は使用しない。
- Claude Agent SDK が Vertex AI をサービスアカウント認証で使用し、Vertex AI の固定モデル ID `claude-haiku-4-5@20251001` を使用するよう明示的に設定する。
- デプロイ済みのエージェントサービスにプロンプトを送って応答を表示するローカル Python クライアントを追加し、`次のバスは何時？` のユースケースを検証する。
- 前提条件、デプロイ手順、エンドポイント設定、テスト手順を文書化する。

## Capabilities

### New Capabilities

- `hosted-claude-agent`: Claude Agent SDK コンテナを Google Cloud Agent Platform にデプロイし、ローカル Python クライアントから呼び出す。
- `bus-schedule-agent-skill`: パッケージ化した金沢さくら台三丁目、金沢みらい駅、金沢テスト市役所の架空時刻表知識を用いて、バス時刻表の質問に回答する。

### Modified Capabilities

- なし。

## Impact

- アプリケーションおよびコンテナ設定、Terraform、デプロイ／ローカルクライアント用スクリプト、運用ドキュメントを追加する。
- プロジェクト `nnyn-dev` に対する Google Cloud 認証と権限、設定済みの Google Cloud Agent Platform 環境、および Vertex AI Model Garden で有効化済みの Claude Haiku 4.5 へのアクセスが必要になる。
- 後から Streamlit Chat UI が呼び出すサービス境界を確立する。この初回変更の対象には UI 自体を含めない。
