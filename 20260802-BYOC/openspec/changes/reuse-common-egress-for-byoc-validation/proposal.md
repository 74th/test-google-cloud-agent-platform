## Why

Agent Runtime と Agent Gateway の関連付けには同一 project・direction 内の制約があり、旧 experiment の Gateway を増設する方式は成立しない。現行の `common-egress` を唯一の Gateway として再利用し、query-job proxy の GCS egress に必要な Registry Service と endpoint policy だけを BYOC 側の専用名で作り直して、長時間経路を再検証する。

## What Changes

- BYOC 検証用 Agent Runtime の作成時に、完全修飾リソース名で指定した `common-egress` を Agent-to-Anywhere Gateway として関連付ける。
- `common/terraform` の output、Terraform state、live API を照合し、project・location・Gateway 名が一致する場合だけデプロイを進める。
- 旧 experiment の `agw-20260822-*` Gateway、Registry Service、Endpoint policy を live inventory で確認し、残存する明示対象だけを削除する。現行の `common-egress` と `mcp-20260823-*` consumer は変更・削除しない。
- `common-egress` 本体は変更せず、query-job proxy が利用する `storage.googleapis.com` / `storage.mtls.googleapis.com` の専用 Agent Registry Service と、対象 Runtime の effective identity に限定した `roles/iap.egressor` endpoint policy をこの BYOC state で管理する。
- Runtime の実構成に `common-egress` が設定されたことを確認してから、通常4操作、短時間長時間ジョブ経路、960秒ジョブ、SDK と REST の比較を再実行する。
- BYOC Runtime の live GET では `revision`、`traffic`、`deployedModels` を要求せず、要求した immutable image digest が `spec.containerSpec.imageUri` と一致することを実行イメージの確認条件とする。
- Runtime 設定、操作結果、GCS 入出力、Cloud Logging の対応ログを試行単位で保存し、Gateway 関連付けの確認と BYOC 処理成功を別々に判定する。
- 検証後の `terraform destroy` は自動実行せず、対象を限定した plan を人間が確認して明示承認した場合だけ別工程で実行する。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `agent-query-verification`: BYOC Agent Runtime が外部所有の共有 `common-egress` を明示的に関連付けてデプロイされ、その実構成を確認した上で既存の通常4操作と長時間ジョブ検証を再実行できる要件を追加する。

## Impact

- `scripts/deploy_agent.py` または同等の宣言的 Runtime 構成、デプロイ結果の記録、関連テストが影響を受ける。
- README、検証スクリプト、非機密の evidence/results に共有 Gateway の preflight、Runtime 関連付け、再検証手順と結果を追加する。
- 外部依存は `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` と、その所有元である `common/terraform` の output/state である。BYOC 側は Registry Service、投影 Endpoint、endpoint IAM policy を追加管理する。
- Agent Registry と IAP endpoint IAM の resource/provider surface、および旧 experiment resource の削除により、Google Cloud の利用料金・権限変更が発生し得る。
- Agent Runtime、Artifact Registry、GCS、IAM、Cloud Logging の検証用リソースを再作成するため、Google Cloud の利用料金が発生し得る。
- `common` の Gateway、VPC、Network Attachment、および既存 `mcp-20260823-*` consumer は変更対象外である。
