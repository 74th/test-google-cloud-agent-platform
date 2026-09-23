# Spec Delta

## Purpose

Sandbox Pod から外部への通信を default deny にし、エージェントの動作に必要な宛先と、検証のために許可した宛先だけに通信できるよう制限する。

## ADDED Requirements

### Requirement: Sandbox Pod の Egress を default deny にする
Sandbox Pod の Egress は、明示的に許可した宛先以外をすべて拒否しなければならない（SHALL）。クラスタ内 DNS と、Workload Identity に必要な GKE メタデータサーバーへの通信は許可しなければならない（SHALL）。

#### Scenario: 未許可の宛先への通信が失敗する
- **WHEN** Sandbox Pod から `www.tohoho-web.com` への HTTPS 通信を試みる
- **THEN** 通信は有限時間内に失敗する

### Requirement: 必要な FQDN だけを許可する
Sandbox Pod の HTTPS（TCP 443）Egress は、FQDN で指定した許可リストの宛先だけを許可しなければならない（SHALL）。許可リストには、Vertex AI、GCS、検証用の `github.com` を含め、`www.tohoho-web.com` は含めてはならない（MUST NOT）。

#### Scenario: 許可した宛先への通信が成功する
- **WHEN** Sandbox Pod から `https://github.com/74th` にアクセスする
- **THEN** HTTP 応答を取得できる

#### Scenario: Vertex AI と GCS への通信が成功する
- **WHEN** Agent Runner が Vertex AI と GCS を呼び出す
- **THEN** Egress 制御が有効な状態でも応答の生成と JSONL の読み書きが成功する

### Requirement: Egress 制御は Sandbox 経由で作られた Pod に適用される
Egress 制御は、Sandbox コントローラが作成する Pod に付く label を対象にしなければならない（SHALL）。新規作成された Sandbox にも、再開された Sandbox にも同じように適用されなければならない（SHALL）。

#### Scenario: 再開した Sandbox にも適用される
- **WHEN** 一時停止していたセッションを再開して、未許可の宛先にアクセスする
- **THEN** 通信は拒否される
