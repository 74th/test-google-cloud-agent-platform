"""Exercise the Python core Sandbox backend against the explicitly named GKE cluster."""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import time
import uuid

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.exceptions import ApiException

from gke_session_sandbox import CoreSandboxBackend, OwnedWorkspacePVCManager


def expected_context() -> str:
    project = os.environ["GKE_PROJECT_ID"]
    location = os.environ["GKE_LOCATION"]
    cluster = os.environ["GKE_CLUSTER_NAME"]
    return f"gke_{project}_{location}_{cluster}"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    expected = expected_context()
    current = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    if current != expected:
        raise SystemExit(f"refusing GKE backend validation: context {current!r}, expected {expected!r}")

    await config.load_kube_config(context=expected)
    async with client.ApiClient() as api_client:
        custom = client.CustomObjectsApi(api_client)
        core = client.CoreV1Api(api_client)
        networking = client.NetworkingV1Api(api_client)
        backend = CoreSandboxBackend(custom, core, networking)
        pvc_manager = OwnedWorkspacePVCManager(core)
        namespace = os.environ.get("GKE_SANDBOX_NAMESPACE", "session-sandboxes")
        name = f"py-backend-{uuid.uuid4().hex[:10]}"
        image = os.environ.get(
            "SANDBOXD_IMAGE",
            "us-central1-docker.pkg.dev/nnyn-dev/research-gke-agent-sandbox-with-sandboxd-images/"
            "sandboxd@sha256:28ce219266fe3586b489e1edf9355722eb2951bef8c73db7ff06ec5541ae5d4a",
        )
        manifest = {
            "apiVersion": "agents.x-k8s.io/v1beta1",
            "kind": "Sandbox",
            "metadata": {"labels": {"app.kubernetes.io/part-of": "gke-session-sandbox", "validation-id": name}},
            "spec": {
                "service": True,
                "podTemplate": {
                    "metadata": {"labels": {"validation-id": name}},
                    "spec": {
                        "runtimeClassName": "gvisor",
                        "automountServiceAccountToken": False,
                        "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000, "fsGroup": 1000},
                        "containers": [{
                            "name": "sandboxd",
                            "image": image,
                            "imagePullPolicy": "IfNotPresent",
                            "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}},
                            "ports": [
                                {"name": "rest", "containerPort": 8080},
                                {"name": "grpc", "containerPort": 9090},
                            ],
                            "readinessProbe": {"httpGet": {"path": "/v1/health", "port": "rest"}},
                            "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}},
                            "volumeMounts": [{"name": "workspace", "mountPath": "/workspace"}],
                        }],
                    },
                },
                "volumeClaimTemplates": [{
                    "metadata": {"name": "workspace"},
                    "spec": {
                        "storageClassName": "session-workspace-rwo",
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "1Gi"}},
                    },
                }],
            },
        }
        ref = None
        workspace_volume_name = None
        shared_fixture = None
        try:
            shared_fixture = await core.read_namespaced_persistent_volume_claim("runtime-code-rom", "session-sandbox-fixtures")
            ref = await backend.create_suspended(manifest, namespace=namespace, name=name)
            await backend.start(ref)
            sandbox = await backend.wait_ready(ref, timeout_seconds=args.timeout, poll_interval_seconds=2)
            status = sandbox.get("status", {})
            pod_list = await core.list_namespaced_pod(namespace, label_selector=status.get("selector"))
            pod = next(pod for pod in pod_list.items if any(c.type == "Ready" and c.status == "True" for c in (pod.status.conditions or [])))
            pvc = await owned_workspace_pvc(core, namespace, ref.uid)
            workspace_volume_name = pvc.spec.volume_name
            owned_refs = await pvc_manager.list_owned(ref)
            assert any(item.uid == pvc.metadata.uid for item in owned_refs)
            first_pod_uid = pod.metadata.uid
            pvc_uid = pvc.metadata.uid

            await backend.suspend(ref)
            await wait_until_suspended(custom, core, namespace, name, args.timeout)
            await backend.start(ref)
            resumed = await backend.wait_ready(ref, timeout_seconds=args.timeout, poll_interval_seconds=2)
            resumed_pods = await core.list_namespaced_pod(namespace, label_selector=resumed.get("status", {}).get("selector"))
            resumed_pod = next(pod for pod in resumed_pods.items if any(c.type == "Ready" and c.status == "True" for c in (pod.status.conditions or [])))
            resumed_pvc = await owned_workspace_pvc(core, namespace, ref.uid)
            assert resumed_pod.metadata.uid != first_pod_uid
            assert resumed_pvc.metadata.uid == pvc_uid
            print(f"python-backend-gke-lifecycle-ok sandbox_uid={ref.uid} pvc_uid={pvc_uid} pod_recreated=true")
        finally:
            if ref is not None:
                try:
                    await backend.delete(ref)
                    await wait_for_not_found(custom, namespace, name, args.timeout)
                    await wait_for_workspace_cleanup(core, namespace, ref.uid, workspace_volume_name, args.timeout)
                    if shared_fixture is not None:
                        remaining_shared = await core.read_namespaced_persistent_volume_claim("runtime-code-rom", "session-sandbox-fixtures")
                        assert remaining_shared.metadata.uid == shared_fixture.metadata.uid
                except ApiException as exc:
                    if exc.status != 404:
                        raise


async def wait_until_suspended(custom, core, namespace: str, name: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sandbox = await custom.get_namespaced_custom_object("agents.x-k8s.io", "v1beta1", namespace, "sandboxes", name)
        conditions = sandbox.get("status", {}).get("conditions", [])
        if any(c.get("type") == "Suspended" and c.get("status") == "True" for c in conditions):
            selector = sandbox.get("status", {}).get("selector")
            pods = await core.list_namespaced_pod(namespace, label_selector=selector)
            if not pods.items:
                return
        await asyncio.sleep(2)
    raise TimeoutError(f"Sandbox {namespace}/{name} did not suspend and remove its Pod")


async def owned_workspace_pvc(core, namespace: str, sandbox_uid: str):
    claims = await core.list_namespaced_persistent_volume_claim(namespace)
    for claim in claims.items:
        if any(owner.uid == sandbox_uid and owner.kind == "Sandbox" for owner in (claim.metadata.owner_references or [])):
            return claim
    raise RuntimeError(f"no PVC owned by Sandbox UID {sandbox_uid} exists in {namespace}")


async def wait_for_workspace_cleanup(core, namespace: str, sandbox_uid: str, volume_name: str | None, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        claims = await core.list_namespaced_persistent_volume_claim(namespace)
        still_owned = any(
            owner.uid == sandbox_uid
            for claim in claims.items
            for owner in (claim.metadata.owner_references or [])
        )
        volume_still_exists = False
        if volume_name:
            try:
                await core.read_persistent_volume(volume_name)
                volume_still_exists = True
            except ApiException as exc:
                if exc.status != 404:
                    raise
        if not still_owned and not volume_still_exists:
            return
        await asyncio.sleep(2)
    raise TimeoutError(f"PVC / PV cleanup for Sandbox UID {sandbox_uid} did not complete")


async def wait_for_not_found(custom, namespace: str, name: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            await custom.get_namespaced_custom_object("agents.x-k8s.io", "v1beta1", namespace, "sandboxes", name)
        except ApiException as exc:
            if exc.status == 404:
                return
            raise
        await asyncio.sleep(2)
    raise TimeoutError(f"Sandbox {namespace}/{name} was not deleted before timeout")


if __name__ == "__main__":
    asyncio.run(main())
