## Context

リポジトリには OpenSpec 構成以外の実装がなく、検証対象は project `nnyn-dev` 上に新規作成する。既存の Autopilot cluster を含む既存 resource は対象外であり、検証 resource は識別・削除可能でなければならない。Agent Registry の Terraform provider 対応と `gcloud` command は変化し得るため、実装時点の公式 documentation と CLI help を source of truth とする。

Cloud Run と GKE では公開面と認証方式が異なる。Cloud Run は IAM 保護した HTTPS endpoint を主たる end-to-end 経路とする。一方、GKE 検証のためだけに external Load Balancer、domain、certificate を増やすことはコストと攻撃面に見合わないため、GKE endpoint は cluster 内に閉じ、cluster 内 client から実行する。Agent Registry は実行 proxy ではなく metadata discovery 面として扱う。

## Goals / Non-Goals

**Goals:**

- 一つの version 固定 image と Tool specification を Cloud Run と GKE で共有する。
- Cloud Run の Registry discovery から IAM 認証付き Tool execution までを主経路として成立させる。
- GKE では cluster-local endpoint の登録・発見と、cluster 内 client による Tool execution を成立させる。
- Terraform plan で対象範囲をレビューでき、検証後に安全に削除できる構成にする。
- command output と log を sanitization して保存し、実測値に基づく比較を作る。

**Non-Goals:**

- Agent Registry を MCP execution proxy として扱うこと。
- GKE MCP endpoint の Internet 公開や、本番用 ingress / certificate / multi-zone 可用性を設計すること。
- Agent Gateway または Claude Agent SDK の既存検証環境を変更すること。
- stateful MCP session、負荷試験、Tool lifecycle の互換性試験、GKE 内 backend 接続を網羅すること。

## Decisions

### 1. 検証を Cloud Run、Registry、GKE の三段階に分ける

最初に local container と Cloud Run の MCP protocol・IAM・scale-to-zero を確認し、次に Agent Registry の登録・検索・発見後実行を確認する。最後に同一 digest を GKE Standard に配置し、cluster-local URL の Registry entry と cluster 内実行を確認する。段階ごとに failure domain を分けることで、Registry discovery failure と runtime/network failure を混同しない。

代替案の全 resource 一括構築は速く見えるが、失敗原因と課金開始点を分離しにくいため採用しない。

### 2. 最小の stateless MCP application と単一 image を使用する

公式 MCP SDK の Streamable HTTP server を利用し、`/mcp` に決定的な応答を返す一つの Tool を公開する。application は `$PORT`（未指定時は開発用 default）を読み、`0.0.0.0` で待ち受ける。Tool metadata は一つの source から runtime と `toolspec.json` に反映し、検証 script で `tools/list` との差分を検出する。image は mutable な `latest` ではなく digest で Cloud Run と GKE に渡す。

代替案の複数 business Tool は discovery の価値を示しやすいが、今回確認したい platform 経路とは無関係な schema と test case を増やすため採用しない。

### 3. Cloud Run を唯一の外部実行 endpoint とする

Cloud Run は ingress を必要範囲に設定し、`allUsers` を付与せず、専用 runtime Service Account で実行する。専用 test invoker identity にだけ `roles/run.invoker` を付与し、検証 client は audience を service URL とする ID token を取得する。minimum instance は 0、maximum instance は小さい固定値とする。

GKE は `ClusterIP` Service とし、Agent Registry には cluster DNS の `/mcp` URL を登録する。Registry 検索結果から得た URL は、一時的な in-cluster validation Job で呼び出す。これにより Registry entry と実行先の一致を保ちながら、external Load Balancer を作らない。operator の protocol debugging に限り `kubectl port-forward` を補助手段とする。

代替案の GKE external HTTPS ingress は本番近似度が上がる一方、domain、certificate、Load Balancer、追加 IAM と継続コストが必要になるため、本変更では扱わない。

### 4. Terraform root を共有し、段階適用できる feature flag を設ける

Terraform は project、region、zone、resource prefix、network CIDR、および GKE 作成可否を variable 化する。API、Artifact Registry、Service Account/IAM、Cloud Run、Custom VPC/subnet/secondary ranges、zonal GKE Standard、専用 node pool を module または責務別 file に分ける。GKE は既定で無効にして Cloud Run 検証を先行できるようにし、有効化時は VPC-native、Workload Identity、小さい machine type、最小 node 数を使用する。

resource name の制限により完全な識別子が入らない場合は短い一意名と `experiment=20260823-mcp-server` label の両方を使用する。既存 resource を data source として暗黙再利用せず、state に属する新規 resource だけを管理する。

代替案の Cloud Run / GKE 別 root は state の影響範囲を狭めるが、API、Artifact Registry、IAM、network input の重複と image digest のずれが生じやすいため採用しない。

### 5. Agent Registry 操作は capability detection を行う冪等 script にする

実装開始時に `gcloud version`、該当 command の `--help`、公式 documentation を記録する。Terraform provider に安定した対応 resource があれば Terraform を優先し、なければ version 管理した `toolspec.json` と idempotent な create-or-update script を使用する。Cloud Run entry と GKE entry は別 ID とし、名前、interface URL、protocol binding、Tool metadata を取得して期待値と比較する。検索と runtime execution は別 command・別証跡にする。

代替案の import-tools は public endpoint を要求する可能性があり、IAM 保護を一時解除する必要があるため、manual Tool specification 登録を採用する。

### 6. 証跡は生成物と report を分離する

再実行手順と期待値は repository の document/script に置く。実環境出力は timestamp 付き evidence directory に保存し、token、credential、個人情報を除去する。最終 report は各検証項目を PASS / FAIL / SKIP とし、証跡 path を参照する。Cloud Run cold start は instance count metric または同等の platform 観測、application start log、request latency を組み合わせ、warm request と少なくとも一回比較する。

環境を実際に構築できない場合でもコード検証結果と未実行理由を記録し、cloud 項目を PASS にしない。

## Risks / Trade-offs

- [Agent Registry の API / CLI / Terraform support が preview 中または変更される] → 実装時に公式 documentation と CLI help を固定して記録し、登録処理を一箇所に隔離する。
- [GKE cluster-local URL は cluster 外 client から実行できない] → in-cluster validation Job で発見 URL を直接使用し、外部 Agent 統合は次の ingress/security 検証として明記する。
- [zonal single-node GKE は本番の可用性を再現しない] → hosting compatibility と運用差の検証に限定し、report で regional production 構成との差を明示する。
- [GKE control plane と node は短時間でも費用が発生する] → GKE feature flag を既定 off にし、Cloud Run 完了後だけ作成して即日 cleanup できる手順を用意する。
- [Cloud Run がいつ scale-to-zero したかを直接断定しにくい] → platform metric と起動 log を併用し、観測できなければ SKIP として推測で PASS にしない。
- [CIDR が既存ネットワークと重複する] → apply 前に project の network/subnet と利用者指定の接続 network を inventory し、CIDR を variable として plan review する。
- [Terraform destroy が API disable や共有 artifact を巻き込む] → この state が新規作成した resource だけを管理し、API の disable-on-destroy を避け、destroy plan を必須確認にする。

## Migration Plan

1. current project、有効 API、network、subnet、Cloud Run、Artifact Registry、GKE cluster を read-only で inventory し、既存 Autopilot cluster と CIDR を記録する。
2. local MCP test、container build、Tool specification consistency test を完了する。
3. Terraform plan を保存・レビューし、GKE 無効の状態で shared resource と Cloud Run を apply する。
4. Cloud Run の認証、未認証拒否、MCP 正常系、Registry 登録・検索・発見後実行、scale-to-zero を検証する。
5. GKE を有効にした plan を再レビューして apply し、同一 image digest の Deployment、ClusterIP Service、validation Job を配置する。
6. GKE entry の登録・検索と cluster 内 Tool execution を検証し、比較 report を更新する。
7. 証跡を退避した後、Agent Registry entry と Kubernetes workload を削除し、Terraform destroy plan の対象を確認して検証 resource を削除する。

Rollback は各段階の逆順とする。Cloud Run revision が失敗した場合は直前の正常 digest に戻す。GKE rollout が失敗した場合は Deployment を直前 digest に戻すか GKE feature flag を無効にする。既存 resource には rollback 操作を行わない。

## Open Questions

- 実装時点で Agent Registry の対象 location と command surface のどれが `nnyn-dev` で利用可能か。availability discovery の結果に基づいて supported region または `global` を選び、選定結果を report に固定する。
- scale-to-zero の待機時間と instance count を最も明確に示す Cloud Monitoring metric は何か。利用可能な metric descriptor を確認して evidence 取得方法を確定する。
