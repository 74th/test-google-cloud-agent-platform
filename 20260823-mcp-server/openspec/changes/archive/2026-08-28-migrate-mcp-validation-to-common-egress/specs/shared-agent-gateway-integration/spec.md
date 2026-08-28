## Purpose

外部所有のproject共通Agent Gatewayをconsumer環境から安全に利用し、共有resourceの非変更、RuntimeのTLS trustと関連付け、egress認可、およびMCP実行結果を独立した証跡で検証できるようにする。

## ADDED Requirements

### Requirement: Shared Gateway is an explicit validated dependency
consumerは共有Agent Gatewayを完全修飾resource IDで明示的に受け取り、owner側の宣言出力とlive APIのproject、location、resource名、governed access path、MCP protocol、Registry、およびactive状態が一致する場合だけAgent Runtimeへ関連付けなければならない（SHALL）。

#### Scenario: common-egress preflight succeeds
- **WHEN** owner outputとlive APIの両方が `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` を示し、必要なGateway属性が一致する
- **THEN** consumerはその完全修飾IDをreview済みのRuntime deployment入力として使用できる

#### Scenario: Shared Gateway preflight detects drift
- **WHEN** owner outputとlive APIのID、location、direction、protocol、Registry、またはactive状態が一致しない
- **THEN** consumerのplanまたはapplyはRuntimeを作成・更新する前に失敗し、不一致を非機密の証跡へ記録する

### Requirement: Shared infrastructure remains externally owned
consumerのinfrastructure definitionとstateは `common-egress`、そのVPC、subnet、およびNetwork Attachmentを作成、更新、import、置換、または削除対象としてはならず（MUST NOT）、consumer-owned resourceだけを管理しなければならない（SHALL）。

#### Scenario: Consumer plan preserves common resources
- **WHEN** operatorが共有Gatewayへの移行planと適用後のdrift planを確認する
- **THEN** common所有resourceにadd、change、replace、destroy actionがなく、既存の他consumer設定も変更されない

#### Scenario: Consumer cleanup excludes common resources
- **WHEN** operatorがconsumer環境のcleanup planを生成する
- **THEN** `common-egress`、common VPC、subnet、Network Attachment、および他consumerはcleanup対象に含まれない

### Requirement: Runtime trusts only the selected Gateway inspection CA
Agent Runtime imageはpreflightで選択した共有GatewayのTLS inspection root CAをOS trust storeへ組み込み、旧GatewayのCA、固定token、Service Account key、または証明書本文をruntime設定やrepository evidenceへ残してはならない（MUST NOT）。

#### Scenario: Runtime image trusts common-egress interception
- **WHEN** `common-egress` を関連付けたAgent Runtimeが許可済みHTTPS endpointへ接続する
- **THEN** TLS inspection後の証明書chainが検証され、requestはGatewayのegress判定へ進む

#### Scenario: CA retrieval or trust installation fails
- **WHEN** 選択Gatewayのroot CAを取得できない、空である、またはbuilt image内のtrust検査に失敗する
- **THEN** image buildまたはdeploymentは停止し、CA本文を出力せず失敗stageを記録する

### Requirement: Consumer owns endpoint registration and egress bindings
consumerは必要なAgent Registry、Vertex AI、IAM Credentials、およびMCP Server endpoint登録をconsumer固有名で管理し、Agent Runtimeのeffective identityへ対象resource単位の `roles/iap.egressor` だけを付与しなければならない（SHALL）。廃止済み実験のRegistry endpointまたはIAM bindingへ依存してはならない（MUST NOT）。

#### Scenario: Runtime receives bounded egress access
- **WHEN** consumer-owned Agent RuntimeとRegistry endpoint群が作成される
- **THEN** Runtime effective identityは承認済みcontrol-plane endpointとMCP Serverにだけegress権限を持ち、project-wide bindingを持たない

#### Scenario: Legacy endpoint is absent
- **WHEN** 旧 `20260822` endpointが存在しない状態でconsumer環境を再構築する
- **THEN** consumerは旧data sourceへfallbackせず、consumer-owned endpointとbindingだけで構築を完了する

### Requirement: Governed Cloud Run MCP regression is proven end to end
Cloud Runのpositive E2EはAgent Runtimeの実構成に `common-egress` が関連付けられたことを確認した上で、Registry discovery、Gateway allow、endpoint認可、Claude Agent SDKのTool選択、およびMCP ServerのTool実行を同一correlation identifierで証明しなければならない（SHALL）。

#### Scenario: Cloud Run Tool executes through common-egress
- **WHEN** 許可されたRuntime identityがRegistry管理されたCloud Run Toolを必要とするpromptを実行する
- **THEN** Runtime設定、Registry Service ID、解決host、Gateway allow、Cloud Run caller認可、Claude Tool event、およびserver-side execution logを同一試行として相互参照できる

#### Scenario: A required evidence layer is missing
- **WHEN** Runtime応答が成功してもGateway判定、Claude Tool event、またはMCP Server実行logのいずれかを確認できない
- **THEN** E2E結果をPASSとして記録しない

### Requirement: Denials are attributed to the enforcing layer
negative検証はtokenなし、wrong audience、endpoint未許可identity、未登録またはegress未許可endpointを個別に実行し、Gateway拒否とendpoint拒否を区別しなければならない（SHALL）。拒否された試行についてMCP Toolが実行されていないことを確認しなければならない（SHALL）。

#### Scenario: Gateway denies unapproved destination
- **WHEN** Agent RuntimeがRegistry未登録またはegress権限のないendpointへ接続を試みる
- **THEN** Gateway段階で拒否され、対応correlation identifierのendpoint requestまたはMCP execution logが存在しない

#### Scenario: Cloud Run rejects invalid endpoint credential
- **WHEN** tokenがない、audienceが異なる、またはInvoker権限のないidentityがCloud Run endpointを呼び出す
- **THEN** Cloud Run認可段階で拒否され、MCP Tool execution logが存在しない

### Requirement: Private GKE validation uses the shared VPC path
GKEのAgent Runtime E2Eを実施する場合、`common-egress` のNetwork Attachmentから到達できるVPC internal HTTPS Load Balancerを経由し、backendのKubernetes ServiceとPodをInternetへ直接公開してはならない（MUST NOT）。経路が未構築または未検証の場合はSKIPまたはFAILとして記録しなければならない（SHALL）。

#### Scenario: Internal GKE Tool executes through common-egress
- **WHEN** private DNS、trusted TLS、internal Load Balancer、endpoint認可、およびGateway egress bindingが構成され、Agent RuntimeがGKE Toolを呼び出す
- **THEN** Gateway VPC接続、internal frontend、backend、ClusterIP Service、およびPod executionを同一correlation identifierで相互参照でき、外部公開resourceは存在しない

#### Scenario: Private route prerequisites are incomplete
- **WHEN** private DNS、trusted TLS、internal Load Balancer到達性、またはendpoint認可のいずれかが未確認である
- **THEN** operator-sideまたはin-cluster smoke testだけをAgent Runtime E2EのPASSとして扱わない

### Requirement: Validation records are reproducible and secret-free
検証記録は日本語で、caller、effective identity、source、Gateway resource、Registry Serviceまたはendpoint、destination、authorization layer、correlation identifier、期待結果、実測結果、および参照logを含めなければならない（SHALL）。token、private key、credential file、およびGateway certificate本文を保存してはならない（MUST NOT）。

#### Scenario: Evidence review
- **WHEN** operatorがREADME、validation report、およびevidenceを検査する
- **THEN** discovery、Gateway egress、endpoint authorization、Claude Tool selection、およびMCP executionが別々に判定され、秘密情報scanが成功する

#### Scenario: Validation completes without automatic teardown
- **WHEN** 構築と検証が完了する
- **THEN** resourceは人間のevidence確認のため保持され、明示承認なしに `terraform destroy` は実行されない
