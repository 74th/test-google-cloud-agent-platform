## 1. 共有 Gateway handoff の事前確認

- [x] 1.1 `common/terraform` の `agent_gateway_id` output と non-secret Gateway/Authz read-back を取得し、`nnyn-dev/us-central1` の `common-egress` であることを evidence に保存して確認する
- [x] 1.2 Agent Runtime の既存 association と direction を inventory し、active-Gateway 制約が consumer deployment を妨げないこと、または実際の blocker を Gateway を追加作成せずに記録して確認する
- [x] 1.3 現在の Agent Gateway API、Terraform provider、Agent Platform Runtime の Gateway-ID schema を確認し、consumer が fully qualified ID を参照するための対応経路を文書化して契約テストで確認する

## 2. Consumer Terraform とデプロイ構成

- [x] 2.1 必須の `agent_gateway_id` input、`nnyn-dev/us-central1` resource-name validation、および example/README の common output handoff を追加し、空・形式不正・別 project/location の入力が Gateway を作成せず失敗するテストで確認する
- [x] 2.2 retired Terraform root を consumer-owned Runtime、Artifact Registry、runtime identity、必要最小限の IAM、出力値だけを管理する構成へ戻し、Runtime が入力 Gateway ID を Agent-to-Anywhere egress に設定することを `terraform validate` と構成テストで確認する
- [x] 2.3 Gateway、VPC、subnet、PSC Network Attachment、IAP Authz Extension、AuthzPolicy の resource/import 定義が consumer にないことを静的テストで確認する
- [x] 2.4 deployment と invocation scripts を shared Gateway input、Runtime resource name、認証済み caller、Runtime effective identity を扱う構成に更新し、dry-run または command-generation tests で完全 resource name と秘密情報非出力を確認する
- [x] 2.5 `AGENT_GATEWAY_ROOT_CERTIFICATES` を container trust bundle に導入する既存 TLS inspection 経路を common Gateway 用に保持し、image build と CA trust contract test で確認する

## 3. Evidence runner とローカル検証

- [x] 3.1 validation runner を、Gateway ID、caller、Runtime effective identity、開始・終了時刻、URL/host、Runtime 応答、application fetch logs、Gateway/IAP logs を一つの non-secret evidence directory に相関保存するよう更新し、fixture tests で確認する
- [x] 3.2 GitHub allow 判定を、`https://github.com/74th` に基づく日本語要約、`github.com` allow 判断、application fetch 成功、caller/identity/Gateway 相関が全て揃う場合だけ PASS にするテストを追加する
- [x] 3.3 Cabinet Office negative 判定を、`www8.cao.go.jp` が policy に allow/host-specific deny として列挙されず、fetch failure、祝日一覧を補完しない応答、default-deny 判断、caller/identity/Gateway 相関が揃う場合だけ PASS にするテストを追加する
- [x] 3.4 MCP/Registry を利用する既存または追加の検証では、Registry Service ID/interface resolution、tool-selection、Gateway decision、endpoint authorization、server-side MCP log が揃わない限り Agent Runtime MCP E2E PASS を出さないテストを追加する
- [x] 3.5 Python tests、tool-spec/contract tests、container smoke、`terraform fmt -check`、`terraform init -input=false`、`terraform validate` を実行し、すべて成功することを確認する

## 4. Reviewed plan、ライブ再検証、引き渡し

- [x] 4.1 common Gateway input を用いた consumer Terraform plan を作成・レビューし、変更対象が consumer-owned resources に限定され、common-owned resource の create/update/import/destroy がないことを plan evidence で確認する
- [x] 4.2 承認済み consumer plan だけを apply し、BYOC Runtime を shared Gateway と Claude Haiku 4.5 で deploy して、認証済み基本呼び出しと Runtime/Gateway association の read-back を evidence で確認する
- [x] 4.3 shared Gateway 経由で GitHub allow、Cabinet Office default-deny、TLS inspection CA trust のライブ検証を実行し、各判定に caller、effective identity、Gateway ID、destination、Gateway/IAP decision、application log が揃うことを確認する
- [x] 4.4 dated evidence report と README を更新し、実行コマンド、common handoff、plan scope、各テストの証跡、未達の MCP E2E 条件、削除を実行していないことを第三者が追跡できるよう確認する
