# 20260822 Agent Gateway egress validation

This repository is a reproducible, test-only BYOC validation for Claude Agent SDK behind Google Cloud Agent Gateway. It creates resources only in `nnyn-dev/us-central1`; Claude Vertex AI inference is configured for `nnyn-dev/global`. Resource names and labels contain `20260822` and are independent of `20260801-agent-hosting`.

The security boundary is Agent Gateway in Agent-to-Anywhere mode. The gateway uses Agent Registry and IAP egress authorization: unregistered destinations are default-deny, while the registered `https://github.com` endpoint is explicitly authorized. The policy intentionally has no per-host deny rule.

## Prerequisites

- Google Cloud project `nnyn-dev`, billing enabled, and permissions to enable APIs, create IAM bindings, create Agent Gateway resources, and deploy Agent Runtime.
- `gcloud` 581.0.0 or newer with the Agent Gateway and Agent Registry command groups; authenticated ADC and an active gcloud account.
- Terraform 1.8 or newer, the Google provider 7.20 or newer, Docker, and `uv`.
- Claude Haiku 4.5 enabled in Vertex AI Model Garden. No Anthropic API key or Secret Manager secret is used.

Authenticate before any cloud operation:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project nnyn-dev
uv sync --extra test --extra deploy
```

The relevant settings are available in [.env.example](.env.example):

```bash
export PROJECT_ID=nnyn-dev
export LOCATION=us-central1
export VERTEX_PROJECT_ID=nnyn-dev
export VERTEX_REGION=global
export AGENT_GATEWAY_NAME=agw-20260822-egress
```

## Build the infrastructure

The official Agent Gateway Terraform resource is currently exposed by the pinned nightly provider because the stable provider does not yet contain the resource schema used by this validation. The provider choice and version are recorded in [terraform/versions.tf](terraform/versions.tf). The official reference module is [terraform-google-agent-gateway](https://github.com/GoogleCloudPlatform/terraform-google-agent-gateway).

```bash
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
cd ..
```

`terraform apply` creates API enablements, a dedicated Artifact Registry, the runtime service account, narrow IAM bindings, and the Google-managed Agent Gateway. It does not create or modify resources from `20260801-agent-hosting`.

## Build and deploy the BYOC agent

After `terraform apply`, `scripts/deploy.sh` configures Docker authentication, builds and pushes the dedicated image, creates the custom container Agent Runtime, and patches its `agentToAnywhereConfig` to the Terraform Agent Gateway resource. The image sets `CLAUDE_CODE_USE_VERTEX=1`, the `nnyn-dev` Vertex project, `global` inference region, and `claude-haiku-4-5@20251001`.

The script retrieves the Gateway root CA and passes it to the real image build. A bare `docker build` without that certificate is only a local, non-deploying build and is not part of the reproducible deployment procedure.

```bash
./scripts/deploy.sh
export AGENT_RESOURCE=projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID
```

The runtime contract is `POST /api/reasoning_engine` for `query`, `POST /api/stream_reasoning_engine` for `stream_query`, and `GET /health`. The SDK has only the `WebFetch` tool. It must fetch a requested URL before answering and must explicitly report a fetch failure without filling in content from memory.

## Register endpoints and authorize GitHub

Agent Gateway itself has no host-by-host deny list. [terraform/egress-policy.yaml](terraform/egress-policy.yaml) is the reviewable contract: `default_action: DENY`, with only `github.com` in the user-controlled Web allow list. The Google-managed services needed by Agent Platform (`agentregistry.googleapis.com`, `aiplatform.googleapis.com`, and `logging.googleapis.com`) are documented separately and are not arbitrary Web destinations.

First inspect the existing registry. Do not recreate an endpoint that is already listed:

```bash
gcloud agent-registry endpoints list --project=nnyn-dev --location=us-central1
```

If a required managed endpoint is absent, register it with the fixed URL and resource name encoded by the helper. The helper accepts only the three documented Google-managed names:

```bash
uv run python scripts/gateway.py register-managed --name agentregistry
uv run python scripts/gateway.py register-managed --name aiplatform
uv run python scripts/gateway.py register-managed --name logging
```

Register GitHub if it is absent, then use the endpoint ID returned by the list command and the deployed Agent Runtime identity principal when applying the IAP egressor binding. The identity principal is available only after `deploy.sh` creates the Runtime:

```bash
uv run python scripts/gateway.py register-github
gcloud agent-registry endpoints list --project=nnyn-dev --location=us-central1
uv run python scripts/gateway.py allow-github \
  --project=nnyn-dev --location=us-central1 \
  --endpoint=ENDPOINT_ID \
  --principal='principal://agents.global.org-PROJECT_NUMBER.system.id.goog/resources/aiplatform/projects/PROJECT_NUMBER/locations/us-central1/reasoningEngines/ENGINE_ID'
```

Do not register the unapproved test host. The intended evidence is a gateway decision log for that host with default-deny, not an individual deny policy.

## Run the live validation

Export the gateway configuration before the calls. The validation runner invokes both prompts first and then collects Gateway and IAP logs, so the evidence is tied to the calls it evaluates. Agent Gateway logs use monitored resource `networkservices.googleapis.com/Gateway`.

```bash
mkdir -p evidence/live
gcloud network-services agent-gateways describe agw-20260822-egress \
  --project=nnyn-dev --location=us-central1 --format=json > evidence/live/gateway.json
export VALIDATION_SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
uv run python scripts/validate.py \
  --agent-resource "$AGENT_RESOURCE" \
  --location us-central1 \
  --collect-after \
  --project nnyn-dev \
  --gateway agw-20260822-egress \
  --since "$VALIDATION_SINCE"
```

The runner creates a UTC timestamped directory containing each exact input, response, stderr, exit status, matched allow/deny log entries, the policy copy, the collected logs, and `summary.json`. The GitHub case requires a response referring to both GitHub and `74th`, plus an `allow` record for `github.com`. The 2027 holiday case requires a fetch-failure response without a holiday list, plus a `deny` record for `www8.cao.go.jp`. A response alone never proves network access.

## Evidence and report

For the completed live run, see [the dated validation report](evidence/20260822-report.md). It includes the saved gateway policy, both exact prompts, responses, exit states, Gateway/IAP log fields used for the decision, pass/fail results, and limitations such as external site availability. Do not include access tokens, ADC contents, API keys, or other secrets.

## Cleanup — human confirmation required

This run intentionally does not destroy resources automatically. After a human has checked the evidence:

1. Delete only the deployed Agent Runtime using its complete resource name:

   ```bash
   uv run python scripts/delete_agent.py --project=nnyn-dev --location=us-central1 --agent-resource="$AGENT_RESOURCE"
   ```

2. Confirm no `20260822-agent-gateway` resources remain in Agent Registry and no gateway calls are in flight.
3. From this repository's `terraform/` directory, review the plan and then run `terraform destroy` to remove only this state. Never run destroy from `20260801-agent-hosting` or another workspace.
4. Re-list the Artifact Registry, service account, and Agent Gateway using the `20260822` name and labels.

If deployment fails, inspect `terraform show`, the Agent Gateway export, Agent Registry endpoint state, the runtime deployment spec, and the Gateway log. Common causes are a disabled Model Garden model, missing `roles/aiplatform.user`, missing Artifact Registry reader binding, a mismatched region, an unregistered endpoint, or an untrusted BYOC gateway root certificate.
