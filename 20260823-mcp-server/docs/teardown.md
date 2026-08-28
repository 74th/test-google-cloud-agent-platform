# Teardown and cleanup review

Cleanup targets are limited to the two Agent Registry services, namespace `20260823-mcp-server`, and Terraform state resources whose names/labels contain the experiment identifier. The existing `autopilot` cluster, default VPC, existing repositories, and all non-experiment Registry services are out of scope.

## Registry and Kubernetes cleanup

```sh
PROJECT_ID=nnyn-dev REGISTRY_LOCATION=us-central1 ./scripts/registry.sh delete cloud-run
PROJECT_ID=nnyn-dev REGISTRY_LOCATION=us-central1 ./scripts/registry.sh delete gke
kubectl delete namespace 20260823-mcp-server
```

## Terraform destroy review

First produce a destroy plan with the actual image digest and GKE enabled:

```sh
terraform -chdir=terraform plan -destroy -input=false \
  -var='container_image=<same immutable digest>' \
  -var='enable_gke=true' \
  -out=/tmp/mcp-20260823-destroy.tfplan
terraform -chdir=terraform show -no-color /tmp/mcp-20260823-destroy.tfplan
```

The reviewed target set must be limited to `mcp-20260823-mcp-server*`, `mcp-20260823-*` service accounts, the experiment API state entries with `disable_on_destroy=false`, and the manually registered services above. Do not apply a destroy plan containing `autopilot`, `default`, `common-egress`, or `claude-agent`. Apply the reviewed plan only after explicit operator confirmation:

```sh
terraform -chdir=terraform apply /tmp/mcp-20260823-destroy.tfplan
```

The repository intentionally does not disable APIs on destroy.
