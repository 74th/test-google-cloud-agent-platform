"""Non-destructive checks for the permissions needed by query-job proxying."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _uri_parts(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError("GCS URI must be gs://bucket/object")
    return parsed.netloc, parsed.path.lstrip("/")


def check_gcs_object_access(storage_client: Any, uri: str) -> dict[str, Any]:
    """Probe object metadata and return a safe, permission-oriented result."""
    bucket_name, object_name = _uri_parts(uri)
    try:
        exists = bool(storage_client.bucket(bucket_name).blob(object_name).exists())
    except Exception as exc:
        return {
            "ok": False,
            "permission": "storage.objects.get",
            "error_type": type(exc).__name__,
        }
    return {"ok": True, "permission": "storage.objects.get", "exists": exists}


def check_service_usage(session: Any, project: str, service: str = "storage.googleapis.com") -> dict[str, Any]:
    """Check ``serviceusage.services.use`` without recording response bodies."""
    # ``serviceusage.services.use`` is a project-level permission. The
    # Service Usage API does not expose a per-service testIamPermissions
    # method, so use the Resource Manager project IAM test endpoint.
    endpoint = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}:testIamPermissions"
    try:
        response = session.post(endpoint, json={"permissions": ["serviceusage.services.use"]}, timeout=30)
        status = int(getattr(response, "status_code", 0))
        if status >= 400:
            return {"ok": False, "permission": "serviceusage.services.use", "http_status": status}
        body = response.json() if hasattr(response, "json") else {}
        permissions = body.get("permissions", []) if isinstance(body, dict) else []
        return {
            "ok": "serviceusage.services.use" in permissions,
            "permission": "serviceusage.services.use",
            "granted": "serviceusage.services.use" in permissions,
        }
    except Exception as exc:
        return {
            "ok": False,
            "permission": "serviceusage.services.use",
            "error_type": type(exc).__name__,
        }


def run_preflight(storage_client: Any, session: Any, *, project: str, input_uri: str, output_uri: str) -> dict[str, Any]:
    """Return separate GCS and Service Usage results for diagnosis before launch."""
    return {
        "gcs_input": check_gcs_object_access(storage_client, input_uri),
        "gcs_output": check_gcs_object_access(storage_client, output_uri),
        "service_usage": check_service_usage(session, project),
    }
