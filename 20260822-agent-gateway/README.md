# 20260822 Agent Gateway shared-egress validation consumer

この checkout は、`common/terraform` が所有する共有 Agent Gateway を利用する
consumer 検証環境です。consumer は `nnyn-dev/us-central1` の Runtime、Artifact
Registry、Runtime identity、検証証跡を扱います。共有 `github.com` Registry
Service とその endpoint IAM、および共通 control-plane Service は
[`common`](../common/README.md) が所有します。
Gateway、VPC、subnet、PSC Network Attachment、Authz Extension、AuthzPolicy は
この Terraform root に定義しません。

## Common handoff

```bash
export PROJECT_ID=nnyn-dev
export LOCATION=us-central1
export AGENT_GATEWAY_ID="$(terraform -chdir=../common/terraform output -raw agent_gateway_id)"
```

AGENT_GATEWAY_ID は `projects/nnyn-dev/locations/us-central1/agentGateways/<name>` の完全修飾名でなければなりません。空、短縮名、別 project/location は Terraform
plan と deployment dry-run の両方で fail closed します。read-back は
[evidence/20260828-common-gateway-handoff.json](evidence/20260828-common-gateway-handoff.json)
に保存しています。

## Consumer plan

```bash
export IMAGE_URI='us-central1-docker.pkg.dev/nnyn-dev/agent-gateway-20260828/claude-agent-gateway@sha256:<immutable-digest>'
PLAN_FILE=evidence/terraform-consumer-$(date -u +%Y%m%d).tfplan \
  AGENT_GATEWAY_ID="$AGENT_GATEWAY_ID" IMAGE_URI="$IMAGE_URI" ./scripts/deploy.sh
terraform show "$PLAN_FILE"
```

`scripts/deploy.sh` は plan を保存するだけです。レビュー済み plan だけを、明示的な
人間の承認後に apply してください。`terraform destroy` は自動実行しません。

The stable Google provider does not carry the Runtime Gateway field, but the
pinned `google-nightly` provider does. Terraform therefore owns the
consumer Runtime and sets the Gateway atomically:

```hcl
deployment_spec {
  agent_gateway_config {
    agent_to_anywhere_config {
      agent_gateway = var.agent_gateway_id
    }
  }
}
```

For explicit API-level dry-run or fallback deployment checks,
`scripts/deploy_agent.py` uses the same atomic v1 payload:

```bash
uv run python scripts/deploy_agent.py \
  --project "$PROJECT_ID" --location "$LOCATION" \
  --agent-gateway "$AGENT_GATEWAY_ID" \
  --image-uri "$IMAGE_URI" \
  --display-name agent-gateway-20260828-claude \
  --dry-run
```

The dry-run output must contain
`spec.deploymentSpec.agentGatewayConfig.agentToAnywhereConfig.agentGateway` and must not contain credentials. The provider/API boundary is documented in
[evidence/20260828-provider-runtime-schema.md](evidence/20260828-provider-runtime-schema.md).

## Image trust and validation

The Gateway `agentGatewayCard.rootCertificates` are passed to the Docker build as
`AGENT_GATEWAY_ROOT_CERTIFICATES`; the Dockerfile installs them into the system
trust bundle. Do not disable TLS verification.

After an approved deployment, obtain the Runtime full name and effective identity
from Runtime GET, then run:

```bash
uv run python scripts/validate.py \
  --agent-resource "$AGENT_RESOURCE" \
  --gateway-id "$AGENT_GATEWAY_ID" \
  --caller "$CALLER_IDENTITY" \
  --runtime-effective-identity "$RUNTIME_EFFECTIVE_IDENTITY" \
  --policy terraform/egress-policy.yaml \
  --logs evidence/live/gateway-logs.json
```

GitHub passes only with the Japanese summary derived from `https://github.com/74th`,
github.com allow evidence, application fetch logs, and complete caller/identity/
Gateway correlation. The Cabinet Office case passes only with a fetch failure, no
fabricated holiday list, no policy listing for `www8.cao.go.jp`, and default-deny
Gateway evidence. Registry discovery or operator/in-cluster smoke tests alone are
not Agent Runtime MCP E2E; that result remains `unproven` unless every execution
layer is present.

## Evidence and cleanup boundary

The latest common-egress live validation is documented in
[evidence/20260829-common-gateway-live-validation.md](evidence/20260829-common-gateway-live-validation.md),
with raw correlated evidence under
[evidence/20260829T150541Z-common-authz-live](evidence/20260829T150541Z-common-authz-live).
It records GitHub allow, Cabinet Office default-deny, `ENFORCE` Authz, and
TLS interception/CA trust evidence. Agent Runtime MCP E2E remains unproven.
The post-validation consumer cleanup is recorded in
[evidence/20260829-consumer-destroy-plan.txt](evidence/20260829-consumer-destroy-plan.txt)
and did not target common-owned resources.

The dated handoff and provider checks are in `evidence/20260828-*.json` and
`evidence/20260828-*.md`. Existing Runtime consumers are inventoried rather than
modified. Consumer resources may be removed only after a human reviews the
consumer-owned plan; never delete or destroy the common Gateway from this checkout.
