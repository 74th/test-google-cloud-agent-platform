## Context

動機は [proposal.md](proposal.md) を参照する。現リポジトリには OpenSpec 設定以外の実装がなく、隣接する `20260801-agent-hosting` に Claude Agent SDK、Agent Platform カスタムコンテナ契約、Terraform、デプロイ／呼び出しスクリプト、およびテストの動作実績がある。ただし、そのクラウドリソースは削除済みであり、状態や名前を再利用できない。

ホスティング先は `nnyn-dev/us-central1`、Claude の Vertex AI 推論先は `nnyn-dev/global` とする。ネットワーク検証では、モデルの事前知識による回答と実際のページ取得を区別し、Gateway のポリシーおよびログとエージェント応答の双方を証跡にする必要がある。

## Goals / Non-Goals

**Goals:**

- 参考プロジェクトと同じ大枠のディレクトリ構成とランタイム契約を保ち、差分を Agent Gateway 統合と Web 取得検証に限定する。
- Terraform とスクリプトにより、構築、デプロイ、2 ケースのライブ検証、削除を再現可能にする。
- 許可リストとデフォルト拒否の境界を設定値と実行時証跡の両方で判定する。
- サービスアカウント認証で Claude Haiku 4.5 を利用し、長期 API キーを持ち込まない。

**Non-Goals:**

- 汎用的な本番用 Gateway 基盤、複数エージェント／テナント、認証済み GitHub API、または高可用性設計。
- `www8.cao.go.jp` に対する個別 deny ルールの作成。
- 2027 年の祝日データ自体の正確性検証や、外部ページ内容のキャッシュ。
- 参考プロジェクトの既存 Terraform state または削除済みリソースの復旧。

## Decisions

### 1. 参考プロジェクトを選択的に移植し、全リソースを `20260822-agent-gateway` 固有名にする

`agent_service/`、`scripts/`、`terraform/`、テスト、Dockerfile、Python プロジェクト設定という構成を踏襲する。Artifact Registry、サービスアカウント、エージェント表示名、Gateway／ポリシー名には `20260822` と `gateway` を含む固有の接頭辞または接尾辞を用い、Terraform state はこのリポジトリ内で新規作成する。

代替として参考ディレクトリを直接利用する方法は、削除済みリソースの state と命名への結合、検証結果の混同を招くため採用しない。全ファイルの無条件コピーも、時刻表スキルなど不要な振る舞いを残すため採用しない。

### 2. Agent Gateway の許可リストを単一のポリシー源にする

Gateway の Web 宛先ポリシーを既定拒否にし、検証対象として HTTPS の `github.com` を許可する。`www8.cao.go.jp` は設定に一切列挙しない。Claude Haiku 4.5 の推論に必要な Google 管理サービス経路は、Agent Platform／Gateway が管理経路として扱う場合はその仕組みを利用し、明示許可が必要な場合のみ対象を絞って追加する。実装時には利用可能な Google Cloud API と Terraform provider のスキーマを確認し、provider が未対応なら再現可能な `gcloud` または REST 呼び出しを Terraform から分離したセットアップスクリプトに封じ込め、その採用理由を README に記録する。

代替の「全許可＋内閣府だけ deny」は検証したいデフォルト拒否を満たさない。コンテナ内のプロキシやアプリケーションコードだけで拒否する方式も Agent Gateway 自体の検証にならないため採用しない。

### 3. Web 取得を明示したエージェント契約にする

Claude Agent SDK の一回のステートレス問い合わせを Agent Platform の `query`／`stream_query` 契約へ適合させる。システムプロンプトは、指定 URL を実際に取得してから回答すること、取得に失敗した場合は失敗を明記して記憶から内容を補完しないことを要求する。SDK に提供するツールは Web 取得に必要なものへ限定し、`permission_mode` とツール許可設定をテストで固定する。

代替として汎用シェルを自由に使わせる方法は、別クライアントや迂回経路で Gateway の評価を曖昧にするため採用しない。アプリ側で固定 HTTP リクエストだけを行う方法も Claude Agent SDK エージェントとしての実利用経路を検証できないため採用しない。

### 4. Vertex AI 認証とリージョンを明示的に固定する

コンテナには `CLAUDE_CODE_USE_VERTEX=1`、`ANTHROPIC_VERTEX_PROJECT_ID=nnyn-dev`、`CLOUD_ML_REGION=global`、`ANTHROPIC_MODEL=claude-haiku-4-5@20251001` を設定する。専用サービスアカウントへ `roles/aiplatform.user` を付与し、Agent Platform のサービスエージェントには専用 Artifact Registry の read のみを付与する。実際の Agent Gateway 構築に追加 IAM が必須な場合は、用途別 member として明示しテストで過剰な基本ロールがないことを検査する。

代替の Anthropic API キーは要件と異なり秘密情報管理も増やすため採用しない。モデル推論を `us-central1` に固定する方法は指定された `global` と Model Garden の利用条件に合わないため採用しない。

### 5. 成否は三層の証跡で判定する

検証コマンドは各プロンプトについて、入力、エージェント最終応答、終了状態をタイムスタンプ付きで保存する。加えて、デプロイ済み Gateway ポリシーのエクスポートと、利用可能な Gateway／Cloud Logging の宛先・allow/deny 判断ログを収集する。GitHub ケースは取得内容に基づく要約と allow 証跡、内閣府ケースはページ未確認を明記した応答と default-deny 証跡の組み合わせで合格とする。

代替の回答文だけによる判定は、幻覚やキャッシュをネットワーク成功と誤認できるため採用しない。ログだけによる判定も、利用者に返る振る舞いを確認できないため採用しない。

## Risks / Trade-offs

- [Agent Gateway または Terraform provider の公開 API が実装時点で変更されている] → バージョンを固定し、公式 API スキーマを確認する契約テストと、必要なら明示的な CLI/REST セットアップ経路を用意する。
- [`github.com` が別ホストの静的資産やリダイレクトを必要とし、ページの一部しか取得できない] → まず `github.com` 単体で本文取得を検証し、追加ホストなしで要約できない場合は失敗証跡を残す。追加許可は要件変更として明示的にレビューし、暗黙に広げない。
- [Vertex AI の管理通信までデフォルト拒否され、エージェント自体が起動できない] → 推論に必要な Google 管理経路だけを特定して許可し、Web 許可先とは分けて文書化・検査する。
- [モデルが内閣府ページを取得せず事前知識で祝日を回答する] → プロンプトで補完を禁止し、Gateway の deny ログを必須証跡にして回答内容単独では合格にしない。
- [外部サイトの内容や可用性が変動する] → 成功条件を文言の完全一致ではなく、取得成功、ページに根ざした要約、宛先ログで判定する。
- [クラウド検証に費用と削除漏れが生じる] → 固有ラベル／名前を付け、削除スクリプトと `terraform destroy` の順序、残存リソース確認を README に記載する。

## Migration Plan

1. ローカル単体テストと Terraform の静的検査を通す。
2. 新しい Terraform state で API、Artifact Registry、サービスアカウント、IAM、Gateway 関連リソースを作成し、出力値とポリシーを確認する。
3. コンテナをビルドして専用 Artifact Registry へ push し、固有名の BYOC エージェントを専用サービスアカウントでデプロイする。
4. Gateway 経由で GitHub ケースと内閣府ケースを順に実行し、応答、ポリシー、ログを証跡として保存する。
5. ロールバック時はエージェントを削除してから Terraform 管理リソースを destroy し、固有名／ラベルで残存物がないことを確認する。
