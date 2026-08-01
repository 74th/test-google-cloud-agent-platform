## Purpose

Web チャット UI を導入する前に、ローカル Python クライアントから呼び出して動作を確認できる、Google Cloud Agent Platform 向けのデプロイ可能な Claude Agent SDK サービスを提供する。

## ADDED Requirements

### Requirement: Hosted agent deployment is reproducible
プロジェクトは、Claude Agent SDK サービスを Google Cloud プロジェクト `nnyn-dev` の Google Cloud Agent Platform にデプロイする、バージョン管理されたコンテナ、Terraform、およびデプロイ用アセットを提供する SHALL。主なロケーションの既定値は `us-central1` とし、コンテナは専用サービスアカウントの Application Default Credentials を使用して Vertex AI の Claude モデルを呼び出す SHALL。Claude API キーや Secret Manager シークレットをデプロイ設定へ含めてはならない。

#### Scenario: Deploy with configured prerequisites
- **WHEN** 運用者が文書化された Google Cloud 認証、プロジェクトアクセス権、ロケーション、Claude 認証情報の設定を与え、デプロイ手順を実行した場合
- **THEN** 手順はサービスコンテナをビルドまたは選択し、`nnyn-dev` 内の設定済み Agent Platform 環境へデプロイし、呼び出しに必要な識別子またはエンドポイントを出力する

#### Scenario: Missing required deployment configuration
- **WHEN** 運用者が必須の非シークレット設定値を指定せずにデプロイ手順を実行した場合
- **THEN** 手順はデプロイ前に失敗し、不足している値と指定方法を示すメッセージを出力する

### Requirement: Agent runtime uses a Terraform-managed service account
プロジェクトは、Claude Agent SDK コンテナが Agent Platform 上で実行されるための専用サービスアカウントを Terraform で作成し、デプロイに使用する SHALL。Terraform は当該サービスアカウントに Vertex AI 推論に必要な最小限の IAM 権限を付与する SHALL。Claude API キーや Secret Manager 読み取り権限を作成してはならない。

#### Scenario: Deploy with Terraform-managed runtime identity
- **WHEN** 運用者が `us-central1` を指定して Terraform を適用した場合
- **THEN** Terraform は専用の実行サービスアカウントを出力し、デプロイ手順はそのメールアドレスを Agent Platform の `service_account` に指定する

### Requirement: Container image repository is Terraform-managed
プロジェクトは、`us-central1` に Docker Artifact Registry リポジトリ `agent-hosting-20260801` を Terraform で作成する SHALL。リポジトリ ID は Artifact Registry の命名規則に従い英字で開始する SHALL。Terraform は Agent Runtime のサービスエージェントへ当該リポジトリだけの読み取り権限を付与し、デプロイスクリプトはリポジトリ名を Terraform output から取得する SHALL。

#### Scenario: Deploy after Terraform creates the image repository
- **WHEN** 運用者が Terraform を適用してからデプロイスクリプトを実行する
- **THEN** スクリプトは環境変数によるリポジトリ名の指定を必要とせず、ローカル Docker でビルドしたコンテナイメージを Terraform output の `agent-hosting-20260801` に push する

### Requirement: Deployment builds and pushes images locally
デプロイスクリプトは、ローカル Docker でコンテナイメージをビルドし、Artifact Registry の Docker 認証を設定してイメージを push する SHALL。Cloud Build を呼び出してはならない。

#### Scenario: Build and publish image without Cloud Build
- **WHEN** 運用者が Docker と Google Cloud 認証を備えたローカル環境でデプロイスクリプトを実行する
- **THEN** スクリプトは `docker build` と `docker push` を実行し、Cloud Build のジョブを作成しない

### Requirement: Agent SDK uses Claude Haiku 4.5 on Vertex AI
Claude Agent SDK を呼び出すアダプターは Vertex AI モードを有効にし、Vertex AI のモデル ID `claude-haiku-4-5@20251001` を明示的に設定する SHALL。

#### Scenario: Invoke the packaged agent
- **WHEN** 有効なテキストプロンプトがエージェントランタイムへ送られた場合
- **THEN** アダプターはサービスアカウント認証と `claude-haiku-4-5@20251001` を指定した Claude Agent SDK オプションで問い合わせを実行する

### Requirement: Agent accepts and returns text conversations
ホストされたサービスは、文書化された Agent Platform 呼び出しインターフェースを通じてテキストプロンプトを受け付け、呼び出し元が表示できる形式でエージェントのテキスト応答を返す SHALL。リクエストを処理できない場合、サービスは明確な呼び出し失敗を呼び出し元に返す SHALL。

#### Scenario: Successful text invocation
- **WHEN** 呼び出し元が有効な日本語テキストプロンプトをデプロイ済みエージェントへ送信した場合
- **THEN** 呼び出し元はエージェントのテキスト応答を受け取り、プロバイダー内部データを解析せずに出力できる

#### Scenario: Invocation failure
- **WHEN** デプロイ先エンドポイントが利用できない、または呼び出しを拒否した場合
- **THEN** ローカルの呼び出し元は対処可能なエラー文脈とともに非ゼロ終了で失敗を報告し、空の応答を成功した回答として表示しない

### Requirement: Local smoke-test client invokes the deployment
プロジェクトは、文書化された設定からデプロイ済みエージェントの識別子またはエンドポイントを受け取り、プロンプトを送信し、得られた応答を標準出力へ書き出すローカル Python クライアントを提供する SHALL。文書化されたスモークテストとして、バス時刻の質問 `次のバスは何時？` をサポートする SHALL。

#### Scenario: Run the documented bus-time smoke test
- **WHEN** 運用者が成功済みのデプロイに向けてローカルクライアントを設定し、`次のバスは何時？` を指定して実行した場合
- **THEN** クライアントはそのプロンプトをホストされたエージェントへ送信し、返された回答を表示する
