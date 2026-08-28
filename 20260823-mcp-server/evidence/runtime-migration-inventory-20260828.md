# Agent Runtime 移行対象インベントリ（2026-08-28）

`us-central1-aiplatform.googleapis.com/v1/projects/nnyn-dev/locations/us-central1/reasoningEngines` を list し、各 resource を GET した結果を、Gateway 関連値だけ sanitized に記録した。画像 digest は識別用に残し、token や credential は取得・保存していない。

| Runtime display name | resource | identity/effective identity | Gateway association |
| --- | --- | --- | --- |
| `claude-agent-platform` | `5830184045782237184` | `AGENT_IDENTITY` / Agent Identity principal | なし |
| `20260822-agent-gateway-claude` | `4711743225822445568` | legacy service account | `agw-20260822-egress` |
| `byoc-query-verification-manual-20260822` | `6660394489590317056` | legacy service account | なし |
| `agent-platform-async-query-mode-poc` | `632810173471129600` | legacy service account | なし |
| `agent-platform-async-echo-poc` | `565256179060572160` | legacy service account | なし |
| `test-claude-agent-sample` | `524723782414237696` | legacy service account | なし |
| `kanazawa-timetable-claude-agent` | `4788401176510988288` | legacy service account | なし |
| `claude-session-store-verification` | `868017700884971520` | service agent | なし |

移行対象はこの consumer が今後作成する `mcp-20260823-runtime` であり、既存 Runtime は変更対象外。`common-egress` は live list で唯一の Agent Gateway として確認した。

過去の Runtime association で `Another Agent Gateway is already active or being created for this project and direction.` が返った事実を、project/direction の実務上の排他制約として扱う。ただし、これは Authz Extension が原因である証拠ではない。Authz policy/extension の所有権を推測して変更しない。
