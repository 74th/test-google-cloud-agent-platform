# common-egress consumer access baseline and blocker (2026-08-28)

This is a non-secret common-side evidence record. It contains resource IDs,
timestamps, identities, and selected structured log fields only. It does not
contain an access token, certificate body, private key, credential, or Secret
value.

## Scope and ownership

| Item | Current read-back | Owner/boundary |
| --- | --- | --- |
| Common Terraform backend/workspace | `common/terraform`, local backend `terraform.tfstate`, workspace `default` | common |
| Common Terraform resources | `google_compute_network.agent_gateway`, `google_compute_subnetwork.agent_gateway`, `google_compute_network_attachment.agent_gateway`, `google_network_services_agent_gateway.shared`, and four API enablement entries | common |
| Consumer state | `20260823-mcp-server/terraform`, workspace `default`; consumer GKE, ILB, DNS, Registry, Runtime, IAM, and application resources | consumer |
| Common VPC relation | Consumer has a data source for `common-agent-gateway-vpc` and creates its own `mcp-20260823-mcp-server-subnet` and `mcp-20260823-mcp-server-proxy-only`; it does not import the common VPC, common subnet, or Network Attachment | explicit cross-state relation; common VPC remains common-owned |
| Existing Autopilot GKE | `asia-northeast1/autopilot`, unrelated to this path | unchanged and out of scope |

The exact common-owned VPC, common subnet, Network Attachment, and Gateway
resource addresses occur only in the common state. The consumer's data source
and consumer-owned subnets are not evidence that it owns or imports those
common resources. The consumer state must not manage the common VPC, common
subnet, Network Attachment, Gateway, or any future common policy.

## Gateway and private path read-back

All values below are in project `nnyn-dev`, region `us-central1` unless a full
resource path says otherwise.

| Field | Value |
| --- | --- |
| Gateway | `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Gateway etag at read-back | `dJ8MLgd6POm1aIr09nFj08MG6sYT3_r_kQdbTE7p57E` |
| Google-managed path | `AGENT_TO_ANYWHERE` |
| protocol | `MCP` |
| Registry scope | `//agentregistry.googleapis.com/projects/nnyn-dev/locations/us-central1` |
| Network Attachment | `https://www.googleapis.com/compute/v1/projects/nnyn-dev/regions/us-central1/networkAttachments/common-agent-gateway-attachment` |
| Attachment connection | `ACCEPTED`, producer project/number `778161432651`, endpoint `10.243.0.3` |
| Attachment subnet | `projects/nnyn-dev/regions/us-central1/subnetworks/common-agent-gateway-subnet` |
| common VPC | `projects/nnyn-dev/global/networks/common-agent-gateway-vpc`, custom/REGIONAL |
| common subnet | `10.243.0.0/28`, purpose `PRIVATE` |
| private DNS zone | `mcp-20260823-mcp-server-private`, `mcp-20260823.internal.`, private |
| private DNS relation | attached to `common-agent-gateway-vpc`; `gke.mcp-20260823.internal.` resolves to `10.240.0.5` |

The Gateway export and provider schema expose no DNS-peering field, policy
attachment field, or allow-rule collection. The private DNS zone is a
consumer-owned relation attached to the common VPC; it is not a Gateway policy
read-back.

## Enforcement-surface inspection

Read-only checks on 2026-08-28 used Terraform `1.13.1`, Google provider
`7.45.0`, `google-nightly` `2026.4.8-7.27.0`, and gcloud `581.0.0`.

- The pinned `google_network_services_agent_gateway` schema contains
  `google_managed`, `network_config`, and `self_managed`, but no security
  policy, authorization policy, extension, or rule field.
- The Network Services v1 discovery schema contains Agent Gateway fields
  `agentConnectivityTemplate`, `agentGatewayCard`, `description`, `etag`,
  `googleManaged`, `networkConfig`, `protocols`, `registries`, and
  `selfManaged`; its methods are `get`, `list`, `patch`, `create`, and
  `delete`.
- The Network Security v1 discovery document exposes Gateway Security Policy
  `get`, `list`, `patch`, `create`, and `delete`, but no live regional Gateway
  Security Policy or rule exists in this project. Regional Authz Policy and
  Endpoint Policy lists are empty. Authz Extension, Extension Binding, and
  Producer Extension list calls for `us-central1` returned no resources.
- The current gcloud Agent Gateway surface provides `list`, `describe`,
  `export`, `import`, and `delete`; it has no allow-rule command. Exported
  configuration contains no policy/rule attachment.

Therefore no supported, attached, common-owned allow surface is proven. The
Network Security resources are not assumed to govern an Agent Gateway merely
because they exist in the provider.

## Runtime association and consumer impact inventory

The live Agent Runtime read-back found three current `AGENT_IDENTITY` Runtime
associations to this Gateway:

| Runtime | Effective identity suffix | Known use |
| --- | --- | --- |
| `2332905838663958528` (`mcp-20260823-runtime`) | `.../reasoningEngines/2332905838663958528` | GKE and Cloud Run Registry validation |
| `6473860142914863104` (`byoc-query-verification-common-egress-diagnostic-01`) | `.../reasoningEngines/6473860142914863104` | common-egress diagnostic |
| `6890548661562900480` (`byoc-query-verification-common-egress-20260828-01`) | `.../reasoningEngines/6890548661562900480` | common-egress validation |

Other listed Runtime resources in the project had no Agent Gateway association
in their live configuration. Recent Gateway log read-back for the associated
source project showed only `CONNECT` requests to `240.0.0.2:443` with status
403 and `default_denied`/`DENIED`; no positive allow rule was observed. Any
policy plan must therefore preserve the behavior of all three associations,
and cannot assume the GKE Runtime is the only affected consumer.

## Bounded GKE Registry probe

The helper `scripts/gateway_probe.py` generated probe ID
`35239d7c-9588-428b-b4ad-dc0cce5e1737` for a bounded probe. Credentials were
held in memory only and were not written to the evidence or repository.

| Field | Result |
| --- | --- |
| caller | operator ADC invoking the Runtime query API |
| Runtime | `projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528` |
| target Registry Service | `mcp-20260823-gke` |
| Runtime result | HTTP 400, `FAILED_PRECONDITION`, `stage=registry_discovery`, `Registry service lookup failed (SSLError)` |
| Runtime correlation | Runtime response did not return the generated probe ID |
| Gateway log | `2026-08-28T07:39:47.033322Z`, `CONNECT`, HTTP/1.1, 403 |
| Gateway structured fields | source project `776113568960`, hostname `240.0.0.2:443`, matched rule `default_denied`, action `DENIED` |
| join strength | provisional: same Runtime resource/source project and bounded UTC request window; no shared correlation field |

This proves a Registry-discovery failure and a same-window Gateway deny, but it
does not prove that `240.0.0.2` is a Registry endpoint, GKE endpoint, or a
user-configurable destination. It also does not prove a CA or origin-TLS
failure, because the request was denied before an origin connection was
observed.

## IAM and endpoint boundary

The consumer state read-back contains the effective Runtime principal

`principal://agents.global.proj-776113568960.system.id.goog/resources/aiplatform/projects/776113568960/locations/us-central1/reasoningEngines/2332905838663958528`

and a resource-scoped `roles/iap.egressor` binding for the consumer-owned GKE
MCP server. That binding is an endpoint/Registry authorization input; it is not
proof of Gateway egress authorization. The GKE front door currently accepts an
in-network TLS smoke request without an independent endpoint authorization
decision, so governed Agent Runtime E2E remains blocked. In-cluster and
operator-side checks are backend baselines only.

## Verdict and retry condition

| Layer | Verdict | Reason |
| --- | --- | --- |
| Registry discovery | FAIL | Runtime query failed at discovery |
| Gateway request correlation | BLOCKED | provisional time/resource/method join only |
| Gateway allow | FAIL | `default_denied` / 403 |
| `240.0.0.2` classification | BLOCKED | no live/API/official mapping to a user-configurable endpoint |
| private DNS/ILB/backend baseline | PASS | consumer-side private route and backend evidence only |
| endpoint authorization | BLOCKED | independent approved Runtime identity/audience decision not proven |
| Agent Runtime E2E | BLOCKED | all required layers and negative authorization case are not evidenced |

The exact enforcement resource and an idempotent mutation surface are not
proven. The owner is the managed Agent Gateway enforcement path until Google
documents or exposes a common-owned policy relation. No allow tuple, policy
mutation, consumer import, public frontend, authentication bypass, or cloud
write was performed. The minimum retry condition is a supported API/provider
surface that identifies the enforced policy/rule and accepts an etag-guarded,
exact host/port/protocol/principal/resource-scoped update, followed by explicit
human approval of the saved common plan.

## Reproduction and safety checks

```text
terraform -chdir=terraform workspace show
terraform -chdir=terraform state list
terraform -chdir=terraform providers schema -json
gcloud network-services agent-gateways describe common-egress --project=nnyn-dev --location=us-central1 --format=json
gcloud logging read 'logName="projects/nnyn-dev/logs/networkservices.googleapis.com%2Fgateway_requests"' --project=nnyn-dev --freshness=1h --limit=20 --format=json
python3 scripts/gateway_probe.py --runtime-id=2332905838663958528 --registry-service=mcp-20260823-gke --target=gke
```

The common validation workflow runs the scope guard and redaction fixture
tests. No apply was performed for this change, and no destructive operation
was performed.

## DRY_RUN IAP Authz trial

On 2026-08-28, the common owner approved the scoped Authz trial. The preflight
inventory found no regional Authz Extension or AuthzPolicy, so no existing
extension was deleted. The reviewed Terraform plan created only the already
enabled `networksecurity.googleapis.com` service entry, the following IAP
extension, and its Gateway-targeted policy; it had zero changes or deletes.

| Resource | Live read-back |
| --- | --- |
| Authz Extension | `projects/nnyn-dev/locations/us-central1/authzExtensions/common-egress-iap-authz` |
| Extension configuration | `iap.googleapis.com`, `timeout=1s`, `failOpen=true`, `iamEnforcementMode=DRY_RUN`, `iapPolicyVersion=V1` |
| AuthzPolicy | `projects/nnyn-dev/locations/us-central1/authzPolicies/common-egress-iap-policy` |
| Policy configuration | `REQUEST_AUTHZ`, `CUSTOM`, target only `common-egress`, custom provider only the extension above |
| Terraform reconciliation | post-apply refresh returned `No changes` |
| Unchanged Gateway | same ID and etag `dJ8MLgd6POm1aIr09nFj08MG6sYT3_r_kQdbTE7p57E`, `AGENT_TO_ANYWHERE`, `MCP`, regional Registry scope, and Network Attachment |

The bounded Runtime probe `73662a5e-bb7b-4462-8e59-381e63d361fa` started at
`2026-08-28T08:29:57Z`. Its direct Runtime response was `400
FAILED_PRECONDITION` at `stage=tool_execution`: Claude returned without a
remote Tool execution event. Gateway logs delivered shortly afterwards still
provide the required same-window path evidence:

| Timestamp (UTC) | Destination / operation | Gateway decision | Result |
| --- | --- | --- | --- |
| `08:29:59.835895` | `agentregistry.googleapis.com`, Registry GET | policy `ALLOWED`; default Gateway rule `ALLOWED` | HTTP 200 |
| `08:30:00.385720` | `iamcredentials.googleapis.com`, ID-token mint | policy `ALLOWED`; default Gateway rule `ALLOWED` | HTTP 200 |
| `08:30:06.130257` | `gke.mcp-20260823.internal/mcp`, MCP `initialize` | policy `ALLOWED`; default Gateway rule `ALLOWED` | HTTP 503 |
| `08:30:07.046112` | `aiplatform.googleapis.com`, Claude prediction | policy `ALLOWED`; default Gateway rule `ALLOWED` | HTTP 200 |

For each listed allow, `authzPolicyInfo` identifies the common policy and
records `result=ALLOWED`; the GKE request also identifies the consumer MCP
server resource. This proves the IAP Authz attachment is evaluated on the
Gateway and no longer blocks Registry discovery. It does not make an E2E
claim: the first observed failure after Gateway authorization is the
consumer-owned private GKE origin's HTTP 503. The same window also includes
successful `CONNECT 240.0.0.2:443` records, but still contains no documented
or same-request field that classifies that address; its semantic identity
remains blocked.

## Terraform plan and approval boundary

The read-only checks produced:

```text
terraform -chdir=terraform plan -refresh-only -input=false -no-color -detailed-exitcode -out=/tmp/common-egress-refresh-20260828.tfplan
terraform -chdir=terraform plan -input=false -no-color -out=/tmp/common-egress-reviewed-20260828.tfplan
python3 scripts/check_scope.py /tmp/common-egress-reviewed-20260828.tfplan.json
```

The refresh-only plan reported the accepted Network Attachment endpoint
transition from `10.243.0.2`/producer `1038138766035` in stale state to live
`10.243.0.3`/producer `778161432651`; it proposed no remote resource action.
The normal saved plan proposed no resource action and only populated the five
non-secret outputs `agent_gateway_etag`, `agent_gateway_protocols`,
`agent_gateway_registries`, `agent_gateway_governed_access_path`, and
`agent_gateway_network_attachment`. Scope guard passed for the normal plan.

Pre-change read-back presented for owner approval:

- Gateway `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
- etag `dJ8MLgd6POm1aIr09nFj08MG6sYT3_r_kQdbTE7p57E`
- `AGENT_TO_ANYWHERE`, `MCP`, Registry scope `nnyn-dev/us-central1`
- Network Attachment `common-agent-gateway-attachment`, accepted endpoint
  `10.243.0.3`, common subnet `10.243.0.0/28`

No apply is authorized by this record. The plan remains at the required human
approval boundary; the unproven managed enforcement surface is also a blocker
for creating an allow-rule plan.
