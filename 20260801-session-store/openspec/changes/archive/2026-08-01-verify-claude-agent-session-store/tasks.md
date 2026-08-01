## 1. 検証プロジェクトの準備

- [x] 1.1 Python プロジェクトを初期化し、Claude Agent SDK と Google Cloud Agent Platform SDK の検証済みバージョンを固定する
- [x] 1.2 必須環境変数を検証する設定モジュールと、秘密値を含めない環境変数テンプレートを追加する
- [x] 1.3 CLI の `start` と `resume` サブコマンド、および段階別 JSON 結果の共通データモデルを定義する

## 2. Session Store アダプター

- [x] 2.1 指定された Agent Engine に検証ユーザーの Session Store セッションを作成し、完全なリソース名を返す処理を実装する
- [x] 2.2 ユーザー入力、Claude 応答、バージョン付き管理情報をロール・invocation ID・UTC タイムスタンプ付きイベントとして追加する処理を実装する
- [x] 2.3 セッションと全イベントを取得し、Claude セッション ID、nonce、初回会話の存在とスキーマバージョンを検証する処理を実装する
- [x] 2.4 未存在セッション、部分保存、API エラーを段階別に分類し、新規セッションを暗黙作成せず報告する処理を実装する

## 3. Claude Agent SDK の初回実行と再開

- [x] 3.1 `start` で nonce を生成し、固定形式の初回プロンプトを Claude Agent SDK へ送信して応答と `ResultMessage.session_id` を取得する
- [x] 3.2 初回会話と管理情報を Session Store へ保存し、別プロセスへ渡す Session Store セッション名と段階別結果を出力する
- [x] 3.3 `resume` で Session Store から取得した Claude セッション ID を `ClaudeAgentOptions(resume=...)` に渡し、nonce を再掲しない確認プロンプトを送信する
- [x] 3.4 Claude の回答と保存済み nonce を比較し、クラウド取得成功と Claude ネイティブ再開成功を分離した総合判定を JSON で出力する
- [x] 3.5 Claude のローカルトランスクリプトがない場合に、Session Store の取得成功を保持したまま再開失敗として報告する

## 4. 自動テスト

- [x] 4.1 Session Store と Claude SDK のテストダブルを用い、セッション作成、イベントの保存順序、管理情報の復元を単体テストする
- [x] 4.2 必須設定不足、未存在セッション、不完全イベント、保存 API 失敗、ローカルトランスクリプト欠落のエラー判定をテストする
- [x] 4.3 独立した二つの CLI プロセスを模した結合テストで、`start` の出力だけを入力に `resume` が nonce 一致まで到達することを検証する
- [x] 4.4 JSON 出力の必須フィールドと、全段階成功時だけ総合成功になることをテストする

## 5. 実環境検証と文書化

- [x] 5.1 Google Cloud と Claude の認証、空の Agent Engine の準備、環境変数、`start`、プロセス終了、`resume` の実行手順を README に記載する
- [x] 5.2 同一ローカル環境で実環境の二段階検証を実行し、SDK バージョン、実行日、段階別結果を README に記録する
- [x] 5.3 Session Store は Claude のローカルトランスクリプトを代替しないこと、ワークスペース永続化が対象外であること、成功判定の適用範囲を README に明記する
- [x] 5.4 検証用セッションと Agent Engine リソースの明示的な削除手順、および課金・IAM・機密情報に関する注意事項を README に記載する
