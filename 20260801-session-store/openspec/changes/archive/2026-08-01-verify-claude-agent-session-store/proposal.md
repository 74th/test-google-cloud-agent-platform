## Why

Google Cloud Agent Platform の Session Store を Claude Agent SDK から利用し、SDK プロセスを終了・再起動しても以前のセッション情報を復元できるかを、再現可能なローカル検証で明らかにする必要がある。

## What Changes

- Claude Agent SDK と Google Cloud Agent Platform Session Store を接続する最小構成のローカルサンプルを追加する。
- 初回実行で会話のセッション情報を保存し、別プロセスでの再実行時に同じセッションを取得して会話を継続する検証シナリオを追加する。
- 保存・取得・再開の成否を確認できるログまたは検証結果を出力する。
- 必要な認証情報、環境変数、実行手順、確認方法、既知の制約を文書化する。
- Claude Agent SDK のワークスペース自体の永続化は今回の検証対象外とする。

## Capabilities

### New Capabilities

- `claude-agent-session-persistence`: Claude Agent SDK のプロセスをまたいで Google Cloud Agent Platform Session Store にセッション情報を保存・取得し、会話コンテキストを再利用できることを検証する機能。

### Modified Capabilities

なし。

## Impact

- ローカル実行用の Claude Agent SDK サンプルコードと依存関係を追加する。
- Google Cloud プロジェクト、リージョン、Session Store の識別情報、および認証設定が必要になる。
- Claude API の認証設定が必要になる。
- Google Cloud Agent Platform Session Store および Claude Agent SDK の公開 API に依存する。
- 本変更は検証用サンプルに限定し、本番運用向けの可用性、排他制御、暗号化、ワークスペース永続化は扱わない。
