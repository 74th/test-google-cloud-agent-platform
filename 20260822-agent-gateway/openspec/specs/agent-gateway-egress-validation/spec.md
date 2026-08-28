# agent-gateway-egress-validation Specification

## Purpose

Claude Agent SDK の BYOC エージェントを Agent Gateway 配下で実行し、必要なモデル通信を維持しながら外向き Web 通信を許可リスト方式で制御できることを検証可能にする。

## Requirements

### Requirement: 再現可能で独立した検証環境
システムは、Google Cloud プロジェクト `nnyn-dev` の `us-central1` に、BYOC エージェント、実行サービスアカウント、および検証に必要な consumer-owned 関連リソースを Infrastructure as Code から作成または更新できなければならない（SHALL）。システムは `common/terraform` が所有し出力した fully qualified Agent Gateway ID を明示入力として使用しなければならず（MUST）、Agent Gateway またはその VPC、subnet、PSC Network Attachment、IAP Authz Extension、AuthzPolicy を新規作成、更新、import、または削除してはならない（MUST NOT）。作成する consumer-owned リソース名は `20260801-agent-hosting` のリソース名と重複してはならない（MUST NOT）。

#### Scenario: 空の環境への構築
- **WHEN** 操作者が文書化された前提条件を満たし、common の `agent_gateway_id` output を入力して Infrastructure as Code を適用する
- **THEN** 検証に必要な consumer-owned リソースが新しい名前で作成または更新され、デプロイに必要な識別子が出力される
- **AND** Agent Runtime は入力された Gateway ID を参照し、consumer の plan に Gateway または common-owned network/Authz resource の作成・変更・import・削除がない

#### Scenario: Gateway 入力が無効である
- **WHEN** 操作者が空、形式不正、または対象プロジェクト・リージョン外の Gateway ID を渡して plan またはデプロイを実行する
- **THEN** 操作は Gateway を作成または変更せずに失敗し、必要な common output を指定するよう報告する

#### Scenario: 検証環境の削除
- **WHEN** 操作者が文書化されたクリーンアップ手順を確認する
- **THEN** 手順は consumer-owned リソースと common-owned Gateway の所有境界を明示し、`terraform destroy` または共有 Gateway の削除を自動実行しない

### Requirement: 共有 Gateway に対する完全な egress 検証証跡
システムは、共有 Gateway を用いるライブ検証ごとに、認証済み caller、Runtime effective identity、fully qualified Gateway ID、対象 URL と宛先ホスト、Agent Runtime 呼び出し結果、Gateway または IAP の許可・拒否判断、アプリケーション側の取得ログを同一の検証識別子または時刻範囲で相関可能な形で保存しなければならない（SHALL）。Registry discovery、Gateway `ALLOWED`、private route 到達、または operator 側 smoke test だけを Agent Runtime MCP E2E 成功として扱ってはならない（MUST NOT）。

#### Scenario: GitHub 許可検証の証跡
- **WHEN** 操作者が共有 Gateway 配下のデプロイ済みエージェントへ GitHub 検証指示を送信する
- **THEN** 保存される証跡は caller、Runtime effective identity、Gateway ID、`github.com`、Agent Runtime の結果、許可判断、およびアプリケーション取得ログを相関できる

#### Scenario: 内閣府 default-deny 検証の証跡
- **WHEN** 操作者が共有 Gateway 配下のデプロイ済みエージェントへ未許可の内閣府 URL の検証指示を送信する
- **THEN** 保存される証跡は caller、Runtime effective identity、Gateway ID、`www8.cao.go.jp`、Agent Runtime の結果、default-deny 判断、およびアプリケーション取得失敗ログを相関できる

### Requirement: Claude Haiku 4.5 による BYOC エージェント実行
エージェントは Claude Agent SDK を使用し、Vertex AI Model Garden の `claude-haiku-4-5@20251001` を Google Cloud の認証情報で呼び出さなければならない（SHALL）。実行サービスアカウントには推論と Agent Platform 実行に必要な最小限の権限を付与し、Anthropic API キーに依存してはならない（MUST NOT）。

#### Scenario: デプロイ済みエージェントの呼び出し
- **WHEN** 認証済みの操作者が空でない日本語の指示をデプロイ済みエージェントへ送信する
- **THEN** エージェントは Claude Haiku 4.5 で指示を処理し、最終回答または安全に正規化された実行エラーを返す

### Requirement: 外向き Web 通信のデフォルト拒否
Agent Gateway の外向き Web 通信ポリシーはデフォルト拒否でなければならず（MUST）、検証対象の許可先として `github.com` を明示しなければならない（SHALL）。Claude Haiku 4.5 の推論に必須な Google 管理サービス通信は必要最小限で利用可能にしなければならない（SHALL）。未許可ホストごとの個別拒否ルールを用いてはならない（MUST NOT）。

#### Scenario: 許可先の確認
- **WHEN** デプロイされたポリシー設定を検査する
- **THEN** `github.com` は Web 通信の許可先として存在し、`www8.cao.go.jp` の許可または個別拒否ルールは存在せず、既定の動作が拒否になっている

#### Scenario: 任意の未許可ホストへの通信
- **WHEN** エージェントが許可リストに存在しない Web ホストへ接続しようとする
- **THEN** Agent Gateway はデフォルト拒否により接続を成立させない

### Requirement: GitHub への許可通信の実証
システムは、エージェントが `https://github.com/74th` の公開内容を取得し、その内容に基づく日本語の要約を返せることをライブ検証できなければならない（SHALL）。

#### Scenario: GitHub 組織ページの要約
- **WHEN** 操作者が「https://github.com/74th の内容を要約して」と指示する
- **THEN** エージェントは `github.com` への通信に成功し、取得したページの内容に基づく要約を返す
- **AND** 検証結果には呼び出し結果と許可された宛先を確認できる証跡が残る

### Requirement: 未許可の内閣府ホストへの通信拒否の実証
システムは、`www8.cao.go.jp` を許可リストへ追加せず、同ホストにあるページの取得がデフォルト拒否によって失敗することをライブ検証できなければならない（SHALL）。エージェントは事前知識から祝日一覧を補完して取得成功に見せかけてはならない（MUST NOT）。

#### Scenario: 2027年祝日ページの取得試行
- **WHEN** 操作者が「https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html は日本の国民の祝日についての広報ページだよ。この内容を見て、2027年の祝日を全て教えて。」と指示する
- **THEN** 対象ページへの接続または取得はデフォルト拒否により成功しない
- **AND** エージェントはページを確認できなかったことを明示し、ページから取得したものとして 2027 年の祝日一覧を回答しない
- **AND** 検証結果には呼び出し結果と拒否された宛先を確認できる証跡が残る
