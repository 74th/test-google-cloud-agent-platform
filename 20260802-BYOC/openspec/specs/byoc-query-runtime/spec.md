# byoc-query-runtime Specification

## Purpose

Gemini Enterprise Agent Platform のカスタムコンテナで4種類のクエリ操作を意図的な遅延付きで受け付け、応答内容と処理ライフサイクルを外部から観測可能にする。

## Requirements

### Requirement: 非ストリーミングクエリ
ランタイムは `query` および `async_query` 操作を受け付けなければならない（SHALL）。各操作はリクエストの処理開始から10秒を目安に待機した後、`OK` を含む単一の最終応答を返さなければならない（SHALL）。

#### Scenario: query の成功
- **WHEN** 有効な入力を持つ `query` リクエストを受信する
- **THEN** ランタイムは処理開始から約10秒後に `OK` を含む単一の応答を返す

#### Scenario: async_query の成功
- **WHEN** 有効な入力を持つ `async_query` リクエストを受信する
- **THEN** ランタイムはイベントループをブロックせず、処理開始から約10秒後に `OK` を含む単一の応答を返す

### Requirement: ストリーミングクエリ
ランタイムは `stream_query` および `async_stream_query` 操作を受け付けなければならない（SHALL）。各操作は処理開始から約5秒後に `Streaming OK` を含むチャンクを、約10秒後に `OK` を含む最終チャンクを、この順序で返さなければならない（SHALL）。

#### Scenario: stream_query の成功
- **WHEN** 有効な入力を持つ `stream_query` リクエストを受信する
- **THEN** ランタイムは約5秒後の `Streaming OK` と約10秒後の `OK` を順番にストリーミングする

#### Scenario: async_stream_query の成功
- **WHEN** 有効な入力を持つ `async_stream_query` リクエストを受信する
- **THEN** ランタイムはイベントループをブロックせず、約5秒後の `Streaming OK` と約10秒後の `OK` を順番にストリーミングする

### Requirement: Agent Platform ランタイム互換性
コンテナは Agent Platform が要求するポートと HTTP パスで待ち受け、操作名と入力を含むランタイム契約のリクエストを解釈しなければならない（MUST）。ストリーミング応答は Agent Platform がチャンク列として転送できる形式でなければならない（MUST）。

#### Scenario: コンテナ起動
- **WHEN** Agent Platform またはローカルのコンテナランタイムがアプリケーションを起動する
- **THEN** アプリケーションは `0.0.0.0:8080` でリクエストを受け付ける

#### Scenario: 未対応操作
- **WHEN** サポート対象外の操作名を持つリクエストを受信する
- **THEN** ランタイムは成功応答に偽装せず、クライアントが判別できるエラーを返す

### Requirement: リクエストライフサイクルログ
ランタイムは全 HTTP リクエストについて受信を直ちに標準出力へ記録し、クエリ処理について開始と終了を記録しなければならない（SHALL）。各ログは同一処理を関連付けられる識別子、操作名、時刻、イベント種別を含まなければならない（MUST）。入力本文に機密情報が含まれ得るため、既定では本文全体を記録してはならない（MUST NOT）。

#### Scenario: 正常処理の追跡
- **WHEN** サポート対象のクエリ操作を受信して正常終了する
- **THEN** 同一の識別子で受信、処理開始、処理終了のログを時系列に確認できる

#### Scenario: 処理失敗の追跡
- **WHEN** リクエスト処理中にエラーが発生する
- **THEN** 同一の識別子で処理失敗とエラー種別を確認でき、機密性のある入力本文や認証情報は出力されない
