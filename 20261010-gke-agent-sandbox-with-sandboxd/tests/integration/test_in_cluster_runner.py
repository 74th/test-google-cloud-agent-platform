import os
import asyncio

import pytest
from kubernetes_asyncio import client, config
from kubernetes_asyncio.stream import WsApiClient
from gke_session_sandbox import (
    CoreSandboxBackend,
    ManagerConfig,
    OwnedWorkspacePVCManager,
    SandboxManager,
    SessionKey,
    SessionConfigurationConflictError,
    SQLiteSessionRepository,
    TemplateRenderer,
    CommandOutputLimitExceeded,
)
from pytest import fail
from kubernetes_asyncio.client.exceptions import ApiException


@pytest.mark.gke
async def test_runner_has_scoped_in_cluster_identity():
    namespace = os.environ["GKE_TEST_NAMESPACE"]
    run_id = os.environ["GKE_TEST_RUN_ID"]
    assert os.environ.get("KUBERNETES_SERVICE_HOST")
    assert os.environ.get("KUBERNETES_SERVICE_PORT")
    config.load_incluster_config()
    async with client.ApiClient() as api:
        core = client.CoreV1Api(api)
        probe_name = f"runner-identity-{run_id}"
        probe = await core.create_namespaced_config_map(
            namespace,
            client.V1ConfigMap(
                metadata=client.V1ObjectMeta(
                    name=probe_name,
                    labels={"session-sandbox.example.com/run-id": run_id},
                ),
                data={"probe": "ok"},
            ),
        )
        assert probe.metadata.labels["session-sandbox.example.com/run-id"] == run_id
        await core.delete_namespaced_config_map(
            probe_name,
            namespace,
            body=client.V1DeleteOptions(preconditions=client.V1Preconditions(uid=probe.metadata.uid)),
        )
        try:
            unexpected_namespace = await core.create_namespace(
                client.V1Namespace(metadata=client.V1ObjectMeta(name=f"gke-pytest-forbidden-{run_id}"))
            )
        except ApiException as exc:
            assert exc.status == 403
        else:
            await core.delete_namespace(
                f"gke-pytest-forbidden-{run_id}",
                body=client.V1DeleteOptions(
                    preconditions=client.V1Preconditions(uid=unexpected_namespace.metadata.uid)
                ),
            )
            pytest.fail("the in-cluster test identity created a namespace outside its run scope")


@pytest.mark.gke
async def test_gke_session_file_round_trip_through_command():
    if os.environ.get("GKE_TEST_FORCE_FAILURE") == "1":
        fail("intentional GKE pytest failure-artifact verification")
    namespace = os.environ["GKE_TEST_NAMESPACE"]
    control_namespace = os.environ["GKE_TEST_CONTROL_NAMESPACE"]
    run_id = os.environ["GKE_TEST_RUN_ID"]
    image = os.environ["GKE_SANDBOXD_IMAGE"]
    manager_config = ManagerConfig(
        namespace=namespace,
        control_namespace=control_namespace,
        workspace_storage_class="session-workspace-rwo",
        workspace_storage="1Gi",
        runtime={"image": image},
        lifecycle={
            "idle_timeout_seconds": 300,
            "retention_seconds": 3600,
            "command_output_limit_bytes": 8192,
            "session_output_limit_bytes": 16384,
            "buffered_response_limit_bytes": 4096,
        },
        environment_fingerprint_key="runner-only-key-not-for-prod-0123456789",
    )
    template = TemplateRenderer().render_file(
        "templates/sandbox.yaml",
        parameters={
            "runtime": manager_config.runtime.model_dump(),
            "workspace": {
                "storage_class": manager_config.workspace_storage_class,
                "storage": manager_config.workspace_storage,
            },
        },
        image_overrides={"sandboxd": image},
    ).manifest
    template["spec"]["podTemplate"]["spec"]["containers"][0]["env"] = [
        {"name": "USER_EMAIL", "value": "template@example.test"}
    ]
    config.load_incluster_config()
    api = client.ApiClient()
    core = client.CoreV1Api(api)
    custom = client.CustomObjectsApi(api)
    repository = SQLiteSessionRepository(f"/tmp/gke-pytest-{run_id}.sqlite3", require_mount=False)
    backend = CoreSandboxBackend(
        custom, core, client.NetworkingV1Api(api)
    )
    manager = SandboxManager(
        manager_config,
        repository,
        backend,
        template=template,
        pvc_manager=OwnedWorkspacePVCManager(core),
    )
    keys = [
        SessionKey(tenant_id=f"gke-pytest-{run_id}", session_id=f"{run_id}-a"),
        SessionKey(tenant_id=f"gke-pytest-{run_id}", session_id=f"{run_id}-b"),
    ]
    handles = []
    try:
        handles.append(await manager.ensure(keys[0], env={"USER_EMAIL": "first@example.test"}))
        handles.append(await manager.ensure(keys[1], env={"USER_EMAIL": "second@example.test"}))
        runtime_pods = []
        for handle in handles:
            sandbox = await custom.get_namespaced_custom_object(
                "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", handle.sandbox_ref.name
            )
            selector = sandbox.get("status", {}).get("selector")
            assert selector
            pods = await core.list_namespaced_pod(namespace, label_selector=selector)
            runtime_pods.append(next(item for item in pods.items if item.status.phase == "Running"))
        runtime_container = next(
            item for item in runtime_pods[0].spec.containers if item.name == manager_config.runtime.container_name
        )
        assert runtime_container.image == image
        assert runtime_pods[0].spec.node_name != runtime_pods[1].spec.node_name
        files_by_session = ("only-in-first.txt", "only-in-second.txt")
        markers = (b"workspace-one", b"workspace-two")
        for handle, file_name, marker in zip(handles, files_by_session, markers, strict=True):
            async with handle.files as files:
                await files.write(file_name, marker)
        for index, handle in enumerate(handles):
            async with handle.files as files:
                assert await files.exists(files_by_session[index])
                assert not await files.exists(files_by_session[1 - index])
        target_runtime_ip = runtime_pods[1].status.pod_ip
        assert target_runtime_ip
        blocked_probe = (
            "import socket,sys\n"
            "s=socket.socket();s.settimeout(3)\n"
            "try:\n s.connect((sys.argv[1],8080))\n"
            "except OSError:\n print('network-denied')\n"
            "else:\n print('unexpected-connect');sys.exit(1)\n"
        )
        ws_api = WsApiClient(api.configuration)
        try:
            ws_core = client.CoreV1Api(ws_api)
            network_result = await ws_core.connect_get_namespaced_pod_exec(
                runtime_pods[0].metadata.name,
                namespace,
                command=["python3", "-c", blocked_probe, target_runtime_ip],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=15,
            )
        finally:
            await ws_api.close()
        assert network_result.strip() == "network-denied"
        async with handles[0].commands as commands:
            limited_command = await commands.start(
                ["python3", "-c", "import sys; sys.stdout.write('x' * 20000)"]
            )
            with pytest.raises(CommandOutputLimitExceeded) as limit_error:
                await commands.wait(limited_command["command_id"])
            assert limit_error.value.limit_bytes == manager_config.lifecycle.command_output_limit_bytes
            limited_output = await commands.read_output(limited_command["command_id"], limit=1024)
            assert 0 < limited_output.total_bytes <= manager_config.lifecycle.command_output_limit_bytes
            assert limited_output.output_complete is False
        for handle, email, file_name, marker in zip(
            handles,
            (b"first@example.test", b"second@example.test"),
            files_by_session,
            markers,
            strict=True,
        ):
            async with handle.commands as commands:
                result = await commands.run(
                    ["sh", "-c", f"printf '%s:' \"$USER_EMAIL\"; cat /workspace/{file_name}"],
                    check=True,
                    timeout_seconds=30,
                )
            assert result.stdout.strip() == email + b":" + marker
        with pytest.raises(SessionConfigurationConflictError):
            await manager.ensure(keys[0], env={"USER_EMAIL": "changed@example.test"})
    finally:
        try:
            for key in keys:
                current = await manager.get(key)
                if current is not None and current.state.value != "terminated":
                    ref = current.sandbox_ref
                    await manager.terminate(current, reason="gke-pytest-cleanup")
                    if ref is not None:
                        await backend.wait_deleted(ref, timeout_seconds=180)
        finally:
            await manager.close()
            await api.close()


@pytest.mark.gke
async def test_controller_expiry_deletes_suspended_workspace_without_worker():
    namespace = os.environ["GKE_TEST_NAMESPACE"]
    control_namespace = os.environ["GKE_TEST_CONTROL_NAMESPACE"]
    run_id = os.environ["GKE_TEST_RUN_ID"]
    image = os.environ["GKE_SANDBOXD_IMAGE"]
    retention_seconds = int(os.environ["GKE_RETENTION_SECONDS"])
    manager_config = ManagerConfig(
        namespace=namespace,
        control_namespace=control_namespace,
        workspace_storage_class="session-workspace-rwo",
        workspace_storage="1Gi",
        runtime={"image": image},
        lifecycle={"idle_timeout_seconds": 300, "retention_seconds": retention_seconds},
    )
    template = TemplateRenderer().render_file(
        "templates/sandbox.yaml",
        parameters={
            "runtime": manager_config.runtime.model_dump(),
            "workspace": {
                "storage_class": manager_config.workspace_storage_class,
                "storage": manager_config.workspace_storage,
            },
        },
        image_overrides={"sandboxd": image},
    ).manifest
    config.load_incluster_config()
    api = client.ApiClient()
    core = client.CoreV1Api(api)
    custom = client.CustomObjectsApi(api)
    repository_path = f"/tmp/gke-pytest-expiry-{run_id}.sqlite3"
    repository = SQLiteSessionRepository(repository_path, require_mount=False)
    backend = CoreSandboxBackend(custom, core, client.NetworkingV1Api(api))
    pvc_manager = OwnedWorkspacePVCManager(core)
    manager = SandboxManager(
        manager_config, repository, backend, template=template, pvc_manager=pvc_manager
    )
    replacement_manager = None
    key = SessionKey(tenant_id=f"gke-pytest-expiry-{run_id}", session_id=run_id)
    old_ref = None
    try:
        handle = await manager.ensure(key)
        old_ref = handle.sandbox_ref
        async with handle.files as files:
            await files.write("expiry-marker.txt", b"must-be-deleted")
        suspended = await manager.suspend(handle)
        assert suspended.record.expires_at is not None

        # There is deliberately no LifecycleReconciler in this pytest Pod.
        await manager.close()
        await backend.wait_deleted(old_ref, timeout_seconds=retention_seconds + 180)

        deadline = asyncio.get_running_loop().time() + 120
        while await pvc_manager.list_owned(old_ref):
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError("controller did not remove the expired workspace PVC")
            await asyncio.sleep(2)

        replacement_repository = SQLiteSessionRepository(repository_path, require_mount=False)
        replacement_manager = SandboxManager(
            manager_config, replacement_repository, backend, template=template, pvc_manager=pvc_manager
        )
        replacement = await replacement_manager.ensure(key)
        assert replacement.generation == suspended.generation + 1
        assert replacement.sandbox_ref.uid != old_ref.uid
        async with replacement.files as files:
            assert not await files.exists("expiry-marker.txt")
        event = next(
            item for item in replacement.pending_context_events
            if item.event_type.value == "workspace_cleared" and item.reason == "retention-expired"
        )
        assert await replacement_manager.ack_context_event(key, event.event_id) is True
        assert await replacement_manager.ack_context_event(key, event.event_id) is False
    finally:
        active_manager = replacement_manager or manager
        if not active_manager._closed:
            current = await active_manager.get(key)
            if current is not None and current.state.value != "terminated":
                await active_manager.terminate(current, reason="gke-pytest-cleanup")
        if not manager._closed:
            await manager.close()
        if replacement_manager is not None and not replacement_manager._closed:
            await replacement_manager.close()
        await api.close()
