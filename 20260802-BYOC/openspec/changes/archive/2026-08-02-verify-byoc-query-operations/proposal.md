## Why

Gemini Enterprise Agent Platform のカスタムコンテナ（BYOC）で、自作のエージェントが各クエリ操作を正しく受信・実行できるかを、応答時間とコンテナログを含めて再現可能に検証したい。通常のクエリに加え、過去の PoC でコンテナへの到達を確認できなかった長時間実行クエリジョブも再検証し、プラットフォーム側とコンテナ側の疎通範囲を明らかにする。

## What Changes

- FastAPI で Agent Platform のカスタムコンテナ・ランタイム契約を実装し、全リクエストの受信、処理開始、処理終了を標準出力へ記録する。
- `query` と `async_query` は処理開始から約10秒後に `OK` を返す。
- `stream_query` と `async_stream_query` は約5秒後に `Streaming OK`、約10秒後に `OK` を順次返す。
- 4種類のクエリ操作をローカルおよびデプロイ済みエージェントに対して呼び出し、応答内容、順序、経過時間、ログを検証できるクライアントとテストを追加する。
- 既存 PoC の構成を参考に、コンテナのビルド、Artifact Registry への push、Agent Platform へのデプロイ、呼び出し、ログ確認、削除までの手順を整備する。
- 長時間実行クエリジョブを開始・監視し、ジョブ状態、出力、およびコンテナへのリクエスト到達有無を証跡として確認する検証手順を追加する。

## Capabilities

### New Capabilities

- `byoc-query-runtime`: BYOC ランタイムが同期・非同期および非ストリーミング・ストリーミングの4操作を、所定の遅延応答と観測可能なログ付きで提供する。
- `agent-query-verification`: ローカルと Agent Platform 上で各クエリ操作および長時間実行クエリジョブを実行し、疎通結果を再現可能に検証する。

### Modified Capabilities

なし。

## Impact

- FastAPI アプリケーション、コンテナ定義、Python 依存関係を追加・変更する。
- Agent Platform API を呼び出すローカルクライアント、テスト、デプロイ・削除用スクリプトを追加する。
- Google Cloud の Artifact Registry、Agent Platform、Cloud Storage、Cloud Logging、および関連 IAM 設定を利用する。
- 検証には Google Cloud リソースの作成と利用料金が発生し得る。
