# Local validation (2026-08-28)

The following checks completed successfully:

```text
uv run pytest -q                         33 passed
terraform -chdir=terraform init -input=false -reconfigure
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate    Success! The configuration is valid.
bash -n scripts/build_push.sh scripts/deploy.sh
docker build --tag agent-gateway-20260828-smoke .
GET http://127.0.0.1:18080/health       {"status":"ok"}
docker build --secret id=agent_gateway_roots,...
                                          completed without certificate material in build output
```

The container smoke used the committed Dockerfile and removed its local test
container afterwards. The Runtime ownership reconciliation used a state import
only and its subsequent Terraform plan was no-op; no cloud resource was
created, updated, or destroyed by that reconciliation. No destroy was run.
