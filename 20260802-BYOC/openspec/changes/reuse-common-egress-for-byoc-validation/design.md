## Context

動機は [proposal.md](proposal.md) を参照する。現在の BYOC 検証は、Terraform が Artifact Registry、実行サービスアカウント、IAM、GCS を管理し、`scripts/deploy_agent.py` が Agent Platform SDK で Runtime を作成する。Runtime 作成 payload には Agent Gateway 構成がなく、共有 Gateway の参照も持たない。

`common/terraform` は独立した local state で、VPC、`/28` subnet、Network Attachment、Agent-to-Anywhere Gateway を所有する。2026-08-28 の live evidence では Gateway は `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`、Network Attachment は `common-agent-gateway-attachment` であり、post-apply plan は no-op だった。Registry Service と Endpoint policy は consumer 側で所有でき、BYOC は専用名でこの state に追加する。

過去に観測した `Another Agent Gateway is already active or being created for this project and direction.` は新しい Gateway 自体の作成ではなく、別 Gateway を指定した Runtime 作成時に返された。したがって制約を「project に Gateway resource が1個」と一般化せず、Runtime の project、location、governed direction、関連付け先を実値で検証する。

既存の BYOC 成功契約は、通常4操作、GCS 入力を使う短時間ジョブ、960秒ジョブ、SDK と REST の非同期経路比較である。これらは Runtime ingress とコンテナ処理の検証であり、アプリケーションからの外向き通信を発生させないため、成功しても Gateway decision log や実 egress 通過を直接証明しない。

## Goals / Non-Goals

**Goals:**

- `common` の output/state/live resource の三者一致をデプロイの前提条件にする。
- Runtime 作成要求に `common-egress` を含め、作成後の live Runtime 構成でも同じ完全修飾 ID を確認する。
- `common-egress` が参照する Registry に BYOC 専用 GCS Service を作成し、対象 Runtime principal に限定した endpoint policy を管理する。
- 既存のローカル、コンテナ、通常4操作、短時間、960秒、SDK/REST 比較を同じ判定基準で再実行する。
- Runtime 構成、identity、image digest、試行 ID、API 結果、GCS、Cloud Logging を分離した非機密証跡を残す。
- BYOC state と共有 Gateway state の所有境界を維持する。

**Non-Goals:**

- `common/terraform`、共有 VPC、Network Attachment、`common-egress` Gateway 本体の変更。
- `mcp-20260823-*` など別 consumer の Registry Service、Endpoint policy、Runtime の変更。
- 検証終了後の Runtime 削除や `terraform destroy` を自動実行すること。

## Decisions

### 1. Gateway は外部所有の完全修飾 ID として受け取る

デプロイ CLI は `--agent-gateway` を必須入力とし、`projects/<project>/locations/<location>/agentGateways/<name>` の形式を検査する。固定の短縮名だけを埋め込まず、次の三つが同一 ID を示すことを preflight で確認する。

1. `terraform -chdir=../common/terraform output -raw agent_gateway_id`
2. `terraform -chdir=../common/terraform state show google_network_services_agent_gateway.shared`
3. `gcloud network-services agent-gateways describe common-egress ...`

さらに live Gateway の governed access path、Registry、Network Attachment を非機密属性として保存する。このリポジトリから `terraform_remote_state` で common の local state を暗黙参照する案は、実行位置への結合と所有境界を曖昧にするため採用しない。

### 2. BYOC の Registry Service と Endpoint policy を専用名で管理する

`common-egress` の live `registries` に含まれる `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1` へ、BYOC の query-job proxy が利用する `storage.googleapis.com` と `storage.mtls.googleapis.com` の HTTP JSON interface を持つ Endpoint Service を登録する。Service ID は `byoc-query-job-storage-20260828` のようにこの検証専用で、既存 Service と一致する場合は上書きせず停止する。

Service から投影された Endpoint ID を read-back し、対象 Runtime の live `spec.effectiveIdentity` から作った `principal://...` だけへ `roles/iap.egressor` を付与する。Endpoint IAM は project-wide binding や既存 consumer policy の置換ではなく、endpoint-scoped member resource として管理する。`google-nightly` provider の `google_agent_registry_service` と `google_iap_agent_registry_endpoint_iam_member` の schema を plan 前に確認する。

旧 experiment の `agw-20260822-*` Gateway、Registry Service、投影 Endpoint policy は project/location の live list と対象 IAM read-back で棚卸しする。残存する完全な ID だけを削除し、既に存在しない場合は no-op evidence を残す。現行 `common-egress`、`mcp-20260823-*` Service/Policy、同 Gateway の Registry は削除対象にしない。

### 3. Runtime と Gateway は一つの作成要求で関連付ける

Runtime 作成 payload の `spec.deploymentSpec.agentGatewayConfig.agentToAnywhereConfig.agentGateway` に、検証済みの完全修飾 ID を含める。使用中の Agent Platform SDK がこのフィールドを保持して API へ送ることをローカル契約テストで確認し、保持できない場合は同じ v1 create payload を公式 REST API へ送る薄い実装を使用する。いずれの場合も、Gateway なしで Runtime を作成した後に PATCH する二段階方式にはしない。

二段階方式は既存例がある一方、PATCH 失敗時に関連付けなしの Runtime が残り、同一 project/direction の競合調査を複雑にする。Terraform で Runtime まで管理する案は原子的な構成にできるが、現在の stable provider から nightly provider への追加移行と、イメージ build 後の再 plan が必要になり、この検証の変更範囲が大きいため採用しない。

作成後は Runtime GET の実レスポンスから Gateway ID、identity type、image URI/digest を読み戻し、要求値と一致しなければ4操作へ進まない。2026-08-28 の BYOC Reasoning Engine GET には `revision`、`traffic`、`deployedModels` が存在しなかったため、これらは BYOC の必須判定項目にしない。`spec.containerSpec.imageUri` の immutable digest を、実行イメージが要求値と一致することの判定に使う。

### 4. 共有 Gateway の CA は必要な通信が生じた場合だけイメージへ導入する

今回の BYOC アプリケーションは受信したクエリに遅延応答し、外部 HTTPS endpoint を呼び出さない。そのため Gateway TLS inspection CA を無条件にイメージへ追加せず、現在のコンテナ内容とローカル/クラウド検証の再現性を維持する。将来アプリケーションが Gateway 経由で HTTPS egress を行う場合は、`agentGatewayCard.rootCertificates` を取得して OS trust store に入れ、対応する Gateway decision log を別 capability で検証する。

### 5. 検証は構成確認と既存処理の回帰を別レイヤーで判定する

検証結果は少なくとも次を別々に持つ。

- `gateway_preflight`: common output/state/live の一致
- `runtime_gateway_association`: Runtime GET による Gateway ID の一致
- `runtime_identity_image`: identity、`spec.containerSpec.imageUri` の image digest の一致。BYOC GET にない revision/traffic/deployedModels は `not_applicable` とする
- `deployed_operations`: 4操作の応答、順序、対応ログ
- `query_job_short`: GCS input、`POST /`、processing、terminal state、GCS output
- `query_job_960`: 960秒処理の同じ5段階
- `sdk_rest_comparison`: 両経路の入力形式、終端、出力属性
- `gateway_traffic`: 対応 decision log がある場合だけ評価し、なければ `not_applicable` または `unproven`

単一の総合 PASS は使わず、必要な各レイヤーが成功した場合に「`common-egress` 関連付け後も既存 BYOC 検証が動作」と結論する。Gateway のトラフィック通過は別の結論とする。

### 6. ライブ変更前後の inventory と停止条件を固定する

apply 前に active account、project、region、common state、Gateway list、旧 `agw-20260822-*` resource、Reasoning Engine/Runtime list、BYOC Terraform state、通常 plan を読み取り専用で保存する。plan はこのディレクトリ固有の Artifact Registry、Registry Service、Endpoint IAM、サービスアカウント、IAM、GCS と API enablement だけを対象とし、common Gateway/VPC や他 experiment の名前が含まれたら停止する。

Runtime 作成が Gateway conflict を返した場合は、対象 API と既存 consumer inventory を記録して停止する。他 Runtime の削除、Gateway の作り直し、Gateway なしの再試行は行わない。

### 7. 長時間検証は短時間成功を明示ゲートにする

ローカルテストとコンテナスモーク、デプロイ済み4操作を通した後、10秒の query job を実行する。GCS input、`POST /`、処理完了、成功終端、GCS output がすべて揃った場合だけ960秒ジョブと SDK/REST 比較を実行する。ログ取り込み猶予と処理時間を超える有限の監視期限を設定し、タイムアウト時は成功扱いせず証跡不足を報告する。

## Risks / Trade-offs

- [SDK が Gateway の nested field を受け付けても送信時に除去する] → serialized request の契約テストと作成後 GET を必須にし、未対応なら同じ v1 payload の REST create に切り替える。
- [共有 Gateway に既存 consumer があり Runtime 関連付け制約へ再度抵触する] → 事前 inventory を保存し、競合時は既存 consumer を変更せず停止して正確な API error を報告する。
- [common local state と live resource が drift する] → output/state/live の三者が一致し、common の通常 plan が no-op の場合だけデプロイを許可する。
- [Registry Service の URL と managed proxy の実際の宛先が一致しない] → `storage.googleapis.com` と `storage.mtls.googleapis.com` の両 interface、投影 Endpoint、Gateway decision log を read-back してから query-job を再実行する。
- [旧 Service/Policy の削除が既存 consumer に影響する] → `agw-20260822-*` の明示 prefix と live resource ID を確認し、`mcp-20260823-*` と `common-egress` は対象外に固定する。
- [通常4操作の成功を Gateway 通過成功と誤解する] → Gateway association と BYOC ingress/processing を別レイヤーで記録し、対応 decision log がない限り egress 通過を未証明とする。
- [960秒ジョブが長時間 RUNNING となり費用が増える] → 短時間ゲート、有限の監視期限、状態と GCS/log の段階別判定を用いる。検証後も削除は自動化しない。
- [既存の dirty worktree や別 experiment の state に影響する] → 変更対象をこの OpenSpec change と BYOC ディレクトリに限定し、明示 directory と saved plan を使い、unrelated changes を変更しない。

## Migration Plan

1. common output/state/live Gateway、旧 `agw-20260822-*` resource、全 Runtime consumer を読み取り専用で棚卸しし、preflight evidence を保存する。
2. デプロイ payload、入力検証、SDK/REST request serialization、結果保存の単体テストを追加する。
3. 旧 `agw-20260822-*` の残存 resource だけを限定削除し、現行 common Gateway と他 consumer の不変性を確認する。
4. BYOC 専用 Registry Service と投影 Endpoint の endpoint-scoped policy を plan/apply し、既存 consumer の policy と common Gateway に差分がないことを確認する。
5. ローカル pytest、ランタイムスモーク、コンテナ build/4操作を実行する。
6. BYOC Terraform の format、validate、通常 plan を実行し、common Gateway/VPC と他 experiment が対象外であることを確認する。
7. 対象を確認した saved plan を apply し、一意な tag で image を build/push して digest を保存する。
8. `common-egress` を含む一つの作成要求で新規検証 Runtime を作成し、live GET で Gateway、identity、image digest を照合する。BYOC GET にない revision/traffic/deployedModels は必須条件にしない。
9. デプロイ済み4操作、Service/Policy read-back、短時間 query job、960秒 query job、SDK/REST 比較の順に実行し、非機密 evidence と結論を保存する。
10. 作成リソースを inventory し、限定した削除 plan と手順だけを提示する。Runtime 削除、Service/Policy 削除、destroy は人間の別途明示承認があるまで実行しない。

コード上のロールバックは Gateway 関連付け対応前のデプロイ CLI へ戻す。ライブ Runtime と Terraform リソースは保持し、削除をロールバックの自動工程には含めない。
