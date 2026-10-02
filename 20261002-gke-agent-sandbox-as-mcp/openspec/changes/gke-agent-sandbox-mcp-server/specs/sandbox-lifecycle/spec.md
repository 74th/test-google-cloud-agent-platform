# Spec Delta

## Purpose

使っていない Sandbox を Suspend して計算資源を解放しつつワークスペースを残し、長期間使われないワークスペースは自動で削除する。実行中のプロセスは途中で止めない。

## ADDED Requirements

### Requirement: 最終 activity からの sliding idle timeout で Suspend する
MCP Server は、Sandbox で実行中のプロセスがなくなり、かつ最後のツール呼び出しが完了してから `SANDBOX_IDLE_TIMEOUT_SECONDS`（既定 1800 秒）が経過したら、Sandbox を Suspend しなければならない（SHALL）。Suspend では Pod を削除し、PVC を保持しなければならない（SHALL）。Sandbox 作成時刻からの固定 TTL にしてはならない（MUST NOT）。idle の判定に使う最終 activity は、MCP Server の再起動で失われない場所（Kubernetes リソース）に保存しなければならない（SHALL）。

#### Scenario: idle timeout 経過で Suspend される
- **WHEN** `exec_command` でコマンドを実行して完了したあと、idle timeout を超えてどのツールも呼び出さない
- **THEN** Sandbox が Suspended になり、Pod は削除され、PVC は残っている

#### Scenario: 利用のたびに idle timeout が延長される
- **WHEN** idle timeout より短い間隔で `exec_command`、`apply_patch`、`view_image` などのツールを繰り返し呼び出す
- **THEN** 利用の合計時間が idle timeout を超えても Sandbox は Suspend されない

### Requirement: 実行中のプロセスがある間は Suspend しない
MCP Server は Sandbox ごとに、`exec_command` で起動してまだ終了していないプロセスの数と、処理中のツール呼び出しの数を管理し、どちらかが 1 つ以上ある間は Suspend してはならない（MUST NOT）。MCP クライアントが `write_stdin` でポーリングしていなくても、プロセスが実行中であれば Suspend してはならない（MUST NOT）。idle timeout の起点は、最後のプロセスの終了時刻と最後のツール呼び出しの完了時刻のうち遅いほうでなければならない（SHALL）。プロセスの実行中は activity を定期的に更新しなければならない（SHALL）。

#### Scenario: idle timeout より長いコマンドが止まらない
- **WHEN** idle timeout より長い `sleep` を `exec_command` で起動し、返った `process_id` を idle timeout より長い間隔をあけて `write_stdin` でポーリングする
- **THEN** プロセスは途中で Suspend されずに完了し、`write_stdin` で `exit_code` 0 を受け取れる

#### Scenario: 長いコマンドの完了後に Suspend される
- **WHEN** idle timeout より長いプロセスが終了し、その後 idle timeout が経過する
- **THEN** Sandbox が Suspended になる

### Requirement: Resume しても /workspace のファイルが残る
Suspend されたセッションを Resume したとき、同じ PVC が `/workspace` にマウントされ、Suspend 前に書いたファイルを読めなければならない（SHALL）。プロセスやメモリの状態は Resume 後に失われてよい。

#### Scenario: Suspend をはさんでファイルが残る
- **WHEN** `exec_command` で `echo hello > /workspace/test.txt` を実行し、Suspend されて Pod が削除され PVC が残っていることを確認したあと、`exec_command` で `cat /workspace/test.txt` を実行する
- **THEN** Sandbox が Resume され、`output` が `hello` になる

### Requirement: retention 経過後にワークスペースを GC する
MCP Server は `SANDBOX_GC_INTERVAL_SECONDS` ごとに定期タスクを実行し、最終 activity から `SANDBOX_WORKSPACE_RETENTION_SECONDS`（既定 604800 秒）が経過したセッションの Sandbox、SandboxClaim、PVC を削除しなければならない（SHALL）。判定には Kubernetes リソースに保存した最終 activity を使わなければならない（SHALL）。実行中のプロセスがあるセッションは削除してはならない（MUST NOT）。削除後に PVC が残ってはならない（MUST NOT）。

#### Scenario: retention 経過で削除される
- **WHEN** retention を短く設定し、最終 activity から retention が経過する
- **THEN** そのセッションの SandboxClaim、Sandbox、PVC がすべて削除される

#### Scenario: 実行中のセッションは GC されない
- **WHEN** retention を超えて実行中のプロセスがあるセッションに GC が実行される
- **THEN** そのセッションは削除されない

### Requirement: MCP Server が停止していてもリソースが放置されない
MCP Server が停止していて idle 管理や GC が動かない場合でも、Sandbox が無期限に残らないよう、Kubernetes 側の期限（`shutdownTime` など）を安全網として設定しなければならない（SHALL）。安全網の期限は通常の idle Suspend や GC より後でなければならない（SHALL）。採用した方式と理由は README に記録しなければならない（SHALL）。

#### Scenario: 安全網の期限は通常の運用を妨げない
- **WHEN** MCP Server が動いている状態でセッションを使い続ける
- **THEN** 安全網の期限によって Sandbox が削除されることはない
