# Cloud Run common-egress 検証マトリクス（2026-08-28）

現行移行の Cloud Run 結果です。旧 Gateway の成功結果は比較用の historical baseline としてのみ扱います。

| ケース | 状態 | caller / effective identity | source / Gateway | destination / authorization layer | correlation ID | 期待結果 / 実測結果 / log reference |
| --- | --- | --- | --- | --- | --- | --- |
| 正常な Registry-resolved Cloud Run MCP | FAIL（Gateway前段） | operator ADC → Runtime `AGENT_IDENTITY` principal | Agent Runtime query / `common-egress` | Service `mcp-20260823-cloud-run` / Registry discovery・Gateway egress | Runtime APIから返却なし | Registry discovery成功を期待。実測 `SSLError`、Gateway `default_denied`。`networkservices.googleapis.com/gateway_requests` の `2026-08-28T04:16:23.199600Z`、hostname `240.0.0.2:443` |
| tokenなし | SKIP | consumer Runtime principal / endpoint caller未到達 | Cloud Run endpoint / `common-egress` 未到達 | Cloud Run Invoker | N/A（positive route blocked） | Cloud Run認証拒否を期待するが、移行後のGateway前段から到達できないため未実施。MCP execution logなし |
| wrong audience | SKIP | consumer Runtime principal / endpoint caller未到達 | Cloud Run endpoint / `common-egress` 未到達 | Cloud Run audience・Invoker | N/A（positive route blocked） | Cloud Run認証拒否を期待するが未実施。MCP execution logなし |
| endpoint未許可 identity | SKIP | unauthorized test identity / Runtime path未到達 | Cloud Run endpoint / `common-egress` 未到達 | Cloud Run Invoker | N/A（positive route blocked） | Cloud Run認可拒否を期待するが未実施。MCP execution logなし |
| 未登録またはegress未許可 destination | SKIP | consumer Runtime principal | Agent Runtime query / `common-egress` | unregistered/unbound destination / Gateway egress | N/A（positive route blocked） | Gateway default-denyを期待する専用probeは、現行Cloud Run positive pathの前段blocker解消後に実施 |

現行の正常ケースは endpoint authorization、Claude Tool selection、MCP executionへ進んでいないため PASSにしません。旧 Gateway での positive/negative backend結果は [`cloud-run-validation-20260823.md`](cloud-run-validation-20260823.md) と [`agent-runtime-gateway-mcp-20260824.md`](agent-runtime-gateway-mcp-20260824.md) にあり、`common-egress` の相関証拠には流用しません。
