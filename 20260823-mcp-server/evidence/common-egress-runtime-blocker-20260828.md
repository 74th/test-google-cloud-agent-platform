# common-egress Runtime probe blocker（2026-08-28）

## 試行

| 項目 | 値 |
| --- | --- |
| caller | operator ADC が Runtime query API を呼び出した |
| source | Agent Runtime `projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528` |
| Runtime identity | `AGENT_IDENTITY`; effective identity は Runtime resource principal |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| destination | Registry Service `mcp-20260823-cloud-run` の discovery path |
| expected | Registry discovery が Gateway を通過し、次の endpoint 認可へ進む |
| actual | Runtime API `FAILED_PRECONDITION`; detail `stage=registry_discovery`, `Registry service lookup failed (SSLError)` |
| Gateway evidence | `projects/nnyn-dev/logs/networkservices.googleapis.com%2Fgateway_requests`、`2026-08-28T04:16:23.199600Z` |
| Gateway decision | hostname `240.0.0.2:443`、matched rule `default_denied` |
| endpoint/app evidence | 同時刻に Runtime HTTP 422。Cloud Run/MCP execution log は確認できない |

再現コマンド:

```sh
curl --max-time 180 -sS \
  -H "Authorization: Bearer <ADC token; do not save>" \
  -H 'Content-Type: application/json' \
  -X POST \
  --data '{"class_method":"query","input":{"target":"cloud-run","message":"execute the registered validation tool once"}}' \
  'https://us-central1-aiplatform.googleapis.com/v1/projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528:query'
```

結果は Registry discovery 段階の fail-closed でした。今回の証拠には Runtime API が返した相関 ID はなく、Gateway log の `agentGatewayInfo` も空でした。そのため、Gateway allow、Cloud Run authorization、Claude Tool selection、MCP execution を PASS として結び付けません。

この blocker は `common-egress` の Gateway authorization path の実測結果として記録します。共有 Gateway、authz policy/extension、VPC、Network Attachment は変更していません。追加の shared-owner action が承認されるまで 5.4 と Cloud Run/GKE Agent Runtime E2E は未完了です。operator-side または in-cluster smoke test はこの blocker を解消する証拠ではありません。

Cloud Run の現行 positive/negative ケースの期待値、未実施理由、`correlation_id=N/A` の扱いは [`cloud-run-common-egress-validation-20260828.md`](cloud-run-common-egress-validation-20260828.md) に分離して記録しています。
