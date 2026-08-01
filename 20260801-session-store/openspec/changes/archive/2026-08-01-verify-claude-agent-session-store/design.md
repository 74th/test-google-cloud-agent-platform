## Context

提案の背景は [proposal.md](proposal.md) を参照する。Google Cloud Agent Platform の Sessions API は、Agent Engine に紐づくセッションを作成し、会話イベントを追加・一覧取得できる。一方、Claude Agent SDK の `resume` は Claude セッション ID に対応するトランスクリプトをローカルファイルシステムから読み込む方式であり、Session Store を SDK のネイティブ永続化バックエンドとして差し替える公開インターフェースは確認できない。

したがって本検証では、「Session Store が Claude のローカルトランスクリプトを代替できるか」ではなく、次の二点を分離して確認する。

1. Claude の会話ターンとセッション ID を Session Store に保存し、別プロセスから取得できるか。
2. 取得した Claude セッション ID と、同じローカル環境に残るトランスクリプトを使って Claude Agent SDK の会話を再開できるか。

参照する公式仕様:

- Google Cloud: Agent Engine をコード配備せず作成し、Sessions API へ直接イベントを追加・一覧取得できる。
  - https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/sessions/manage-sessions-api
- Claude Agent SDK: `ResultMessage.session_id` を保存し、次のプロセスで `ClaudeAgentOptions(resume=...)` に渡す。トランスクリプトはローカルファイルシステムに保存される。
  - https://platform.claude.com/cookbook/claude-agent-sdk-04-migrating-from-openai-agents-sdk

## Goals / Non-Goals

**Goals:**

- 初回実行と再開実行を明確に別プロセスとして実行できる CLI サンプルにする。
- Google Cloud 側の永続化成功と Claude SDK 側の再開成功を別々に観測できるようにする。
- 会話内容、Claude セッション ID、および対応関係を、バージョン付きの保存形式で Session Store に記録する。
- 手作業でも自動テストでも判定できる決定的な検証プロンプトを用いる。

**Non-Goals:**

- Claude Agent SDK のローカルトランスクリプトや作業ディレクトリをクラウドへ同期すること。
- Session Store のイベントから Claude 独自トランスクリプトを再生成すること。
- Agent Engine 上で Claude Agent SDK 自体をホストまたは実行すること。
- 本番向けの同時更新制御、長期保持、データ分類、コスト最適化を設計すること。

## Decisions

### Python の二段階 CLI とする

サンプルは `start` と `resume` の二つのサブコマンドを持つ Python CLI とする。`start` は Session Store セッションを作成して初回会話を保存し、`resume` は完全なセッションリソース名を入力としてクラウドからイベントを取得して会話を継続する。利用者は `start` 終了後に別のシェルプロセスで `resume` を実行する。

単一プロセス内でクライアントを作り直す案は、OS プロセス終了後の永続性を実証できないため採用しない。二つの独立したスクリプトに分ける案は初期化と検証ロジックが重複するため採用しない。

### Session Store には移植可能なイベントと Claude セッション ID を保存する

各会話ターンを Session Store のイベントとして保存し、`author`、`invocation_id`、UTC タイムスタンプ、ロール付きテキストを記録する。加えて、アダプター管理イベントとして次の論理情報を JSON テキストで保存する。

- `schema_version`
- `claude_session_id`
- 検証用 nonce
- サンプルのバージョン

Session Store のイベント API が公式に提供する Content 形式だけを用いることで、Claude SDK 内部の非公開トランスクリプト形式への依存を避ける。Claude セッション ID のみをローカルファイルへ保存する案は、クラウドから取得できたことを証明できないため採用しない。Claude の生の内部メッセージをそのまま保存する案は、形式の安定性と秘密情報混入のリスクがあるため採用しない。

### Claude のネイティブ `resume` を互換性検証に使う

`start` は Claude Agent SDK の最終結果から `session_id` を取得する。`resume` は Session Store の管理イベントからその ID を復元し、`ClaudeAgentOptions(resume=claude_session_id)` を指定した新しい SDK クライアントを起動する。

会話履歴を通常プロンプトへ連結して新規セッションを作る案は、表面的には以前の内容へ応答できても Claude の同一セッション再開を検証できないため採用しない。なお、ネイティブ `resume` はローカルトランスクリプトに依存するため、Session Store 単独の永続化とは呼ばない。

### nonce の再現で会話継続を判定する

`start` はランダムな nonce を含む指示を Claude に渡し、Claude の応答と nonce を Session Store に保存する。`resume` は nonce 自体をプロンプトに再掲せず、前回記憶した値を答えるよう依頼する。取得した値との完全一致により、一般的な自然言語応答の目視判定を避ける。

Claude 応答の文意を人が判断する案は再現性が低いため採用しない。モデル出力の揺らぎに備え、応答形式を固定し、比較前に前後空白だけを正規化する。

### 段階別の JSON 結果を出力する

実行結果は `session_created`、`events_appended`、`events_retrieved`、`claude_resumed`、`nonce_matched` と、エラーの段階・種別を JSON で出力する。総合成功は全項目が真の場合だけとする。これにより、Session Store の互換性と Claude ローカル永続化の寄与を混同しない。

## Risks / Trade-offs

- [Claude のローカルトランスクリプトが失われると、Session Store に会話イベントが残っていてもネイティブ再開できない] → 段階別結果で明示し、今回の成功条件を「同一ローカル環境」に限定する。
- [Session Store と Claude の書き込みはトランザクションではなく、Claude 応答後にクラウド保存だけ失敗し得る] → 各イベントに安定した invocation ID を付け、部分保存を検出して成功扱いしない。
- [Session Store と Claude Agent SDK は更新される外部 API である] → 依存バージョンを固定し、README に検証日とバージョンを記録する。
- [会話イベントに機密情報が保存される] → サンプルは生成した nonce と固定文だけを用い、認証情報や環境変数値をイベントへ含めない。
- [モデル応答の揺らぎで偽陰性が起こる] → ツール利用を不要にし、短い固定形式で nonce のみを返す確認プロンプトにする。
- [Agent Engine リソースの準備に課金や IAM 設定が必要になる] → 既存リソースを指定可能にし、新規作成手順と削除手順を文書化する。

## Migration Plan

1. 検証用依存関係と環境変数テンプレートを追加する。
2. 必要に応じてコードを配備しない空の Agent Engine リソースを検証用に作成する。
3. `start` を実行し、表示された Session Store セッション名を控えてプロセス終了を確認する。
4. 別プロセスで `resume` を実行し、段階別 JSON 結果を保存する。
5. README に実測した SDK バージョン、結果、制約を記録する。
6. 検証環境を破棄する場合は作成したセッションと Agent Engine リソースだけを明示的に削除する。実装はサンプル追加のみのため、ロールバックは追加ファイルの削除で行う。

