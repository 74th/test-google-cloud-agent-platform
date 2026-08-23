# 20260823-mcp-server validation runbook

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

Review a second plan with `enable_gke=true`, then apply it. Render and apply the manifests only after the cluster is Ready:

```sh
gcloud container clusters get-credentials mcp-20260823-mcp-server-gke --zone=us-central1-a --project=nnyn-dev
IMAGE_DIGEST='<immutable-digest>' GKE_WORKLOAD_SERVICE_ACCOUNT='<Terraform output email>' node scripts/render-manifests.mjs | kubectl apply -f -
kubectl -n 20260823-mcp-server rollout status deployment/mcp-20260823-mcp-server
kubectl -n 20260823-mcp-server wait --for=condition=complete job/mcp-20260823-validation
```

The GKE endpoint is intentionally cluster-local. Run the registry-discovered URL check from a Pod, not from a cluster-external client.

## Evidence order

Keep sanitized command output in an operator-controlled evidence store. Repository evidence summaries are in `evidence/`; the final matrix is [validation-report.md](validation-report.md). Never paste bearer tokens or credential files into evidence.
