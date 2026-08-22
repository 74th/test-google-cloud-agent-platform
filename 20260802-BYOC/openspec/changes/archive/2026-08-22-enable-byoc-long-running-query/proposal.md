## Why

BYOC の長時間実行クエリはジョブ自体を開始できるものの、実行サービスアカウントが GCS 入力を取得する際に `serviceusage.services.use` の拒否を受け、コンテナのルートエンドポイントへ配送される前に失敗している。さらに、権限問題の解消後も現在の GCS 入力はルートエンドポイントの必須フィールドを満たさないため、Google の成功例と同じ経路で短時間・15分超の処理を段階的に実証できる状態にする必要がある。

## What Changes

- BYOC 実行サービスアカウントへ、長時間ジョブの proxy が GCS API を利用するために必要な Service Usage 権限を宣言的に付与する。
- 長時間ジョブ用 GCS 入力をルートエンドポイントが受理できるクエリ形式にし、通常の Agent Platform 操作とは独立して `POST /` を検証できるようにする。
- 長時間ジョブの実入力 URI、実出力 URI、operation の最終エラー、proxy-container と job-container のログを収集し、GCS 取得失敗・HTTP 配送失敗・アプリ処理失敗を区別する。
- まず約10秒の短時間ジョブで経路全体を確認し、その成功後に15分を超えるジョブをキャンセルせず完了まで監視する再現可能な検証を追加する。
- 過去の「未到達」判定を、判明した GCS 取得時の IAM エラーを根拠に再評価し、検証結果と手順を更新する。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `agent-query-verification`: 長時間ジョブの前提権限、実際の GCS URI、proxy/job コンテナログ、operation エラーを含む段階別診断と、短時間成功後の15分超検証を要求する。
- `byoc-query-runtime`: GCS 経由の長時間ジョブ入力を `POST /` で受理し、非ストリーミング応答として処理できるランタイム契約を追加する。

## Impact

- Terraform の実行サービスアカウント IAM が変更対象となる。
- `scripts/query_job.py` の入力生成、状態・結果収集、Cloud Logging フィルター、評価ロジックが変更対象となる。
- `byoc_runtime/app.py` と入力モデルは、ルートエンドポイントの長時間ジョブ入力契約に合わせて変更される可能性がある。
- 長時間検証用の遅延設定、テスト、README、非機密の結果記録を更新する。
- Agent Platform の通常4操作の公開契約と応答形式に破壊的変更は加えない。
