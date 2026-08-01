## Purpose

Web チャット UI を導入する前に、ローカル Python クライアントから呼び出して動作を確認できる、Google Cloud Agent Platform 向けのデプロイ可能な Claude Agent SDK サービスを提供する。

## ADDED Requirements

### Requirement: Hosted agent deployment is reproducible
プロジェクトは、Claude Agent SDK サービスを Google Cloud プロジェクト `nnyn-dev` の Google Cloud Agent Platform にデプロイする、バージョン管理されたコンテナおよびデプロイ用アセットを提供する SHALL。デプロイ設定は、ロケーションやランタイム認証情報を含む環境固有の値を、シークレットのハードコードではなく文書化された入力から取得する SHALL。

#### Scenario: Deploy with configured prerequisites
- **WHEN** 運用者が文書化された Google Cloud 認証、プロジェクトアクセス権、ロケーション、Claude 認証情報の設定を与え、デプロイ手順を実行した場合
- **THEN** 手順はサービスコンテナをビルドまたは選択し、`nnyn-dev` 内の設定済み Agent Platform 環境へデプロイし、呼び出しに必要な識別子またはエンドポイントを出力する

#### Scenario: Missing required deployment configuration
- **WHEN** 運用者が必須の非シークレット設定値を指定せずにデプロイ手順を実行した場合
- **THEN** 手順はデプロイ前に失敗し、不足している値と指定方法を示すメッセージを出力する

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
