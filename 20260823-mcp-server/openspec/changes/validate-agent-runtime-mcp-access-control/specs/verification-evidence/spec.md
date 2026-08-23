## MODIFIED Requirements

### Requirement: Minimum validation matrix
検証結果は少なくともAgent RuntimeによるCloud Run／GKE entryのdiscovery、接続情報validation、Agent Gatewayのallow／default-deny判定、Claude Agent SDKによる各hosting先のTool選択・実行、許可identityのendpoint認可成功、未認証・未許可identityの拒否、未登録URLの拒否、Registry entry更新・削除の反映、およびserver-side実行証跡を個別に扱わなければならない（SHALL）。既存のruntime単体、Tool specification整合性、Cloud Run scale-to-zero、およびGKE cluster-local検証も回帰項目として保持しなければならない（MUST）。

#### Scenario: 必須結果の確認
- **WHEN** 最終reportを検査する
- **THEN** discovery、governance、authorization、Claude Tool selection、MCP execution、hosting provenance、およびnegative testごとにstatus、期待結果、実測結果、identity、接続元、接続先、証跡が存在する

## ADDED Requirements

### Requirement: Layered authorization evidence
Registry IAM、Agent Runtime identity、endpoint IAMまたは認証機構、およびMCP Tool実行は別々の境界として検証され、ある境界の成功から別の境界の成功を推測してはならない（MUST NOT）。

#### Scenario: Registry閲覧可能かつendpoint未許可
- **WHEN** 検証identityがRegistry entryを取得できるが対象endpointの実行権限を持たない
- **THEN** reportはdiscoveryをPASS、authorizationとTool executionをFAILまたは期待どおりの拒否として別々に記録する

### Requirement: Claude execution evidence
Claude Agent SDKによるE2E PASSは、Agent Runtime invocation結果だけでなく、選択されたMCP Tool、Registry Service ID、解決されたhost、caller identity、correlation identifier、および対象hosting側logを伴わなければならない（SHALL）。

#### Scenario: 両hosting先のE2E PASS
- **WHEN** Cloud RunとGKEのAgent Runtime検証をPASSとして記録する
- **THEN** 各結果についてClaudeがToolを選択した証跡と、対応するMCP ServerがToolを実行した証跡を相互参照できる
