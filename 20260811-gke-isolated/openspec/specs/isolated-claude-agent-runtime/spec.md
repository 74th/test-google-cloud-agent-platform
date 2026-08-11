## Purpose

Claude Agent SDK を GKE 上で実行し、Vertex AI と BigQuery の必要な機能を保ちながら、外向き通信を宣言済みホストだけに限定できる再現可能な隔離環境を提供する。

## Requirements

### Requirement: 単一ゾーンの Dataplane V2 クラスタ
システムは、`default` サブネットを使用する `us-central1-a` のゾーンクラスタ `test-isolated` を構築し、GKE Dataplane V2 を有効にしなければならない（SHALL）。クラスタはマシンタイプ `e2-standard-2` のノードを 1 台だけ実行しなければならない（SHALL）。

#### Scenario: クラスタ構成を検査する
- **WHEN** オペレータがプロビジョニング済みクラスタのロケーション、ネットワーク、Dataplane、およびノードプールを検査する
- **THEN** クラスタ名は `test-isolated`、ロケーションは `us-central1-a`、サブネットは `default`、Dataplane V2 は有効であり、`e2-standard-2` のノードが 1 台だけ Ready である

### Requirement: ワークロード固有の Google Cloud 権限
テスト Deployment は Kubernetes Service Account を使用し、そのワークロード ID で Vertex AI 上の `claude-haiku-4-5@20251001` を呼び出し、BigQuery ジョブを実行できなければならない（SHALL）。ワークロードは長期 Google Cloud サービスアカウント鍵を保存してはならない（MUST NOT）。

#### Scenario: Claude モデルを認証付きで呼び出す
- **WHEN** オペレータが Deployment 内で Claude Agent SDK スクリプトに `https://github.com/74th の要約して` と渡す
- **THEN** スクリプトはワークロード ID を使って指定モデルを呼び出し、ワンショットの応答を標準出力へ返す

#### Scenario: BigQuery 公開データを照会する
- **WHEN** オペレータが Deployment 内で指定された Google Trends のクエリを実行する
- **THEN** BigQuery ジョブはワークロード ID で完了し、最大 100 件の結果を標準出力へ返す

### Requirement: 再現可能なエージェント用コンテナ
システムは Claude Agent SDK と BigQuery クライアントを実行できるコンテナイメージ、およびそのイメージを起動する `test` Deployment を提供しなければならない（SHALL）。Deployment は対話セッションを必須とせず、`kubectl exec` による各ワンショット検証を繰り返し受け付けなければならない（SHALL）。

#### Scenario: Claude スクリプトをワンショット実行する
- **WHEN** オペレータが `kubectl exec deploy/test -- python claude_agent_sdk.py "https://github.com/74th の要約して"` を実行する
- **THEN** コマンドは Agent SDK の最終応答を表示して正常終了する

#### Scenario: BigQuery スクリプトをワンショット実行する
- **WHEN** オペレータが `kubectl exec deploy/test -- python test_bq.py` を実行する
- **THEN** コマンドは指定クエリの結果を表示して正常終了する

### Requirement: ホスト許可リスト方式の外向き通信制御
システムは対象 Pod からの外向き通信をデフォルト拒否し、DNS、Google Cloud 認証、Vertex AI、BigQuery、および `github.com` への動作上必要な通信だけを許可しなければならない（SHALL）。許可はホスト名を基準として管理でき、許可対象にないインターネットホストを到達不能にしなければならない（SHALL）。

#### Scenario: 許可済み GitHub ホストへ接続する
- **WHEN** 通信ポリシー適用後に対象 Pod から `curl https://github.com/74th.keys` を実行する
- **THEN** HTTPS 要求は成功し、GitHub が公開する鍵データを返す

#### Scenario: Agent SDK が許可済み GitHub URL を処理する
- **WHEN** 通信ポリシー適用後に Claude Agent SDK へ `https://github.com/74th 要約して` と指示する
- **THEN** Agent SDK は GitHub と Vertex AI への必要な通信を行い、要約応答を返す

#### Scenario: 未許可ホストへの接続を拒否する
- **WHEN** 通信ポリシー適用後に対象 Pod から `curl http://checkip.amazonaws.com` を有限のタイムアウト付きで実行する
- **THEN** 要求は応答本文を取得できず失敗する

#### Scenario: 通信制御下でも BigQuery を利用する
- **WHEN** 通信ポリシー適用後に対象 Pod から BigQuery 検証スクリプトを実行する
- **THEN** Google Cloud 認証と BigQuery に必要な通信は許可され、クエリ結果が返る

### Requirement: 段階的で再実行可能な検証
システムは、人間が実行可能なスクリプトで、通信ポリシー適用前の機能確認、ポリシー適用、および適用後の成功・拒否確認を明確に分離しなければならない（SHALL）。各検証は期待結果と異なる場合に非ゼロで終了しなければならない（SHALL）。

#### Scenario: 制限前の基準動作を確認する
- **WHEN** オペレータが通信ポリシーを適用する前の検証スクリプトを実行する
- **THEN** GitHub 取得、Claude Agent SDK、および BigQuery クエリのすべてが成功し、その後にのみポリシー適用へ進める

#### Scenario: 制限後の許可と拒否を確認する
- **WHEN** オペレータが通信ポリシー適用後の検証スクリプトを実行する
- **THEN** GitHub 取得、Claude Agent SDK、および BigQuery は成功し、`checkip.amazonaws.com` への接続だけは失敗したものとして検証全体が成功する

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
システムは検証環境の Artifact Registry repository ID に既定で `test-gke-isolated` を使用しなければならず（SHALL）、image build、push、deploy、および cleanup で Terraform output が示す同じ repository を一貫して参照しなければならない（SHALL）。cleanup は現在の Terraform state が所有するリソースだけを対象とし、state に存在しない同名または類似名の repository を import または削除してはならない（MUST NOT）。

#### Scenario: 既定の repository を計画する
- **WHEN** オペレータが `artifact_repository_id` を上書きせずに Terraform plan を生成する
- **THEN** 作成対象の Artifact Registry repository ID は `test-gke-isolated` であり、image repository output にも `/test-gke-isolated` が含まれる

#### Scenario: 後段処理で Terraform output を使用する
- **WHEN** オペレータが image build、push、および workload deploy のスクリプトを実行する
- **THEN** すべての処理は Terraform の image repository output を使用し、別の repository ID をハードコードしない

#### Scenario: state 外の repository を cleanup 対象から除外する
- **WHEN** GCP 上に同名または類似名の repository が存在するが、現在の Terraform state にその resource address が存在しない
- **THEN** cleanup はその repository を import または削除せずに停止し、state が所有する削除対象だけをオペレータへ表示する

#### Scenario: 所有対象だけを削除する
- **WHEN** オペレータが確認済みの destroy plan を適用する
- **THEN** plan に含まれる repository ID は Terraform state が所有する `test-gke-isolated` であり、他の Artifact Registry repository は保持される
