## MODIFIED Requirements

### Requirement: Runtime access control
Cloud RunとGKEのMCP endpointは、Agent Runtimeから到達可能なHTTPS interfaceにおいてcaller identityを検証し、明示的に許可されたAgent Runtime identityの呼び出しだけを受け入れなければならない（SHALL）。未認証または未許可の呼び出しはMCP Tool実行前に拒否されなければならず（MUST）、GKEのcluster-local interfaceを外部Agent Runtime用の認可境界として扱ってはならない（MUST NOT）。

#### Scenario: Cloud Run の認証済み呼び出し
- **WHEN** Invoker権限を持つAgent Runtime identityが対象audienceの有効なcredentialを付けてCloud Run MCP endpointを呼び出す
- **THEN** Cloud Runはcallerを認可し、MCP requestをServerへ配送する

#### Scenario: Cloud Run の未認証拒否
- **WHEN** credentialがない、audienceが異なる、またはInvoker権限を持たないidentityがCloud Run endpointを呼び出す
- **THEN** 呼び出しはMCP Toolが実行される前に拒否される

#### Scenario: GKEのAgent Runtime呼び出し
- **WHEN** 許可されたAgent Runtime identityが有効なcredentialを付けてGKEの認証付きHTTPS endpointを呼び出す
- **THEN** GKEの認可境界はcallerを認可し、対象MCP Serviceへrequestを配送する

#### Scenario: GKEの未認証・未許可拒否
- **WHEN** credentialがない、対象が異なる、または許可されていないidentityがGKEのHTTPS endpointを呼び出す
- **THEN** 呼び出しはMCP Toolが実行される前に拒否される

## ADDED Requirements

### Requirement: Execution target is observable
Cloud RunとGKEの各MCP Serverは、秘密情報を含まないrequest correlationとserver-side logによって、Agent RuntimeのTool呼び出しがどのhosting先で実行されたかを検証可能にしなければならない（SHALL）。

#### Scenario: Hosting先の証明
- **WHEN** Agent RuntimeがCloud Run用またはGKE用Toolを実行する
- **THEN** agent結果と対応するhosting側logを同一のcorrelation identifierで関連付けられる
