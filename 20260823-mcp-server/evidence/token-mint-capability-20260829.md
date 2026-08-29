# Runtime token-mint capability: 2026-08-29

The current Runtime uses the dedicated keyless caller path. No service-account
key or long-lived token is stored.

| Check | Result |
| --- | --- |
| Runtime effective identity | `agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/8548154799411953664` |
| Dedicated caller | `mcp-20260823-mcp-server-caller@nnyn-dev.iam.gserviceaccount.com` |
| Runtime → caller delegation | PASS: caller SA has `roles/iam.serviceAccountOpenIdTokenCreator` only for the Runtime principal; the successful Cloud Run run observed `generateIdToken` HTTP 200 |
| Caller endpoint use | PASS: caller SA has Cloud Run `roles/run.invoker`; the successful request used the exact Cloud Run audience |
| Direct AGENT_IDENTITY mint | NOT independently verified: the managed Runtime principal is not available as an operator impersonation target, so no direct-mint claim is made |
| Operator mint for separate invoker SA | PASS denial: `gcloud auth print-access-token --impersonate-service-account=mcp-20260823-invoker@nnyn-dev.iam.gserviceaccount.com` returned `PERMISSION_DENIED`, `iam.serviceAccounts.getAccessToken` |
| Operator mint of audience-bound token for separate invoker SA | PASS denial: `gcloud auth print-identity-token --impersonate-service-account=... --audiences=<Cloud Run audience>` returned the same permission denial |

The denied operator probes did not add IAM, create a key, or change the
Runtime. The direct-mint capability remains an explicit limitation rather than
being inferred from the delegated success.
