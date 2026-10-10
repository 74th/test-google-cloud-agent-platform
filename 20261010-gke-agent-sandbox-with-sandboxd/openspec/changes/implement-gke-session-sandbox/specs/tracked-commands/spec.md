# Spec Delta

## Purpose

利用側がcommandを送るだけで実行状態と結果を追跡できるようにし、切断・再起動・大量出力・子プロセスの残存による誤ったidle判定を防ぐ。

## ADDED Requirements

### Requirement: Automatic process tracking
commandは SHALL 一意なIDで自動追跡し、argv実行、stream、stdin / EOF、signal、PTYを提供する。利用側にactivity管理やheartbeatを要求してはならない。

#### Scenario: Run and interactive execution
- **WHEN** buffered / streaming command、stdin、signal、PTY変更を要求する
- **THEN** stdout / stderr / exit codeを取得し、長時間無出力でも実行中として扱う

#### Scenario: Nonzero exit
- **WHEN** commandが非ゼロexitで終了する
- **THEN** 通常は結果を返し、check指定時だけcommand失敗例外にする

### Requirement: Unknown outcomes and reconnection
実行状態は SHALL running / finished / unknownを区別する。client切断だけで実行数を減らしてはならず、IDで状態と保存出力を再取得可能にする。

#### Scenario: Disconnected caller
- **WHEN** clientが切断またはBotが再起動する
- **THEN** Pod側が追跡と出力保存を継続し、既知IDで結果を照会できる

#### Scenario: Restarted tracker
- **WHEN** tracker再起動で終了を確定できない
- **THEN** unknownを返す。別IDで自動再実行せず、終了済みと誤認しない

### Requirement: Process group completion
終了判定は SHALL 受付commandのprocess group全体を対象とする。cancel / timeout時はSIGTERM、5秒後SIGKILLを試み、終了確認後に実行数を減らす。detached実行はサポートしない。

#### Scenario: Remaining child
- **WHEN** shellだけ終了して子processが残る
- **THEN** 残存groupを停止・確認するまでfinishedとせず、確認不能ならunknownにする

### Requirement: Independent output consumption
trackerは SHALL subscriberが停止・切断してもsandboxd streamを消費する。出力を有限queueと永続保存で管理し、command IDとcursorで保持範囲を再取得可能にする。

#### Scenario: Slow reader
- **WHEN** subscriberが読まない・遅い・切断する
- **THEN** commandの出力消費は継続し、メモリが増え続けず、cursorで保存出力を読める

### Requirement: Output limits and expiration
出力保存は SHALL command合計64MiB / session合計256MiBを既定上限とし、設定可能にする。終了から7日またはworkspace削除で出力を失効させ、欠落を明示する。

#### Scenario: Capacity failure
- **WHEN** 出力上限またはPVC書込み失敗が発生する
- **THEN** 停止を試み、終了確認までstreamを消費し、上限・保存エラーと欠落を返す。正常結果として切り詰めない

#### Scenario: Buffer and retention
- **WHEN** 各8MiBのbuffered応答上限または出力保持期限を超える
- **THEN** 対応するエラーを返す。保存済み範囲は期限内なら取得でき、出力削除でidle起点は消えない
