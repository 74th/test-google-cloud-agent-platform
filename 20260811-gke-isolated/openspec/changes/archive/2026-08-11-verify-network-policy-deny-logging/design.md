## Context

既存の `isolated-claude-agent-runtime` は GKE Dataplane V2 の標準 NetworkPolicy と FQDNNetworkPolicy を組み合わせ、未許可の `checkip.amazonaws.com` が timeout することを検証している。現在はクライアント側の失敗だけが証拠であり、Kubernetes Event や Pod log にデータプレーンの拒否理由は残らない。

Dataplane V2 クラスタにはクラスタ単位で一つだけ存在する `networking.gke.io/v1alpha1` の `NetworkLogging/default` がGKEによって作成される。deny loggingを有効にすると、Cloud Loggingの `policy-action` logに `disposition=deny`、接続元・宛先、protocol、direction、countなどが記録される。ただし暗黙denyには単独の拒否ポリシーが存在しないため、deny logには拒否したNetworkPolicy名は含まれない。

前回の検証環境はTerraform destroy済みであるため、実環境の受入検証では既存スクリプトからクラスタとワークロードを再構築する。

既存の `artifact_repository_id` の既定値 `claude-agent` は別プロダクトのrepositoryと衝突した。さらに、Terraform stateに存在しないrepositoryを構成上の名前一致だけでimportし、destroy対象へ加えると、所有権を誤認して他プロダクトのデータを削除できる。repository名とstate所有境界の両方を修正する必要がある。

## Goals / Non-Goals

**Goals:**

- 許可通信のログ量を増やさず、対象Podのdeny通信をCloud Loggingで観測できるようにする。
- 一回の接続試行を、開始時刻、Pod名、名前解決した宛先IP、port、protocol、directionでログと対応付ける。
- Cloud Loggingの反映遅延とdeny log集約を考慮した、有限時間で再実行可能な検証を提供する。
- ログ設定が既存allowlist、Workload Identity、許可済み通信の動作を変えないことを確認する。
- Artifact Registryに検証環境固有のIDを使用し、buildからcleanupまで同一のTerraform outputを参照する。
- cleanup対象を現在のTerraform stateが所有するresource addressへ限定する。

**Non-Goals:**

- すべての許可通信を記録すること。
- VPC Flow Logs、Packet Mirroring、Hubble UIなど別のフロー観測基盤を導入すること。
- deny logから、暗黙denyを発生させた単一のNetworkPolicy名を特定すること。
- Cloud Loggingのsink、長期保存bucket、アラート、ダッシュボードを構築すること。
- ログ閲覧権限をPodのKSA principalへ付与すること。
- state外の既存Artifact Registry repositoryを採用、import、移行、または削除すること。

## Decisions

### 1. `NetworkLogging/default` でdenyだけを記録する

`k8s/network-logging.yaml` で既存の `NetworkLogging/default` を宣言し、`spec.cluster.deny.log=true`、`deny.delegate=false`、`allow.log=false`、`allow.delegate=false` とする。適用前後にclient/server dry-run、`kubectl get`、`kubectl describe`を実行し、CRDの存在と設定エラーがないことを確認する。

許可通信も記録する案は、今回の目的に不要なログ量とCloud Logging費用を増やすため採用しない。namespace annotationへ委譲する案も、単一の検証namespaceしか使わず設定箇所が分散するため採用しない。

### 2. logging設定を通信ポリシーより先に適用する

denyの発生を取りこぼさないよう、NetworkLogging設定を成立させてから標準NetworkPolicyとFQDNNetworkPolicyを適用する。既存の `apply-network-policy.sh` を、logging設定のdry-run・apply・成立確認を含む順序へ拡張する。

loggingをテスト後に有効化する案では、確認対象となる接続試行そのものが記録されない可能性があるため採用しない。

### 3. 専用スクリプトで接続試行とCloud Loggingを照合する

`scripts/test-network-policy-logging.sh` を追加し、次の情報を接続前に保存する。

- UTCの開始時刻
- selectorから取得した実行中Pod名とnamespace
- Pod内のDNSで解決した `checkip.amazonaws.com` のIPv4アドレス集合
- 接続先port `80` とprotocol `tcp`

その後、有限timeout付きcurlが失敗することを確認し、`gcloud logging read` を一定間隔で再実行する。queryは `resource.type="k8s_node"`、project、cluster location/name、`policy-action` log、開始時刻以降、`jsonPayload.disposition="deny"`、`direction="egress"`、接続元Pod名、port 80、protocol tcpで絞り込む。結果の宛先IPが事前の名前解決結果に含まれることも確認する。

既存の制限後テストへ直接組み込む案は、Cloud Loggingの反映待ちによって機能テストの所要時間と失敗原因が混ざるため採用しない。専用スクリプトに分け、接続遮断とログ観測を個別に再実行できるようにする。

### 4. deny logの集約と反映遅延を受入条件に織り込む

deny logは同一接続の再試行を集約し、`count`が1より大きくなる場合がある。そのためログ件数や一試行一レコードを要求せず、開始時刻以降に条件一致するレコードが一つ以上あり、必須フィールドと宛先が一致することを判定する。反映待ちは既定300秒の有限pollingとし、環境変数で調整可能にする。

固定sleepだけを使う案は、ログ反映の揺らぎに弱く不要な待機も増えるため採用しない。

### 5. Cloud LoggingのAPIと閲覧権限はオペレータ側に置く

Terraformのrequired servicesに `logging.googleapis.com` を追加し、クラスタのCloud Loggingが有効であることを確認する。ログ検索はホスト上の `gcloud` 認証を使い、事前検査で対象projectとログ閲覧可否を確認する。Podには `roles/logging.viewer` などを付与しない。

ログ検索をPod内から実行する案は、隔離対象へ観測系のIAM権限とCloud Logging endpointを追加し、検証対象の境界を広げるため採用しない。

### 6. Artifact Registry IDを環境固有にし、stateを所有権の根拠にする

`artifact_repository_id` の既定値を `test-gke-isolated` に変更する。repository URLを必要とするimage build、push、deploy、表示、READMEの例は、文字列を個別に組み立てず、Terraformの `image_repository` または `image_uri` outputを参照する。これにより変数を上書きした場合も同じrepositoryへ一貫して追従する。

cleanup前には `terraform state list` とdestroy planを表示し、`google_artifact_registry_repository.agent` がstateに存在し、その実IDが期待するproject、location、repository ID `test-gke-isolated` と一致する場合だけplanの適用へ進む。resource addressがstateにない場合、GCP上の名前一致を根拠に `terraform import` や `gcloud artifacts repositories delete`を実行してはならない。別途存在するrepositoryは、この変更の所有対象ではない。

ランダムsuffixを付ける案は衝突耐性が高い一方、再現時に名前が安定せず人間が識別しにくいため採用しない。既存の `claude-agent` をimportして再利用する案は所有権を証明できず、他プロダクトへの影響を防げないため採用しない。

## Risks / Trade-offs

- [Cloud Loggingへの反映に時間差がある] → 有限pollingと開始時刻filterを使い、timeout時は実行したqueryを表示する。
- [deny logが複数試行を集約する] → レコード数ではなく必須field、宛先、`count >= 1`を検証する。
- [暗黙denyのログにはNetworkPolicy名が含まれない] → 対象Pod、時刻、宛先IP/port、direction、dispositionで対応付け、仕様上の制約をREADMEへ明記する。
- [FQDNは複数IPへ解決され、TTLで変化する] → 接続直前にPod内で全IPv4を取得し、ログの宛先がその集合のいずれかであることを確認する。
- [ログ閲覧権限がないと通信制御が正常でも検証が失敗する] → スクリプト開始時にgcloud認証、project、Logging API、query実行可否を検査し、権限エラーを拒否ログ未検出と区別する。
- [deny loggingはログ保存量と費用を増やす] → allow loggingは無効のままにし、検証後の無効化手順とCloud Loggingの課金注意をREADMEへ記載する。
- [GKE addonが所有するdefault objectを変更する] → 名前を変えず、サポートされるNetworkLogging specだけを宣言し、describeのEventで設定エラーを検出する。
- [固定repository IDでも別の実行者が同名を作成できる] → apply前にrepositoryの存在とTerraform stateを照合し、state外に存在する場合はimportせず、明示的な別IDへの上書きを要求する。
- [destroy planの対象を名前だけで判断すると他プロダクトを削除できる] → resource address、project、location、repository IDをstateとplanの両方で検査し、不一致ならcleanupを停止する。

## Migration Plan

1. `artifact_repository_id` の既定値を `test-gke-isolated` に変更し、全参照がTerraform outputを使うことを確認する。GCP上に同名repositoryが存在してstateにない場合はimportせず、applyを停止する。
2. TerraformにLogging APIを追加し、planで既存ネットワーク、allowlist、Pod IAMに変更がないことを確認してクラスタを再構築する。
3. ワークロードをdeployし、通信制御前の既存テストを通す。
4. `NetworkLogging/default` のdeny loggingを適用して成立を確認した後、標準NetworkPolicyとFQDNNetworkPolicyを適用する。
5. 既存の制限後テストを実行し、許可通信の成功と未許可通信の拒否を再確認する。
6. 専用ログ検証で新しい拒否通信を発生させ、Cloud Loggingの該当レコードを取得して必要fieldを確認する。
7. READMEの手順を先頭から再実行し、検証結果を記録する。検証終了後はstateとdestroy planに含まれる `test-gke-isolated` を照合してからTerraform管理リソースを削除し、他のrepositoryが保持されたことを確認する。

ロールバック時は `NetworkLogging/default` の `deny.log` を `false` に戻す。通信ポリシーやワークロードは変更せず、環境全体が不要な場合はTerraform destroyを実行する。
