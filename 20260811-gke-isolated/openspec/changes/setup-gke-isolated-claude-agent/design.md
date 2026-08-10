## Context

現状は Terraform のバージョン指定だけがあり、クラスタ、コンテナ、Kubernetes リソース、検証手順は未実装である。要求の詳細は [proposal.md](proposal.md) と `isolated-claude-agent-runtime` の差分仕様を参照する。

この構成には、次の制約がある。

- `us-central1-a` はリージョンではなくゾーンなので、要望する「その場所だけ・1 ノード」はゾーンクラスタとして表現する。
- Kubernetes 標準の `NetworkPolicy` は IP/CIDR を扱うが FQDN を扱えない。IP が変化する SaaS/API をホスト許可リストにするには、Dataplane V2 の FQDN Network Policy を併用する必要がある。
- Claude Agent SDK は内部で Claude Code CLI を起動し、Vertex AI 認証、モデル API、および URL 取得の複数の外向き通信を行う。
- BigQuery 公開データの読み取りにも、利用者プロジェクトでのジョブ作成と BigQuery API への到達性が必要である。

## Goals / Non-Goals

**Goals:**

- Terraform とマニフェストを分離し、インフラ、ワークロード、外向き通信制御を独立して再適用できるようにする。
- ポリシー適用前に機能基準を確立してから、同一 Pod で許可通信の継続と未許可通信の遮断を証明する。
- 秘密鍵ファイルを使わず、Kubernetes Service Account を Google Cloud IAM の主体へ結び付ける。
- 実行者がどの段階で何を確認しているか分かり、失敗を終了コードで検出できるようにする。

**Non-Goals:**

- 本番向けの高可用性、オートスケーリング、プライベートクラスタ、NAT、組織ポリシー対応。
- 複数テナントの隔離、エージェントのファイル・プロセス権限制御、入力内容の安全性評価。
- GitHub の全サービスや任意の Claude Code ツールに必要なドメインを包括的に許可すること。
- Terraform の destroy を自動実行すること。

## Decisions

### 1. ゾーンクラスタと専用ノードプールを Terraform で作る

Google、Google Beta、Kubernetes の各 provider を使い、プロジェクト ID を入力、ゾーンを `us-central1-a` とする。既存の auto-mode VPC `default` と `us-central1` の `default` サブネットをデータ参照し、`test-isolated` クラスタをそのサブネットへ配置する。初期ノードプールを削除して、`e2-standard-2`、初期・最小・最大ノード数 1 の専用ノードプールを作る。クラスタでは Dataplane V2、Workload Identity、FQDN Network Policy を明示的に有効にする。

単一ノードの要件を曖昧にする regional cluster は採用しない。新規 VPC は不要であり、利用者指定の `default` サブネットを優先する。

Terraform は必要な Service Usage API、Artifact Registry リポジトリ、Google Service Account（GSA）、IAM も所有する。これにより、コンテナイメージ名や IAM 主体を output として後段スクリプトへ受け渡せる。

### 2. Workload Identity Federation for GKE で KSA と GSA を関連付ける

`test` Kubernetes Service Account（KSA）を専用 GSA に annotation で関連付け、GSA に `roles/aiplatform.user` と `roles/bigquery.jobUser` をプロジェクト単位で付与する。GSA には KSA 主体の `roles/iam.workloadIdentityUser` binding を付与する。ノード OAuth scope は `cloud-platform` とするが、実際の認可範囲は IAM で絞る。

サービスアカウント鍵の Secret 配布やユーザ ADC の Pod へのマウントは、長期資格情報が残るため採用しない。公開 BigQuery データセットは公開読み取り権限を利用し、利用者プロジェクト側にはジョブ実行権限だけを与える。

### 3. Agent SDK と検証コードを 1 つの常駐コンテナへ入れる

`container/` のイメージには Python、`claude-agent-sdk`、`google-cloud-bigquery`、Claude Code CLI、`curl` と必要な CA 証明書を含める。通常コマンドは低負荷で待機させ、`kubectl exec deploy/test -- ...` を何度でも実行可能にする。

`claude_agent_sdk.py` は必須の prompt 引数を受け、Vertex 利用フラグ、Terraform から渡されたプロジェクト ID、既定の Vertex ロケーション `global`、モデル `claude-haiku-4-5@20251001` を使い、Agent SDK の最終結果を標準出力へ出す。URL を処理できるよう WebFetch 相当の必要最小ツールだけを許可し、ワンショットで終了する。`test_bq.py` は指定クエリを変更せずに実行し、行を安定したテキスト形式で出力する。

SDK をホストへ直接インストールする案は再現性が低く、検証対象の Pod 外で通信してしまうため採用しない。Claude と BigQuery を別イメージに分ける案も、同一の ID とネットワーク境界を検証する目的に対して不要である。

### 4. 通常マニフェストと通信制御マニフェストを別適用にする

`k8s/` には KSA と `test` Deployment の通常マニフェストを置き、通信制御は別ファイル（または別 kustomize overlay）にする。Deployment は専用ラベルを持ち、すべてのポリシーはそのラベルだけを選択する。この分離により、制限前の基準テストが通るまで通信制御を適用しない手順を構造的に保つ。

マニフェスト内の GSA 名、プロジェクト ID、イメージ URL は固定値を複製せず、デプロイスクリプトが Terraform output から安全に置換または `kubectl set image` で注入する。

### 5. 標準 NetworkPolicy と GKE FQDNNetworkPolicy を組み合わせる

標準 `NetworkPolicy` で対象 Pod の egress をデフォルト拒否し、クラスタ DNS（UDP/TCP 53）と Workload Identity のメタデータサーバーへの通信だけを IP/namespace ベースで許可する。外部 HTTPS は GKE の `FQDNNetworkPolicy` で TCP 443 に限定して許可し、初期許可リストを次に限定する。

- `github.com`
- `aiplatform.googleapis.com`（Vertex の `global` endpoint）
- `bigquery.googleapis.com`

SDK/Google クライアントが実行時に別の正式な Google API endpoint を必要とすることが観測された場合は、失敗ログと名前解決を根拠に、その正確な FQDN のみを追加する。広い `0.0.0.0/0` や `*.com` は許可しない。`*.googleapis.com` の一括許可も初期選択とはせず、個別 endpoint では安定動作できないことが確認された場合の限定的な代替とする。`checkip.amazonaws.com` はどの許可規則にも含めない。

IP allowlist は Google/GitHub の IP 変更に追随できず、HTTP proxy は今回の Dataplane V2 検証とは別の運用コンポーネントを増やすため採用しない。Kubernetes 標準リソースだけでは FQDN 要件を満たせないため、GKE 固有 CRD の利用を意図的に受け入れる。

### 6. スクリプトで構築と検証のフェーズを固定する

`scripts/` に少なくとも、Terraform apply と kubeconfig 取得、イメージ build/push と通常マニフェストの deploy、制限前テスト、通信制御の apply、制限後テストを置く。各スクリプトは `set -euo pipefail`、前提コマンド検査、対象 project/cluster の表示を行い、非対話で再実行できるようにする。

制限前テストは Pod Ready を待ち、GitHub curl、Agent SDK、BigQuery の順に成功を確認する。制限後テストはポリシーの成立を待って同じ 3 つを再実行し、最後に `curl --connect-timeout` / `--max-time` 付きで `checkip.amazonaws.com` が失敗することを反転条件で確認する。未許可先が成功した場合はテスト全体を失敗させる。

単一の「全部実行」スクリプトにまとめずフェーズを分けることで、人間が制限前の成功を確認してから明示的にポリシーを適用でき、問題発生箇所も判別できる。

## Risks / Trade-offs

- [FQDN ポリシーは DNS 応答、TTL、既存接続に依存し、適用直後に短い収束時間がある] → apply 後にリソース成立を確認し、既存 exec プロセスを再利用せず、新しい接続で有限時間のリトライを行う。
- [Claude Code/Google SDK の endpoint がバージョンや設定で増える可能性がある] → 依存バージョンを固定し、制限前後テストで回帰を検出し、観測された正確な FQDN だけをレビュー付きで追加する。
- [モデルがプロジェクトで未承認、未購入、または `global` で利用不能だと IAM が正しくても失敗する] → apply 前提として Vertex AI API と Model Garden の利用条件を確認し、エラーを通信遮断と区別して表示する。
- [単一ノードは upgrade、障害、リソース不足で停止する] → 学習・検証環境のコスト優先トレードオフとして受け入れ、Pod Ready とノード状態を各テスト前に確認する。
- [`default` ネットワークまたは `default` サブネットが削除済みのプロジェクトでは構築できない] → Terraform の data lookup で早期に明確に失敗させ、新規ネットワークを暗黙作成しない。
- [外部 IP を持つ公開ノードは本番向け境界ではない] → 今回は egress ポリシー検証に限定し、本番化では private nodes と Cloud NAT/Private Google Access を別変更として設計する。
- [公開データセットの内容は日付とともに変化し、指定日が空になる可能性がある] → ジョブ成功とスキーマを主判定にし、0 行を認証・到達性エラーとは扱わない。

## Migration Plan

1. Terraform を初期化・計画し、対象 project、zone、既存 `default` subnet を確認してから apply する。
2. kubeconfig を取得し、クラスタの Dataplane V2、FQDN policy 機能、単一ノード、Workload Identity/IAM を検査する。
3. コンテナを build/push し、KSA と Deployment だけを適用して Pod Ready を待つ。
4. 制限前テストを実行し、GitHub、Claude、BigQuery がすべて成功するまでネットワークポリシーを適用しない。
5. 通信制御マニフェストを適用し、制限後テストで 3 つの許可通信の成功と未許可通信の失敗を確認する。
6. 問題時は通信制御マニフェストだけを削除して基準状態へ戻す。ワークロードの rollback は以前のイメージ digest へ戻し、環境全体が不要ならオペレータが確認後に Terraform destroy を実行する。
