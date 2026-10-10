#!/usr/bin/env bash
set -euo pipefail

: "${GKE_PROJECT_ID:?Set GKE_PROJECT_ID explicitly}"
: "${GKE_LOCATION:?Set GKE_LOCATION explicitly}"
: "${SANDBOXD_IMAGE_REPOSITORY:?Set SANDBOXD_IMAGE_REPOSITORY explicitly}"

version="python-0.1.14"
image="${GKE_LOCATION}-docker.pkg.dev/${GKE_PROJECT_ID}/${SANDBOXD_IMAGE_REPOSITORY}/gke-pytest:${version}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

gcloud auth configure-docker "${GKE_LOCATION}-docker.pkg.dev" --quiet
docker build --pull \
  --file "${repo_root}/runtime/gke-pytest/Dockerfile" \
  --tag "${image}" "${repo_root}"
docker push "${image}"
digest="$(gcloud artifacts docker images describe "${image}" --format='value(image_summary.digest)')"
if [[ -z "${digest}" ]]; then
  printf 'Artifact Registry did not return a digest for %s\n' "${image}" >&2
  exit 4
fi
printf 'GKE_PYTEST_IMAGE=%s@%s\n' "${image%:*}" "${digest}"
