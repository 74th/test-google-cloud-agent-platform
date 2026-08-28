# 20260822 Agent Gateway validation (retired)

この検証のTerraform管理対象は `common` へ移行しました。このディレクトリは過去の検証証跡を保存するためのもので、Agent Gateway、Agent Runtime、Agent Registry、IAM、Artifact Registryを作成・更新するTerraformやdeploy scriptは保持していません。

2026-08-28 に、承認済みのcleanupを実行しました。

- `agw-20260822-egress` を削除
- Terraform stateを空に確認
- Terraform外で作成された2つのAgent Runtimeを削除
- APIは `disable_on_destroy=false` により有効状態を維持

詳細な実行結果は [`common/evidence/20260828-cleanup.md`](../common/evidence/20260828-cleanup.md) を参照してください。過去のライブ検証結果は `evidence/` に保存されています。

共有基盤を構築する場合は、[`common/terraform`](../common/terraform) を使用します。利用側は、commonの `agent_gateway_id` outputを明示的な入力として受け取ります。
