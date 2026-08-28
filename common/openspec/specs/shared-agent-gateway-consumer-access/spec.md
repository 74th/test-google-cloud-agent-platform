# shared-agent-gateway-consumer-access Specification

## Purpose

共有 Agent Gateway の default-deny と common/consumer の所有境界を維持しながら、承認済み Agent Runtime が Registry discovery と private GKE MCP endpoint を利用した事実を層別の非機密証跡で検証可能にする。

## Requirements

### Requirement: Gateway 拒否レイヤーの実証
システムは、Agent Runtime の Registry discovery に対応する Gateway request について、CONNECT destination、解決対象 endpoint、effective caller identity、matched rule、action、および enforcement layer を live API と Gateway log から特定しなければならない（SHALL）。`240.0.0.2:443` の意味を推測だけで Registry、GKE、または到達不能 endpoint と断定してはならない（MUST NOT）。

#### Scenario: default-denied を診断する
- **WHEN** Runtime query が `stage=registry_discovery` で失敗し、同時刻の `common-egress` log が `240.0.0.2:443` と `default_denied` を記録する
- **THEN** 診断結果は destination と Registry/control-plane request の対応を live resource、API、または同一試行の log で裏付ける
- **AND** endpoint 未登録、host 未許可、identity 未許可、protocol 不一致、および別の authorization layer を区別する

#### Scenario: 対応関係を証明できない
- **WHEN** Runtime invocation と Gateway request の対応または `240.0.0.2:443` の意味を一意に証明できない
- **THEN** システムは拒否レイヤーを未確定の blocker として報告する
- **AND** private GKE route または CA を原因として PASS/FAIL 判定しない

### Requirement: default-deny を維持した最小許可
システムは `common-egress` の default-deny を維持し、確認済みの Runtime principal に対して必要な Registry/control-plane endpoint と `gke.mcp-20260823.internal:443` だけを、確認済み protocol と resource scope で許可しなければならない（SHALL）。`allUsers`、project-wide Owner/Editor、catch-all host、広範囲な public allow、匿名 HTTP、および認証なしの外部 fallback を追加してはならない（MUST NOT）。

#### Scenario: common-owned allow を設計する
- **WHEN** 診断により `common-egress` 側の追加許可が必要と判明する
- **THEN** 変更案は対象 resource、IAM principal、host、port、protocol、適用範囲、既存 rule への影響、および rollback 方法を apply 前に列挙する
- **AND** Registry、Vertex AI、IAM Credentials、GKE MCP host のうち live request に必要と証明された endpoint だけを含める

#### Scenario: 許可対象の Runtime が接続する
- **WHEN** 承認済み Runtime principal が許可済み endpoint へ確認済み protocol で接続する
- **THEN** Gateway log は対象 allow rule と許可 action を記録する
- **AND** `default_denied` rule は許可リスト外の宛先に対して有効なままである

#### Scenario: 許可範囲外を拒否する
- **WHEN** 未承認 identity、未登録 host、異なる port、または異なる protocol で接続を試みる
- **THEN** Gateway は fail-closed で拒否する
- **AND** log は deny action と matched rule を判別可能にする

### Requirement: common-owned resource の変更保護
システムは Gateway、Gateway policy、authorization extension、VPC、subnet、および Network Attachment の所有権を `common` に維持しなければならない（SHALL）。consumer Terraform state はこれらを import、作成、更新、または削除してはならず（MUST NOT）、common 側の変更は read-only inventory、影響確認、対象限定 plan、および要求された承認境界を経なければならない（MUST）。

#### Scenario: 変更前の inventory を取得する
- **WHEN** common-owned resource の変更を検討する
- **THEN** システムは Gateway ID、etag、direction、protocol、Registry 関係、policy/extension、Network Attachment、DNS peering、および既存 consumer を read-only で記録する
- **AND** plan は置換、削除、既存 allow の後退、および対象外 resource の変更を明示する

#### Scenario: 最小変更を適用して read-back する
- **WHEN** 必要性が証明された対象限定 plan が承認境界を満たして適用される
- **THEN** システムは変更後の Gateway ID、etag、direction、protocol、policy rule、Registry 関係、Network Attachment、および DNS peering を live API から再取得する
- **AND** consumer state が common-owned resource を所有していないことを確認する

#### Scenario: destroy または範囲外変更を防止する
- **WHEN** plan または手順が `terraform destroy`、既存 Autopilot GKE の変更、common network の consumer 管理、または対象外 consumer への後退を含む
- **THEN** システムはその操作を実行せず blocker として報告する

### Requirement: private GKE endpoint 経路の検証
システムは Gateway の Network Attachment と DNS peering を利用して、`gke.mcp-20260823.internal` を `10.240.0.5` に解決し、Internal HTTPS Load Balancer から healthy backend、ClusterIP `10.242.0.20:80`、GKE MCP Pod へ配送できることを検証しなければならない（SHALL）。検証対象に Internet-facing frontend が存在してはならない（MUST NOT）。

#### Scenario: private frontend へ TLS 接続する
- **WHEN** Gateway 許可後の Agent Runtime invocation が GKE Registry Service の interface を解決して MCP endpoint へ接続する
- **THEN** private DNS は `gke.mcp-20260823.internal` を `10.240.0.5` に解決する
- **AND** TLS は hostname と trust chain を検証し、Internal HTTPS Load Balancer へ到達する
- **AND** backend health と server-side log は request が ClusterIP と MCP Pod へ配送されたことを示す

#### Scenario: private route の一層が失敗する
- **WHEN** DNS、Network Attachment、TLS、frontend、backend health、ClusterIP delivery のいずれかを実証できない
- **THEN** システムは最後に成功した層と最初に失敗した層を報告する
- **AND** operator-side または in-cluster smoke test を Agent Runtime E2E の代替証拠にしない

#### Scenario: public frontend を検査する
- **WHEN** GKE MCP endpoint の forwarding rule、Ingress、および Service を inventory する
- **THEN** 証跡は frontend が internal であり、public IP または Internet-facing frontend が存在しないことを示す

### Requirement: endpoint authorization の独立検証
システムは Registry discovery と Gateway allow とは別に、GKE MCP endpoint が承認済み Runtime identity を認可し、未承認 caller を拒否することを検証しなければならない（SHALL）。内部ネットワーク上にあることだけを endpoint authorization とみなしてはならない（MUST NOT）。

#### Scenario: 承認済み Runtime を認可する
- **WHEN** 許可済み Runtime identity が audience と対象 endpoint に適合する短命 credential を用いて MCP request を送る
- **THEN** endpoint authorization layer は request を許可する
- **AND** 証跡は identity、audience、resource、および authorization result を秘密値なしで示す

#### Scenario: 未承認 caller を拒否する
- **WHEN** credential がない、audience が異なる、または許可されていない identity が同じ endpoint へ request を送る
- **THEN** endpoint authorization layer は MCP Tool を実行せず request を拒否する
- **AND** private 到達性と authorization 拒否を別の判定として記録する

### Requirement: Agent Runtime E2E の相関証跡
システムは同じ correlation ID を用いて Runtime invocation、Registry Service/interface 解決、Gateway decision、private frontend、endpoint authorization、および GKE MCP Pod の server-side execution を追跡し、すべての層が成功した場合に限って Agent Runtime E2E を PASS としなければならない（SHALL）。

#### Scenario: governed GKE MCP E2E が成功する
- **WHEN** Agent Runtime が Registry Service `mcp-20260823-gke` から承認済み interface を解決し、登録 Tool を一度実行する
- **THEN** 証跡は Runtime resource と effective identity、Registry Service と resolved host、Gateway allow rule、endpoint authorization result、frontend/backend delivery、および Pod execution を同じ correlation ID で示す
- **AND** MCP Tool result と server-side execution log が一致する

#### Scenario: 中間層だけが成功する
- **WHEN** Registry discovery、Gateway allow、private TLS 到達、endpoint authorization、または MCP execution の一部だけを確認できる
- **THEN** システムは確認できた層だけを個別に PASS とする
- **AND** Agent Runtime E2E 全体を PASS としない

### Requirement: 非機密 evidence と明確な blocker
システムは検証コマンド、resource ID、時刻、caller、identity、route、authorization layer、判定、および秘密値を除いた log field を evidence に記録しなければならない（SHALL）。Gateway CA 本文、token、private key、credential、または Secret 内容を Markdown や log に保存してはならない（MUST NOT）。

#### Scenario: 成功 evidence を返す
- **WHEN** Agent Runtime E2E の全層が成功する
- **THEN** evidence は再現手順と各層の positive および必要な negative 判定を含む
- **AND** CA は存在、検証結果、または fingerprint だけを記録する

#### Scenario: 安全な完了が不可能である
- **WHEN** 必要な許可が API/provider で表現できない、owner 承認が必要、相関が不足する、または禁止された fallback なしでは検証できない
- **THEN** システムは正確な enforcement layer、必要な common-owned resource/policy、変更 owner、approval boundary、consumer が変更してはならない理由、および再試行に必要な最小変更を報告する
- **AND** 変更しない場合の FAIL または SKIP 判定を明示する
