# Spec Delta

## Purpose

Sandbox Pod から外部への通信を default deny にし、明示的に許可した宛先にだけ通信できるよう制限する。

## ADDED Requirements

### Requirement: Sandbox Pod の Egress を default deny にする
Sandbox Pod の Egress は、明示的に許可した宛先以外をすべて拒否しなければならない（SHALL）。クラスタ内 DNS と GKE メタデータサーバーへの通信は許可しなければならない（SHALL）。

#### Scenario: 未許可の宛先への通信が失敗する
- **WHEN** Sandbox Pod から許可リストにない宛先（例: `www.tohoho-web.com`）へ HTTPS 通信を試みる
- **THEN** 通信は有限時間内に失敗する

### Requirement: FQDN の許可リストで HTTPS を許可する
Sandbox Pod の HTTPS（TCP 443）Egress は、FQDNNetworkPolicy の許可リストにある宛先だけを許可しなければならない（SHALL）。許可リストは検証に必要な最小限とし、追加した FQDN は README に記録しなければならない（SHALL）。

#### Scenario: 許可した宛先への通信が成功する
- **WHEN** Sandbox Pod から許可リストにある宛先（例: `https://github.com`）にアクセスする
- **THEN** HTTP 応答を取得できる

### Requirement: Egress 制御は SandboxClaim から作られた Pod すべてに適用される
Egress 制御は、SandboxTemplate が Pod に付ける label を対象にしなければならない（SHALL）。新規作成された Sandbox にも、Resume された Sandbox にも同じように適用されなければならない（SHALL）。MCP Server の Pod には Sandbox 用の制限を適用してはならない（MUST NOT）。

#### Scenario: Resume した Sandbox にも適用される
- **WHEN** Suspend していたセッションを Resume し、未許可の宛先にアクセスする
- **THEN** 通信は拒否される
