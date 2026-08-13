## ADDED Requirements

### Requirement: GKE DNS 名前解決ログの追跡
システムは GKE クラスタが使用する VPC の DNS Query Logging を単一の Cloud DNS Policy で有効化し、その設定を IaC で管理しなければならない（SHALL）。DNS query log は既存の Cloud Logging 保存経路に保持し、外部 sink、広範な Log Router exclusion、ワークロードの外向き通信許可、またはワークロード IAM 権限を追加してはならない（MUST NOT）。

#### Scenario: VPC の DNS logging 設定を検査する
- **WHEN** オペレータが対象 GKE クラスタの VPC に関連付けられた Cloud DNS Policy と Terraform の管理状態を検査する
- **THEN** 対象 VPC に関連付けられた policy は重複せず、その policy で DNS Query Logging が有効である

#### Scenario: GKE ワークロードの DNS query log を取得する
- **WHEN** オペレータが対象テスト Pod から解決可能な FQDN の DNS 問い合わせを発生させ、発生時刻以降の `dns_query` ログを有限時間検索する
- **THEN** Cloud Logging に対象 FQDN の `queryName`、問い合わせ元を示す `sourceIP`、および一つ以上の名前解決結果を含む `rdata` が記録され、検証は必須フィールドが欠ける場合またはログが見つからない場合に非ゼロで終了する

#### Scenario: DNS 応答を NetworkPolicy deny と相関する
- **WHEN** 対象 Pod が名前解決した未許可 FQDN への接続を試み、オペレータが DNS query log と Dataplane V2 の deny log を調査する
- **THEN** オペレータは問い合わせ時刻、`sourceIP`、`queryName`、`rdata`、接続元 Pod、deny の宛先 IP、および deny 発生時刻を表示し、DNS 応答の IP と deny の宛先 IP を対応付けられる

#### Scenario: Kubernetes メタデータの非付与を考慮して検索する
- **WHEN** オペレータが namespace または Pod を起点に DNS query log を調査する
- **THEN** 手順は `dns_query` ログに namespace、Pod 名、container 名が直接付与されないことを示し、これらの resource label による直接フィルタではなく時刻、送信元 IP、問い合わせ名、および応答 IP による相関を使用する

#### Scenario: DNS logging 有効化後も既存の境界を維持する
- **WHEN** DNS Query Logging を有効化した後に既存の通信制御および権限の検証を再実行する
- **THEN** GitHub、Vertex AI、および BigQuery の既存許可通信は成功し、未許可通信は引き続き拒否され、外部 log sink、追加の FQDN allowlist、および追加のワークロード IAM role は存在しない
