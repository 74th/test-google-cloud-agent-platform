# Provider/API Gateway-ID contract (2026-08-28)

Read-only schema checks used Terraform 1.13.1, Google provider 7.45.0,
Google-Nightly 2026.4.8-7.27.0, and the Vertex AI v1 REST API.

The v1 Runtime create contract accepts the full Gateway reference at:

`spec.deploymentSpec.agentGatewayConfig.agentToAnywhereConfig.agentGateway`

The stable `google_vertex_ai_reasoning_engine` schema exposes
`spec.deployment_spec`, `container_spec`, `class_methods`, `identity_type`,
and `effective_identity`, but no `agent_gateway_config` or `agent_gateway`
attribute. The pinned `google-nightly` schema does expose
`spec.deployment_spec.agent_gateway_config.agent_to_anywhere_config.agent_gateway`.
The consumer therefore uses the nightly resource for the consumer-owned
Runtime and passes the validated full ID directly through Terraform. The v1
REST payload in `scripts/deploy_agent.py` remains an atomic fallback for
explicit deployment tooling; a PATCH-after-create or gateway-less retry is not
an accepted fallback.

Contract commands:

```text
terraform providers schema -json
jq '.provider_schemas[...].resource_schemas.google_vertex_ai_reasoning_engine...'
```

The common-owned Gateway remains outside this root. This file contains no
credential, token, certificate body, or secret value.
