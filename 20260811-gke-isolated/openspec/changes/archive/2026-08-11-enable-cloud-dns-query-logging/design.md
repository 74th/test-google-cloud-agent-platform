## Context

既存 Terraform は `data.google_compute_network.default` で既存 VPC を参照し、その VPC 上に GKE Dataplane V2 クラスタを構築している。Network Policy Logging とその `policy-action` deny log の検証は既に存在するが、DNS Policy は Terraform に存在せず、`dns.googleapis.com` も管理対象 API に含まれていない。2026-08-11 の読み取り専用確認では、現在選択中の `nnyn-dev` プロジェクトに Cloud DNS Policy は存在しなかった。

Cloud DNS Query Logging は VPC 単位であり、`dns_query` resource には Kubernetes namespace、Pod 名、container 名が直接付与されない。DNS cache、ログ取り込み遅延、GKE の DNS 転送経路によって、アプリケーション接続とログが一対一にならないこと、および `sourceIP` が常に Pod IP を表すとは限らないことを前提とする。

## Goals / Non-Goals

**Goals:**

- 現在の VPC に DNS Query Logging を Terraform 管理で追加し、重複 policy を作成しない安全策を設ける。
- 実際の GKE ワークロードから query を発生させ、現環境のログ schema で `queryName`、`sourceIP`、`rdata` を検証する。
- DNS 応答 IP と `policy-action` deny の宛先 IP を時刻情報とともに調査できる再現可能な手順を提供する。
- DNS logging の追加が既存の通信許可、IAM、Log Router 保存経路を変えないことを確認する。

**Non-Goals:**

- namespace 単位で DNS query log を保存、分離、または直接フィルタ可能にすること。
- BigQuery、Pub/Sub、Cloud Storage への log sink や独自の logging bucket を作ること。
- kube-dns / NodeLocal DNSCache の query logging、DNS proxy、CoreDNS、eBPF ベースの DNS 可観測性を導入すること。
- DNS query を通信監査ログとして扱い、各 application connection と一対一に対応させること。
- Shared VPC 全般に対応する provider 構成へ変更すること。

## Decisions

### 1. 既存 VPC に Terraform の Cloud DNS Policy を関連付ける

`dns.googleapis.com` を `local.required_services` に追加し、`google_dns_policy.gke_dns_logging` を `gke-dns-logging` という名前で作成する。`enable_logging = true` とし、`networks.network_url` には既存の `data.google_compute_network.default.id` を使う。API 有効化の完了後に policy を作る依存関係を明示する。

現在の対象プロジェクトには policy がないため、新規 resource が現在の構成に一致する。apply 前の setup preflight では、選択した VPC に関連付く policy と Terraform state を照合する。既存 Terraform resource が見つかればそれへ `enable_logging = true` を追加し、state 外 policy が後から見つかった場合は plan 前に停止して明示的な IaC 取り込み判断を求める。外部 policy が存在する状態で同じ VPC 向け resource を自動作成しない。

代替として `gcloud dns policies create/update` を setup script から実行する方式は、Terraform の所有境界と plan / review / rollback を外れるため採用しない。外部 policy の自動 import も、その policy の既存設定や destroy 時の所有権を暗黙に引き受けるため採用しない。

### 2. 既存の Cloud Logging 保存経路だけを利用する

DNS Query Logging が生成する `dns_query` entry はプロジェクト既定の Cloud Logging 経路へ送る。Log Router sink、bucket、exclusion は Terraform に追加しない。これにより新しい配送先の運用を増やさず、既存ログを広範な exclusion で失うリスクを避ける。

代替の BigQuery / Pub/Sub / Cloud Storage sink は長期分析や後段相関には有効だが、今回の調査目的には不要であり採用しない。

### 3. 専用スクリプトで実ログを有限時間 polling する

既存の `test-network-policy-logging.sh` と同様に、前提コマンド、認証、Terraform output、対象 Pod、Logging API を検査する専用スクリプトを追加する。問い合わせ開始時刻を UTC で記録し、対象 Pod から設定可能なテスト FQDN（既定は `example.com`）を問い合わせた後、次を基本 filter として有限時間 polling する。

```text
resource.type="dns_query"
timestamp>="START_TIME"
jsonPayload.queryName:"example.com"
```

ログの FQDN 末尾 dot、`rdata` の表現、payload の追加フィールドは実際の entry を取得して許容的に解析する一方、`queryName`、非空の `sourceIP`、IP アドレスを含む非空の `rdata` は必須とする。権限エラー、query エラー、timeout、必須 field 欠落を異なる非ゼロ終了として扱い、成功時は timestamp と相関用フィールドを表示する。cache hit で entry が生成されない場合に備え、テスト FQDN、待機時間、polling 間隔を環境変数で差し替え可能にする。

一回の `gcloud logging read` だけで判定する方式は Cloud Logging の取り込み遅延に弱いため採用しない。固定 sleep も環境差が大きく不要な待機を生むため採用しない。

### 4. DNS と deny の相関は時刻と応答 IP を中心に行う

検証結果と README には DNS log の `timestamp`、`sourceIP`、`queryName`、`responseCode`、`rdata` を表示し、deny log の Pod、timestamp、destination IP / port と並べる。`rdata` の IP が deny の destination IP と一致することを主要な対応条件とし、query と deny の時間帯、および DNS 経路上の `sourceIP` を補助条件にする。

`dns_query` に存在しない Kubernetes resource label で namespace を直接 filter する方式は採用しない。また `sourceIP == Pod IP` を無条件には要求せず、実環境で node / DNS cache を経由する場合は、対象 Pod から発生させた一意な時間窓と問い合わせ名、応答 IP を使う。namespace 単位の永続的な分離が将来必須になった場合は、別 change で kube-dns / NodeLocal DNSCache logging、DNS proxy、または後段 enrichment を評価する。

### 5. Shared VPC のログ所有先を運用手順で明示する

現在の Terraform はクラスタ project 内の VPC data source を参照する構成である。README では Shared VPC の場合に host project 側で policy と `dns_query` ログを確認する必要があることを明記するが、この change では provider alias や host / service project の変数モデルは追加しない。

## Risks / Trade-offs

- [apply 前に同じ VPC へ state 外 policy が追加される] → setup preflight で network association と state を再確認し、自動作成せず停止する。
- [DNS cache によりテスト query の新規 entry が見つからない] → cache 制約を明記し、テスト名と timeout を差し替え可能にして、必要に応じて別の解決可能な FQDN または TTL 経過後に再試行する。
- [Cloud Logging の取り込みが遅延する] → 有限時間 polling と設定可能な timeout を使用し、一回取得で失敗判定しない。
- [`sourceIP` が Pod IP ではなく node または DNS component を表す] → sourceIP の存在は検証するが直接一致は前提にせず、時刻、問い合わせ名、`rdata`、deny 宛先 IP を組み合わせる。
- [VPC 全体の query log により保存量と課金が増える] → scope と費用影響を README に明記し、外部 sink は増やさない。不要になった場合は Terraform plan で policy の logging 無効化または resource 削除をレビューする。
- [Shared VPC で service project を検索してログを見落とす] → host project が policy とログの所有先になり得ることを手順に明記する。

## Migration Plan

1. Terraform と GCP の読み取り専用 preflight で、対象 VPC、既存 DNS Policy、Terraform state の所有関係を確認する。
2. `dns.googleapis.com` と DNS Policy を含む Terraform plan を生成し、既存 VPC への関連付け、`enable_logging = true`、他 policy / sink / IAM / network rule への変更がないことをレビューする。
3. 保存済み plan を apply し、Cloud DNS Policy の実設定を読み取って logging が有効であることを確認する。
4. 対象 Pod から DNS query を発生させ、`dns_query` entry と必須 field を検証する。
5. 未許可 FQDN への既存 deny テストを実行し、DNS 応答 IP と `policy-action` destination IP を時刻とともに照合する。
6. 既存の許可通信、deny、IAM、sink 不変性を再確認し、実際のログ field と検証結果を README に記録する。

ロールバックでは Terraform plan を生成し、今回追加した policy の削除または logging 無効化だけが対象であることを確認してから apply する。既存の NetworkPolicy logging、GKE cluster、VPC、sink は変更しない。
