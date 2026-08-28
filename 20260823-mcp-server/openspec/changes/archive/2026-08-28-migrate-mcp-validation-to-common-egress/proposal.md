## Why

Agent Runtime と Agent Gateway の関連付けには同一 project・governed direction 内の排他制約があり、旧 `agw-20260822-egress` は既に廃止されているため、現在の検証環境は再構築できない。`common` が所有する project 共通の `common-egress` を外部依存として利用する構成へ移行し、既に成功した Cloud Run MCP の governed E2E が共有 Gateway でも成立することを証跡付きで再確認する。

## What Changes

- Agent Runtime が参照する Gateway を、`common/terraform` の output と live API で確認した完全修飾 `common-egress` resource IDへ変更する。
- `common-egress` の project、location、governed access path、MCP protocol、Registry、VPC Network Attachment、active状態を apply 前に照合し、不整合時は consumer の変更を停止する。
- この検証環境は共有 Gateway、専用 VPC、subnet、Network Attachmentを作成・変更・削除せず、consumer側 Terraform state と所有境界を分離する。
- `common-egress` の TLS inspection root CA を取得して Agent Runtime image の trust storeへ組み込み、証明書本文やcredentialを evidenceへ保存しない。
- Runtimeの実構成、実効identity、Registry/IAP egress binding、endpoint IAMを再照合し、必要な consumer-owned resourceだけを再構築する。
- 過去に成功した Cloud Run MCP の Registry discovery、Gateway allow、Cloud Run認可、Claude Tool選択、MCP Tool実行を同一 correlation IDで再検証する。
- tokenなし、wrong audience、未許可identity、未登録またはegress未許可endpointのnegative testを再実行し、Gateway拒否後にMCP Server実行logがないことまで確認する。
- GKEについては `common-egress` のVPC接続を利用する Internal Load Balancer経路を別フェーズとして検証し、未構築の経路をPASSにしない。
- README、runbook、validation report、および日本語 evidenceを、旧Gateway名、共有resourceの責務境界、実測結果に合わせて更新する。
- 検証後の `terraform destroy` は実行せず、人間が対象限定planを確認して明示承認した場合だけ別工程で行う。

## Capabilities

### New Capabilities

- `shared-agent-gateway-integration`: 外部所有の共有 Agent Gateway を安全に参照し、TLS trust、Runtime関連付け、egress認可、MCP E2E、および共有resource非変更を検証する契約を定義する。

### Modified Capabilities

なし。

## Impact

- TerraformのGateway入力、Agent Runtime定義、IAM binding、plan/apply手順、およびstate所有境界が影響を受ける。
- Agent Runtime image build scriptとtrust store、Gateway preflight、validation runner、Terraform/static testが影響を受ける。
- README、`docs/runbook.md`、`validation-report.md`、`evidence/` の検証記録が影響を受ける。
- 外部依存は `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` と、`common/terraform` が所有するVPCおよびNetwork Attachmentである。2026-08-28のlive inventoryでは `AGENT_TO_ANYWHERE`、`MCP`、`us-central1` Registry、および `common-agent-gateway-attachment` が設定され、Gateway用authz policy/extensionは別resourceとして検出されていないため、実装時にRuntime関連付けとegress IAMの実挙動を改めて検証する。
- Agent Runtime、Artifact Registry、Cloud Run、Registry、IAM、Loggingのconsumer-owned resourceを再構築するため、Google Cloud利用料金が発生し得る。
- `common-egress` と既存consumerは変更対象外であり、この変更のTerraform stateやcleanup対象に含めない。
