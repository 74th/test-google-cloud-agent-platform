# GKE-disabled Terraform plan

Command:

```sh
terraform -chdir=terraform plan -input=false -lock=false \
  -var='container_image=<artifact-registry-image>@sha256:<64-hex-digest>' \
  -var='enable_gke=false'
```

Observed result: plan succeeded with `15 to add, 0 to change, 0 to destroy`. It contained only the experiment’s required APIs, Artifact Registry repository, Cloud Run service, dedicated runtime/test identities, Cloud Run IAM, and runtime log-writer binding. No `autopilot` cluster, `default` network, existing service, or destructive action appeared.

The applied image was the immutable digest recorded in the Cloud Run and GKE evidence. The plan showed Cloud Run `min_instance_count=0`, `max_instance_count=3`, IAM-only invoker membership, and `experiment=20260823-mcp-server` labels.
