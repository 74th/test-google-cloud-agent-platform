## Purpose

Claude Agent SDK を GKE 上で実行し、Vertex AI と BigQuery の必要な機能を保ちながら、外向き通信を宣言済みホストだけに限定できる再現可能な隔離環境を提供する。

## ADDED Requirements

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
