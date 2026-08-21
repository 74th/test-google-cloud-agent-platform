## Why

これまでの検証では Agent Platform の長時間実行クエリジョブが BYOC コンテナへ到達したことを確認できなかった。一方、Google から、既存の `POST /api/reasoning_engine` に加えて `POST /` を公開すると長時間実行クエリがルートパスへ配送されたとの情報を得たため、この経路を実測し、BYOC で長時間実行クエリを処理できるか結論を更新する必要がある。

## What Changes

- BYOC ランタイムに `POST /` を追加し、長時間実行クエリジョブから想定されるリクエストを受信して、既存の単項クエリ処理へ安全に接続する。
- `POST /` と既存の `POST /api/reasoning_engine` が同じ検証可能な処理結果とライフサイクルログを生成することをローカルテストで確認する。
- 長時間実行クエリジョブを一意な検証マーカー付きで実行し、ジョブ状態、GCS 出力、Cloud Logging のリクエストパスと処理ログを収集する。
- 収集した証跡から、ルートパスへの配送、処理完了、出力生成を個別に判定し、BYOC で動作するかどうかを再現可能な検証結果として記録する。
- 既存エンドポイントと4種類の通常クエリ操作の挙動は維持する。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `byoc-query-runtime`: 長時間実行クエリジョブの配送候補である `POST /` を受け付け、既存の単項処理と同等に検証マーカーを処理・記録できる要件を追加する。
- `agent-query-verification`: ルートパス経由の長時間実行クエリについて、配送先、ジョブ状態、出力、ログを収集し、動作可否を段階的に判定する要件へ更新する。

## Impact

- `byoc_runtime/app.py` の FastAPI ルーティングと、対応する HTTP テストが影響を受ける。
- `scripts/query_job.py` の証跡収集・判定ロジックと README のクラウド検証手順・結果記録が影響を受ける。
- Agent Platform の長時間実行クエリジョブ、Cloud Logging、Cloud Storage を利用するライブ検証が必要となり、Google Cloud の利用料金が発生し得る。
- 公開 API の削除や互換性を壊す変更はない。
