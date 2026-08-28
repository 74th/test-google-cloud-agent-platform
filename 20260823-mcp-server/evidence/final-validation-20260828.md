# 最終検査証跡（2026-08-28）

| 検査 | 結果 |
| --- | --- |
| `uv run pytest -q agent_test` | PASS、13 passed |
| `npm test` | PASS、2 files / 13 tests |
| `npm run check:tool-spec` | PASS、runtime definition と `toolspec.json` が一致 |
| `terraform fmt -check` / `terraform validate` | PASS |
| `openspec validate migrate-mcp-validation-to-common-egress --strict` | PASS |
| `openspec validate --specs --strict` | PASS、4 specs |
| common/shared drift plan | PASS、No changes。Terraform detailed exit code `2` は no-op の意味 |
| scope fixtures | PASS、4 forbidden casesを拒否、consumer-only caseを受理 |
| secret scan | PASS、PEM本文・private key・token literalなし |
| legacy executable scan | PASS、旧Gateway名はhistorical evidence/design説明だけ。consumer Terraform/scriptsに実行選択なし |
| teardown plan | PASS、37 consumer actionsのみ。scope guard PASS、apply/destroy未実施 |

この検査の `correlation_id` は invocationではないため `N/A (validation)` です。Runtime probeは別途 `registry_discovery` FAIL、GKEは private route未構築のSKIPとして記録しています。
