# Read-only project inventory

Collected 2026-08-23 with `gcloud` read-only list commands against project `nnyn-dev`. Values below contain no credentials or tokens.

## Commands

```sh
gcloud services list --enabled --project=nnyn-dev --format='value(config.name)'
gcloud compute regions list --project=nnyn-dev
gcloud compute networks list --project=nnyn-dev
gcloud compute networks subnets list --project=nnyn-dev
gcloud artifacts repositories list --project=nnyn-dev
gcloud run services list --project=nnyn-dev --platform=managed
gcloud container clusters list --project=nnyn-dev
```

## Sanitized observations

| Area | Observation |
| --- | --- |
| APIs | `agentregistry`, `artifactregistry`, `compute`, `container`, `iam`, `iamcredentials`, `logging`, `monitoring`, `run`, and `serviceusage` are enabled. |
| Region | `us-central1` is `UP`; it is selected for the experiment. |
| VPCs | Only the auto-mode `default` network was listed. |
| Subnets | The default network has its normal `10.128.0.0/20`-style regional ranges. The existing Autopilot subnet in `asia-northeast1` has Pod `10.16.128.0/17` and Service `10.17.0.0/22` secondary ranges. |
| Artifact Registry | Existing repositories are `gcr.io`, `agent-gateway-20260822`, and `claude-agent`; no `mcp-20260823-mcp-server` repository exists. |
| Cloud Run | No existing managed Cloud Run services were listed. |
| GKE | `autopilot` in `asia-northeast1` is `RUNNING`, `autopilot.enabled=true`, network `default`. It is explicitly out of scope and is not referenced by this Terraform root. |

## CIDR and naming decision

The dedicated VPC uses primary node range `10.240.0.0/20`, Pod secondary range `10.241.0.0/16`, and Service secondary range `10.242.0.0/20`. These do not overlap the inventoried ranges. Resource prefix `mcp-20260823-mcp-server` and label `experiment=20260823-mcp-server` identify experiment-owned resources.
