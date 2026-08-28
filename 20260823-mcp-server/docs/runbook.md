# 20260823-mcp-server validation runbook

The former Gateway experiment was retired on 2026-08-28. This consumer does not
create or manage a Gateway. Supply `agent_gateway_id` explicitly from the
approved `common` Terraform output after the common Gateway is deployed. The
2026-08-28 consumer-only plan was reviewed and applied as a no-op; any future
apply still requires the same scope review.

This runbook creates only resources labeled `experiment=20260823-mcp-server` in project `nnyn-dev`. It never stores ID tokens, service-account keys, or Terraform secret values in the repository.

## Prerequisites

Install Node.js 20+, Docker, Terraform 1.13+, gcloud 581+ with the `beta` component, and `kubectl` with the GKE auth plugin. The operator needs permission to use the listed Google Cloud APIs, create the experiment resources, and (for the dedicated invoker test) mint an ID token as the test-invoker service account. The latter is an operator prerequisite and is not part of the workload IAM bindings.

## Local checks

```sh
npm ci
npm test
npm run check:tool-spec
docker build --tag mcp-20260823-mcp-server:0.1.0 .
docker run --detach --publish 18082:8080 --name mcp-20260823-local mcp-20260823-mcp-server:0.1.0
SMOKE_URL=http://127.0.0.1:18082 node scripts/local-smoke.mjs
SMOKE_URL=http://127.0.0.1:18082 node scripts/check-tool-spec.mjs http://127.0.0.1:18082/mcp
docker rm --force mcp-20260823-local
```

## Cloud Run phase

```sh
terraform -chdir=terraform init
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
terraform -chdir=terraform plan -var='enable_gke=false' -var='container_image=<immutable-digest>' -out=/tmp/mcp-20260823-disabled.tfplan
terraform -chdir=terraform apply /tmp/mcp-20260823-disabled.tfplan
terraform -chdir=terraform output
```

Build and push a versioned image to the Terraform-created repository, resolve its digest, and rerun `terraform apply` with the full `@sha256:` image reference. Use the URL from `terraform output` for the Cloud Run MCP check. Keep discovery and execution as separate commands; `scripts/registry.sh` provides `apply`, `search`, `describe`, and `delete` operations.

## GKE phase

Review a second plan with `enable_gke=true`, then apply it. The first trial keeps
the MCP Service as `ClusterIP` and validates it only from inside GKE. The
private-front-door trial adds a consumer-owned private DNS zone, internal IP,
proxy-only subnet, and `gce-internal` HTTPS Ingress backed by that ClusterIP.
Render and apply the backend manifests only after the cluster is Ready:

```sh
gcloud container clusters get-credentials mcp-20260823-mcp-server-gke --zone=us-central1-a --project=nnyn-dev
IMAGE_DIGEST='<immutable-digest>' GKE_WORKLOAD_SERVICE_ACCOUNT='<Terraform output email>' GKE_SERVICE_CLUSTER_IP='10.242.0.20' node scripts/render-manifests.mjs | kubectl apply -f -
kubectl -n 20260823-mcp-server rollout status deployment/mcp-20260823-mcp-server
kubectl -n 20260823-mcp-server wait --for=condition=complete job/mcp-20260823-validation
```

The GKE endpoint is intentionally cluster-local. Run the registry-discovered URL check from a Pod, not from a cluster-external client.

The internal HTTPS phase uses the reviewed hostname
`gke.mcp-20260823.internal`, private frontend `10.240.0.5`, and the
`mcp-20260823-mcp-server` ClusterIP backend. The Kubernetes TLS Secret used for
this test is self-managed and must be supplied out of band; do not commit its
private key or certificate body. A successful Pod-side check is only network,
TLS, and backend evidence. It is not Agent Runtime E2E until endpoint
authorization, `common-egress` allow, Claude Tool selection, and server-side
correlation are all present.

After the ClusterIP trial, supply an out-of-band TLS certificate and key for
`gke.mcp-20260823.internal` to the namespace, then apply the internal Ingress
template:

```sh
kubectl -n 20260823-mcp-server create secret tls mcp-20260823-gke-tls \
  --cert=<reviewed-certificate.pem> --key=<reviewed-private-key.pem>
sed -e 's/__INTERNAL_IP_NAME__/mcp-20260823-mcp-server-gke-ilb/g' \
    -e 's/__GKE_MCP_HOSTNAME__/gke.mcp-20260823.internal/g' \
  k8s/gke-internal-https.yaml.tmpl | kubectl apply -f -
kubectl -n 20260823-mcp-server describe ingress mcp-20260823-internal-https
```

The certificate/key paths above are placeholders and must not be committed.
The Ingress needs the consumer-owned `REGIONAL_MANAGED_PROXY` subnet created by
the Terraform ILB phase. Do not call a Pod-side smoke result an Agent Runtime
result.

## Governed Agent Runtime phase

Build and push both images by digest before applying the Runtime phase:

```sh
docker build --tag us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server/mcp-server:20260823-r1 .
docker push us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server/mcp-server:20260823-r1
docker build --file agent_runtime/Dockerfile --tag us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server-agent/agent-runtime:20260823-r1 .
docker push us-central1-docker.pkg.dev/nnyn-dev/mcp-20260823-mcp-server-agent/agent-runtime:20260823-r1
```

Resolve both `sha256` digests and pass them as `container_image` and
`agent_runtime_image`. Review the create-only plan before applying. The Runtime
uses `identity_type=AGENT_IDENTITY`, the reviewed
`projects/nnyn-dev/locations/us-central1/agentGateways/common-egress`
gateway, Registry viewer permission, and endpoint/MCP-server scoped
`roles/iap.egressor`. The fallback caller SA is keyless and receives only
target invocation roles; no SA key or Anthropic API key is supported.

The invocation input is `{ "target": "cloud-run"|"gke", "message": "..." }`.
URLs are rejected. Each invocation resolves the fixed Registry Service ID,
validates HTTPS/host/JSONRPC/Tool schema, mints the exact audience token, and
configures Claude's remote HTTP MCP server with a fresh authorization header.
The result is not PASS unless an SDK Tool event and a server-side correlation
log both exist.

The Runtime phase uses the shared `common-egress` Gateway because Google permits
only one active Agent Gateway per project and direction. This Terraform state
does not manage or delete that Gateway. Before planning, compare owner output and
the live Gateway without emitting the root certificate body:

```sh
python3 scripts/gateway_preflight.py \
  --owner-json <(terraform -chdir=../common/terraform output -json) \
  --live-json <(gcloud beta network-services agent-gateways describe \
    projects/nnyn-dev/locations/us-central1/agentGateways/common-egress \
    --project=nnyn-dev --format=json)
```

The consumer owns only its Registry Services/interfaces, endpoint-scoped IAM,
Runtime, and MCP workloads. It does not reuse 20260822 control-plane entries.
The GKE HTTPS phase is separately blocked until
`gke_mcp_hostname`, DNS control, trusted TLS, and IAP audience are reviewed.

## Evidence order

Keep sanitized command output in an operator-controlled evidence store. Repository evidence summaries are in `evidence/`; the final matrix is [validation-report.md](validation-report.md). Never paste bearer tokens or credential files into evidence.

## 2026-08-28 common-egress migration result（日本語）

共有 Gateway は `common` 所有であり、consumer は
`projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` を完全修飾
inputとして preflight します。CA は Gateway API から取得して BuildKit secret で
trust storeへ入れ、証明書本文は保存せず fingerprint と件数だけを記録します。
Runtime は `AGENT_IDENTITY` の effective identity を使い、Registry discovery、
Gateway egress、endpoint authorization、MCP実行を別責務として扱います。Registry
に登録されていることだけでは到達性や認可を意味しません。

再現する確認:

```sh
python3 scripts/gateway_preflight.py --owner-json <common output JSON> --live-json <sanitized live Gateway JSON>
terraform -chdir=terraform plan -refresh-only -no-color -detailed-exitcode <reviewed digest variables>
python3 scripts/check_scope.py <saved plan JSON>
terraform -chdir=terraform apply <reviewed plan>
```

2026-08-28 の Runtime query は `registry_discovery / SSLError` で停止し、同時刻の
Gateway request logは `240.0.0.2:443` と `default_denied` を示しました。このため
Cloud Runの no-token / wrong-audience / endpoint-unauthorized、egress-unbound、
Claude Tool selection、server-side MCP executionは移行後のPASSにしていません。
追加の共有ポリシー変更は common owner の承認が必要であり、consumer は推測で
`common-egress` や authz extension を変更しません。GKE は private DNS、trusted TLS、
internal HTTPS Load Balancer、endpoint authorization が未構築なので SKIP です。
