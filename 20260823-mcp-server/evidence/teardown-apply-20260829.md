# Teardown application: 2026-08-29

The operator requested termination of this experiment. A fresh Terraform
destroy plan was generated from the live state and reviewed before apply.

## Applied scope

| Check | Result |
| --- | --- |
| Initial saved plan | `0 to add, 0 to change, 49 to destroy` |
| Initial plan scope | PASS: all managed actions were consumer resources; common Gateway/VPC/Endpoints were references only |
| Apply | The Runtime, Cloud Run, three consumer Registry Services, consumer IAM, repositories, GKE node pool/cluster, DNS, and consumer networking were destroyed |
| Delayed GKE cleanup | Two Kubernetes-created forwarding rules released after cluster deletion; the remaining VIP and two subnets were destroyed by a second 3-resource plan |
| Final Terraform state | Empty (`terraform state list` returned no managed resources) |
| Shared Gateway | Present: `projects/nnyn-dev/locations/us-central1/agentGateways/common-egress` |
| Shared VPC | Present: `common-agent-gateway-vpc` |
| Enabled APIs | Required APIs remained enabled because `disable_on_destroy=false` |
| Experiment kubeconfig context | Removed, including the stale `current-context` pointer |

The first apply temporarily stopped when GKE-created forwarding rules still
referenced the consumer proxy-only subnet and Gateway VIP. After the cluster
delete operation completed, a read-only inventory showed those forwarding
rules absent; the regenerated plan contained exactly the remaining three
consumer resources and applied successfully.

This teardown is irreversible through Terraform. Rebuilding the experiment
requires a new reviewed create plan and new image/runtime resources.
