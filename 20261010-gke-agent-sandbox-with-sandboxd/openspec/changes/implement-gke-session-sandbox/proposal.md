# Proposal

## Why

SlackBot / Claude Agent SDKから使うセッション専用workspaceについて、READMEの仕様を実装可能な契約と検証手順へ落とし込む必要がある。実GKEでライフサイクル・command追跡・永続性・ネットワーク分離を検証できるPythonライブラリと専用Terraform環境を作る。

## What Changes

- `gke_session_sandbox` asyncライブラリ、YAMLテンプレート、image指定、作成時env、core Sandbox v1beta1の管理を追加する。
- Pod内CommandTrackerを実装し、実行中 / 終了 / 不明、process group、切断後の実行、保存出力とcommand IDによる再照会を提供する。
- 60秒ごとの監視デーモン、最終command終了から300秒で停止、停止完了から604800秒で削除するpolicyを実装する。
- session ID・実行状態・確認時刻等をKubernetes metadataへ保存し、ConfigMap / Leaseによる永続状態・排他・クラッシュ回復を追加する。
- 専用PVC、readOnly共有PVC、FQDN / 通常NetworkPolicy、workspace消失イベントとackを提供する。
- `./terraform`へ専用GKE Standard、Dataplane V2、FQDN policy、gVisor node poolと関連インフラの定義を追加する。物理名は`research-gke-agent-sandbox-with-sandboxd`系に統一し、他の検証のstate / リソースから分離する。
- クラスタ非接続のunit test、実GKE integration / E2E、cluster内runner、診断・cleanupと互換性記録を追加する。

## Capabilities

### New Capabilities

- `research-gke-infrastructure`: Terraformによる専用検証環境、物理命名・state分離、環境出力と削除責務。
- `session-workspaces`: セッションごとのSandbox、テンプレート / env、専用・共有PVC、接続とネットワーク分離。
- `tracked-commands`: command追跡、process操作、ファイルAPI、結果・出力保持と障害時の契約。
- `sandbox-lifecycle`: 毎分監視、idle停止、再開・期限削除、Kubernetes metadata、消失通知と回復。
- `gke-validation`: unit / 実クラスタ検証、互換性spike、run分離・診断・cleanupと受け入れ記録。

### Modified Capabilities

なし。既存のmain spec・実装はない。

## Impact

新規対象は`src/`、`tests/`、`templates/`、`runtime/`、`k8s/`、`scripts/`、`terraform/`、Python packagingとREADME。Kubernetes / Google Cloud API、Agent Sandbox controller / CRD、sandboxd、CSIとネットワーク機能に依存する。

`../common`や隣接検証のTerraform stateとリソースは変更しない。SlackBot本体、常駐Agent runner、WarmPool、メモリsnapshot、SQL Repositoryは対象外。Cloudのproject / location / CIDRは実行時に指定し、planと接続先確認後に実環境を検証する。
