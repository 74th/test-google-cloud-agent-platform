#!/usr/bin/env bash
set -euo pipefail
: "${PROJECT_ID:?PROJECT_ID is required}"
: "${LOCATION:?LOCATION is required}"
: "${REPOSITORY:=byoc-query-verification}"
: "${TAG:=latest}"
IMAGE_URI="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/byoc-query-verification:${TAG}"
gcloud auth configure-docker "${LOCATION}-docker.pkg.dev" --quiet
docker build --tag "${IMAGE_URI}" . >&2
docker push "${IMAGE_URI}" >&2
printf '%s\n' "${IMAGE_URI}"
