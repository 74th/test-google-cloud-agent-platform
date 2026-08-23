# Agent Registry validation evidence

Registration used `scripts/registry.sh` with `gcloud agent-registry services create` and the verified `JSONRPC` protocol binding. Separate services were created:

| Host | Service | Interface | Tool |
| --- | --- | --- | --- |
| Cloud Run | `mcp-20260823-cloud-run` | Cloud Run `/mcp` URL | `validate_echo` |
| GKE | `mcp-20260823-gke` | `http://mcp-20260823-mcp-server/mcp` | `validate_echo` |

`gcloud agent-registry mcp-servers search --location=us-central1 --search-string='displayName:20260823*'` returned both projected MCP servers after the normal short projection delay. Each result included its interface and `validate_echo` metadata. The Cloud Run discovered URL was used in the IAM-authenticated direct execution checks. The GKE discovered cluster-local URL was passed to a separate in-cluster validation Pod, which completed the MCP smoke flow.
