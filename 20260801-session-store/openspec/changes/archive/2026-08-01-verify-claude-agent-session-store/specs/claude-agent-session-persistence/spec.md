## Purpose

Claude Agent SDK のローカルプロセスを終了して起動し直した場合に、Google Cloud Agent Platform Session Store へ保存した会話情報を取得し、同一セッションの会話を継続できるかを再現可能な手順で判定する。

## ADDED Requirements

### Requirement: 検証に必要な設定を明示する
検証サンプルは、Claude と Google Cloud の認証情報、Google Cloud プロジェクト、リージョン、Agent Engine リソース、および検証ユーザーを外部設定として受け取らなければならない（SHALL）。また、秘密情報をソースコードまたは Session Store の会話イベントへ保存してはならない（MUST NOT）。

#### Scenario: 必須設定が揃っている
- **WHEN** 利用者が必要な認証と設定値を与えて検証を開始する
- **THEN** サンプルは対象の Claude API と Session Store に接続して初回実行を開始する

#### Scenario: 必須設定が不足している
- **WHEN** 必須の認証または設定値が不足した状態で検証を開始する
- **THEN** サンプルは不足項目を特定できるエラーを表示し、会話処理を開始せずに失敗する

### Requirement: 初回会話を Session Store に保存する
サンプルは、初回プロセスで Session Store のセッションを作成し、利用者の入力、Claude の応答、および Claude Agent SDK が発行したセッション識別子を、後続プロセスが取得可能な形式で保存しなければならない（SHALL）。

#### Scenario: 初回会話の保存に成功する
- **WHEN** 利用者が初回実行用のプロンプトを送信し Claude が応答する
- **THEN** サンプルは会話ターンと Claude のセッション識別子を Session Store に保存し、再開時に指定する Session Store のセッション識別子を表示する

#### Scenario: Session Store への保存に失敗する
- **WHEN** Claude の応答後に Session Store へのイベント保存が失敗する
- **THEN** サンプルは検証を成功扱いせず、保存段階と原因を識別できるエラーを表示する

### Requirement: 別プロセスから保存済みセッションを取得する
サンプルは、初回プロセスとは別に起動した後続プロセスで、指定された Session Store のセッションおよびイベントをクラウドから取得しなければならない（SHALL）。取得結果には、少なくとも初回の利用者入力、Claude の応答、および Claude のセッション識別子が含まれなければならない（MUST）。

#### Scenario: 保存済みセッションを取得できる
- **WHEN** 初回プロセスを終了した後、利用者が表示済みの Session Store セッション識別子を指定して後続プロセスを起動する
- **THEN** 後続プロセスは Session Store から初回会話と Claude のセッション識別子を取得し、取得した内容を検証する

#### Scenario: セッションが存在しない
- **WHEN** 利用者が存在しない、削除済み、または対象 Agent Engine に属さないセッション識別子を指定する
- **THEN** サンプルは新規セッションを暗黙に作成せず、対象セッションを取得できないことを明示して失敗する

#### Scenario: 保存イベントが不完全である
- **WHEN** 対象セッションは存在するが再開に必要な会話イベントまたは Claude のセッション識別子が欠けている
- **THEN** サンプルは破損または不完全な保存データとして失敗し、不足要素を表示する

### Requirement: Claude Agent SDK の会話を再開する
後続プロセスは、Session Store から取得した Claude のセッション識別子を用いて Claude Agent SDK を再開し、初回会話の情報を必要とする確認プロンプトへ応答させなければならない（SHALL）。この検証は Claude Agent SDK のローカル会話トランスクリプトが同じ実行環境に残っていることを前提としなければならない（MUST）。

#### Scenario: プロセス再起動後に会話を継続できる
- **WHEN** 初回プロセスが終了済みで、後続プロセスが保存済み識別子を使って確認プロンプトを送信する
- **THEN** Claude の応答は初回会話で与えた検証用情報を参照し、サンプルは同じ Claude セッションを再開できたことを確認する

#### Scenario: Claude のローカルトランスクリプトがない
- **WHEN** Session Store のイベントは取得できるが Claude Agent SDK が必要とするローカルトランスクリプトが存在しない
- **THEN** サンプルは「Session Store の取得成功」と「Claude ネイティブ再開の失敗」を区別して報告する

### Requirement: 互換性の判定根拠を出力する
サンプルは、Session Store の作成、イベント保存、別プロセスでの取得、および Claude のネイティブ再開を個別に判定し、総合結果と制約を機械可読または一貫した形式で出力しなければならない（SHALL）。

#### Scenario: 全検証段階が成功する
- **WHEN** セッション作成、保存、取得、および Claude の再開がすべて成功する
- **THEN** サンプルは「同一ローカル実行環境のプロセス再起動」という条件下で利用可能と判定する

#### Scenario: 一部の検証段階だけ成功する
- **WHEN** Session Store の保存と取得は成功するが Claude の再開に失敗する、または別の段階が失敗する
- **THEN** サンプルは利用可能と断定せず、各段階の成否と失敗理由を分けて出力する

