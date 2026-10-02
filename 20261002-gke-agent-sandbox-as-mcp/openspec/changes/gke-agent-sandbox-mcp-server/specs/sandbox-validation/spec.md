# Spec Delta

## Purpose

実クラスタ上の Agent Sandbox の仕様を確認し、MCP Server の振る舞いを E2E で検証して、結果と計測値を証跡と README に残す。

## ADDED Requirements

### Requirement: 実クラスタの仕様を記録する
実装の前に、GKE、Agent Sandbox コントローラ、Agent Sandbox API、`k8s-agent-sandbox`、`mcp` Python SDK のバージョン、各 CRD のバージョン、既定の StorageClass を記録しなければならない（SHALL）。あわせて `operatingMode`、`shutdownTime` / `shutdownPolicy`、`volumeClaimTemplates`、SandboxClaim の `env`、SandboxClaim と Sandbox の所有関係、PVC の ownerReference、Suspend 時と削除時の PVC の挙動を確認して記録しなければならない（SHALL）。ドキュメントと実クラスタの CRD が異なる場合は、実クラスタを優先し、差異を記録しなければならない（SHALL）。

#### Scenario: 仕様確認の証跡がある
- **WHEN** オペレータが `evidence/` を確認する
- **THEN** 上記のバージョンと CRD の仕様、PVC の挙動が記録されたファイルがある

### Requirement: MCP Server を書く前に手動で検証する
MCP Server を実装する前に、kubectl または小さなスクリプトで、Suspend / Resume による Pod の削除と PVC の保持、Resume 後のファイルの保持、claim の `env` による `USER_EMAIL` の注入、`shutdownTime` の挙動を検証し、記録しなければならない（SHALL）。`shutdownTime` を更新し続ける方式と、MCP Server が `operatingMode` を変更する方式を比較し、採用方式と理由を README に記録しなければならない（SHALL）。

#### Scenario: 手動検証の結果から方式が決まる
- **WHEN** 手動検証が完了する
- **THEN** `evidence/` に結果があり、idle Suspend の採用方式と理由が README に書かれている

### Requirement: 単体テストで主要なロジックを確認する
Kubernetes API をモックした pytest で、binding 不一致のエラー、claim 名の決定性、idle 判定（実行中のプロセスがある間は Suspend しない）、GC 判定、プロセス管理（yield、`process_id` の払い出しとセッションの照合、出力の切り詰め）、`apply_patch` のパッチ解析と適用（失敗時に部分適用しない）、ログに生メールアドレスが出ないことを確認しなければならない（SHALL）。

#### Scenario: 単体テストが通る
- **WHEN** オペレータが `uv run pytest` を実行する
- **THEN** 上記の観点を含むテストがすべて成功する

### Requirement: 検証では LLM を使わない
検証の対象は MCP Server であり、単体テストと E2E 検証は、決まった引数でツールと REST API を直接呼び出すスクリプトで行わなければならない（SHALL）。判定に LLM の応答を使ってはならない（MUST NOT）。

#### Scenario: 検証スクリプトは LLM を呼び出さない
- **WHEN** オペレータが E2E 検証スクリプトを実行する
- **THEN** スクリプトは MCP Server と Kubernetes API だけに接続し、LLM の API には接続しない

### Requirement: E2E 検証を実クラスタで行う
クラスタにデプロイした MCP Server に対して、`kubectl port-forward` 経由で MCP クライアントのスクリプトから次の 13 項目を確認し、結果を `evidence/` に保存しなければならない（SHALL）。(1) 新規セッションで `exec_command` を呼ぶと Sandbox と PVC が作られる、(2) `echo $USER_EMAIL` が入力したメールアドレスになる、(3) 別の `user_email` ではエラーになる、(4) idle timeout で Suspend され Pod が消え PVC が残る、(5) Resume 後に `/workspace` のファイルが残る、(6) idle timeout より長いコマンドが `exec_command` と `write_stdin` によるポーリングの間に Suspend されない、(7) MCP Server を再起動しても既存セッションに再接続できる、(8) `delete_workspace` 後は新規ワークスペースになる、(9) retention 経過で GC される、(10) ログ、REST API の応答、label / annotation に生メールアドレスが含まれない、(11) `apply_patch` でファイルの追加・更新・削除ができ、不正なパッチでは何も変わらない、(12) `view_image` で Sandbox 内の画像を取得できる、(13) REST API で Running / Suspended などの状態を取得できる。検証時は idle timeout と retention を短くしてよい。

#### Scenario: E2E の全項目が記録される
- **WHEN** オペレータが E2E 検証スクリプトを実行する
- **THEN** 13 項目それぞれの判定結果が `evidence/` に保存され、すべて成功している

### Requirement: 起動と Resume の時間を計測する
WarmPool ありとなしでの Sandbox の起動時間、`env` を指定した claim が WarmPool の Pod を使えるかどうか、Resume にかかる時間を計測し、README に記録しなければならない（SHALL）。

#### Scenario: 計測結果が README にある
- **WHEN** オペレータが README を確認する
- **THEN** cold start の時間、WarmPool 利用の可否と時間、Resume の時間が記載されている

### Requirement: README に結果と手順をまとめる
README には、構成図と各コンポーネントの責務、MCP ツールと Codex のツールの対応と差異、バージョンと CRD 仕様の確認結果、構築・デプロイ・削除の手順、環境変数の一覧、idle Suspend 方式の比較と採用理由、計測結果、Resume 後および MCP Server の再起動後はプロセスとメモリの状態（実行中の `process_id` を含む）が失われ `/workspace` のファイルだけが残るという前提、production へ向けた残課題（複数 replica 化、認証、NetworkPolicy、監視など）を記載しなければならない（SHALL）。

#### Scenario: README に必要な項目がそろっている
- **WHEN** オペレータが README を確認する
- **THEN** 上記の項目がすべて記載されている
