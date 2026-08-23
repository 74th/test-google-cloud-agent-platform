# Agent Registry capability check

Collected 2026-08-23 from Google Cloud CLI `581.0.0` after installing the matching `beta` component. Agent Registry API is enabled in `nnyn-dev`.

## Verified command surface

```sh
gcloud agent-registry services create --help
gcloud agent-registry services update --help
gcloud agent-registry services delete --help
gcloud agent-registry mcp-servers list --help
gcloud agent-registry mcp-servers search --help
gcloud agent-registry mcp-servers describe --help
```

The selected registration surface is writable `services create/update/delete`, with `--mcp-server-spec-type=tool-spec`, `--mcp-server-spec-content`, and `--interfaces=protocolBinding=jsonrpc,url=...`. The runtime uses Streamable HTTP carrying JSON-RPC messages; the registry’s verified enum is `jsonrpc`. A manually registered Service is projected by Agent Registry as a read-only MCP Server. Discovery uses `mcp-servers list/search/describe`.

The concrete location is `us-central1`, selected because it is available and is also the Cloud Run/Artifact Registry region. The API reference printed by CLI help is `https://docs.cloud.google.com/agent-registry/overview` and the command surface uses `agentregistry/v1`.

No Terraform Google provider Agent Registry resource was found in the selected provider surface, so the repository isolates registration in `scripts/registry.sh`.
