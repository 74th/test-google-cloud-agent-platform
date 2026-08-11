## ADDED Requirements

### Requirement: NetworkPolicy 拒否ログの追跡
システムは GKE Dataplane V2 が拒否した対象 Pod の通信を Cloud Logging に記録し、オペレータが接続元、宛先、方向、および拒否結果を追跡できなければならない（SHALL）。拒否ログの有効化によって、許可通信を既定で記録したり、Pod の外向き通信許可や Google Cloud IAM 権限を追加したりしてはならない（MUST NOT）。

#### Scenario: 拒否ログ設定を確認する
- **WHEN** オペレータがクラスタの Network Policy Logging 設定を検査する
- **THEN** Dataplane V2 の拒否通信ログは有効、許可通信ログは無効であり、設定エラーが報告されていない

#### Scenario: 未許可 egress の拒否ログを取得する
- **WHEN** NetworkPolicy 適用後の対象 Pod が未許可の `checkip.amazonaws.com:80` へ接続し、有限時間内に失敗する
- **THEN** 対象クラスタの Cloud Logging に、同じ Pod を接続元とする `policy-action` ログが有限時間内に現れ、direction は `egress`、disposition は `deny`、protocol は `tcp`、宛先 port は `80` である

#### Scenario: 拒否ログを接続試行と対応付ける
- **WHEN** オペレータが拒否通信を発生させた時刻、Pod 名、および接続先の名前解決結果を使ってログを検索する
- **THEN** 検証結果は接続元 Pod、宛先 IP と port、protocol、direction、disposition、および集約された試行回数を表示し、該当ログが見つからない場合は非ゼロで終了する

#### Scenario: ログ有効化後も既存の通信境界を維持する
- **WHEN** 拒否ログ設定と既存の NetworkPolicy を適用して制限後テストを再実行する
- **THEN** GitHub、Vertex AI、および BigQuery は成功し、`checkip.amazonaws.com` は引き続き拒否され、FQDN allowlist とワークロード IAM principal の権限は追加されていない

### Requirement: Artifact Registry の固有な所有境界
システムは検証環境の Artifact Registry repository IDに既定で `test-gke-isolated` を使用しなければならず（SHALL）、image build、push、deploy、およびcleanupでTerraform outputが示す同じrepositoryを一貫して参照しなければならない（SHALL）。cleanupは現在のTerraform stateが所有するリソースだけを対象とし、stateに存在しない同名または類似名のrepositoryをimportまたは削除してはならない（MUST NOT）。

#### Scenario: 既定のrepositoryを計画する
- **WHEN** オペレータが `artifact_repository_id` を上書きせずにTerraform planを生成する
- **THEN** 作成対象のArtifact Registry repository IDは `test-gke-isolated` であり、image repository outputにも `/test-gke-isolated` が含まれる

#### Scenario: 後段処理でTerraform outputを使用する
- **WHEN** オペレータがimage build、push、およびworkload deployのスクリプトを実行する
- **THEN** すべての処理はTerraformのimage repository outputを使用し、`claude-agent`を含むrepository IDをハードコードしない

#### Scenario: state外のrepositoryをcleanup対象から除外する
- **WHEN** GCP上に同名または類似名のrepositoryが存在するが、現在のTerraform stateにそのresource addressが存在しない
- **THEN** cleanupはそのrepositoryをimportまたは削除せずに停止し、stateが所有する削除対象だけをオペレータへ表示する

#### Scenario: 所有対象だけを削除する
- **WHEN** オペレータが確認済みのdestroy planを適用する
- **THEN** planに含まれるrepository IDはTerraform stateが所有する `test-gke-isolated` であり、他のArtifact Registry repositoryは保持される
