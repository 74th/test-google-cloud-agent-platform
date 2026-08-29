# Teardown and cleanup review

Cleanup targets are limited to the three consumer-owned Agent Registry services, namespace `20260823-mcp-server`, and Terraform state resources whose names/labels contain the experiment identifier. The existing `autopilot` cluster, shared `common-egress` Gateway, common VPC/subnet/Network Attachment, existing repositories, and all non-experiment Registry services are out of scope.

## Registry and Kubernetes cleanup

```sh
PROJECT_ID=nnyn-dev REGISTRY_LOCATION=us-central1 ./scripts/registry.sh delete cloud-run
PROJECT_ID=nnyn-dev REGISTRY_LOCATION=us-central1 ./scripts/registry.sh delete gke
PROJECT_ID=nnyn-dev REGISTRY_LOCATION=us-central1 \
  CLOUD_RUN_REGISTRY_SERVICE=mcp-20260823-gke-http-diagnostic \
  ./scripts/registry.sh delete cloud-run
kubectl delete namespace 20260823-mcp-server
```

The third command uses the script's Cloud Run selector only as a bounded
experiment-service deletion; verify the exact service ID before running it.
The shared common Registry endpoints and the `common-egress` Gateway are never
deleted from this workspace.

## Terraform destroy review

First produce a destroy plan with the actual image digest and GKE enabled:

```sh
terraform -chdir=terraform plan -destroy -input=false \
  -var='container_image=<same immutable digest>' \
  -var='enable_gke=true' \
  -out=/tmp/mcp-20260823-destroy.tfplan
terraform -chdir=terraform show -no-color /tmp/mcp-20260823-destroy.tfplan
```

The reviewed target set must be limited to the experiment-prefixed Cloud Run,
GKE, Registry, IAM, DNS, address, repository, Runtime, and API-state resources
shown by the saved plan. Do not apply a destroy plan containing `autopilot`,
the default VPC, `common-egress`, common endpoint IDs, or `claude-agent`.
The 2026-08-29 plan contained 49 delete actions and passed the consumer scope
guard after the guard's default-network check was made field-aware. Apply the
reviewed plan only after explicit operator confirmation:

```sh
terraform -chdir=terraform apply /tmp/mcp-20260823-destroy.tfplan
```

The repository intentionally does not disable APIs on destroy.

## Applied teardown status

The reviewed teardown was applied on 2026-08-29 after operator request. The
consumer Terraform state is empty, the experiment GKE context was removed from
kubeconfig, and the shared `common-egress` Gateway, common VPC, common
Registry endpoints, and enabled APIs remain. See
[`evidence/teardown-apply-20260829.md`](../evidence/teardown-apply-20260829.md).
