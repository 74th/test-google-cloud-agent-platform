# Cloud Run authorization negatives: 2026-08-29

These probes target the Cloud Run MCP endpoint directly. They are separate
from the positive Agent Runtime path.

| Case | Result | Evidence |
| --- | --- | --- |
| No token | PASS | `POST /mcp` with `tools/call` and correlation ID `mcp-negative-notoken-2026082901` returned HTTP 403. No Cloud Run log matched that correlation ID. |
| Unauthorized operator credential | PASS | An operator OAuth access token sent to the Cloud Run endpoint returned HTTP 401; no MCP response or application execution was observed. |
| Wrong audience with authorized caller identity | SKIP | The active operator could not impersonate the dedicated caller Service Account to mint a wrong-audience ID token. No IAM broadening or key creation was performed. |
| Separate unauthorized ID-token identity | SKIP | No approved keyless mint path for a separate unauthorized test identity was available. The operator-credential rejection above is retained as a bounded negative probe. |

The successful positive path independently used the Runtime's configured
keyless caller flow and exact Cloud Run audience. Tokens and credential values
are not stored in this evidence.

## Additional bounded mint attempt

The operator temporarily received a target-specific
`roles/iam.serviceAccountTokenCreator` binding on the consumer caller SA and
the Cloud Run runtime SA to obtain the two missing ID-token cases. The IAM
policy read-back showed the temporary binding, but both
`gcloud auth print-identity-token --impersonate-service-account` attempts were
denied at `iam.serviceAccounts.getAccessToken`. The temporary bindings were
removed immediately; final SA policies contain no operator Token Creator
binding. No token, key, or endpoint permission was retained. The wrong-audience
and separate-identity cases therefore remain SKIP rather than being inferred
from the failed mint attempt.

## Additional direct probe

At `2026-08-29T08:04:16.902413Z`, a direct `POST /mcp` without an
Authorization header returned HTTP 403. Cloud Run reported `The request was
not authenticated` and `Empty Authorization header value`; no MCP application
execution log was emitted. An audience-bearing ID token could not be minted by
the active operator account (`--audiences` requires a service-account identity),
so no wrong-audience token or additional IAM grant was introduced.
