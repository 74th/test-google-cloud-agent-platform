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
    ExecutionOutcomeUnknown,
    OutputIncompleteError,
    ResourceOwnershipError,
    SandboxBusyError,
)
from gke_session_sandbox.reconciler import LifecycleReconciler
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
            "command_output_limit_bytes": 16 * 1024 * 1024,
            "session_output_limit_bytes": 64 * 1024 * 1024,
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
        same_key_handles = await asyncio.gather(*(
            manager.ensure(keys[0], env={"USER_EMAIL": "first@example.test"}) for _ in range(4)
        ))
        assert len({handle.sandbox_ref.uid for handle in same_key_handles}) == 1
        assert len({handle.generation for handle in same_key_handles}) == 1
        handles.append(same_key_handles[0])
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

        # A disconnected caller leaves the server-side command tracked and blocks suspend.
        async with handles[0].commands as disconnected_client:
            running_command = await disconnected_client.start([
                "python3", "-c", "import time; print('started', flush=True); time.sleep(8); print('finished')",
            ])
        with pytest.raises(SandboxBusyError):
            await manager.suspend(handles[0])
        async with handles[0].commands as reconnected_client:
            reconnected_result = await reconnected_client.wait(running_command["command_id"])
        assert reconnected_result.stdout == b"started\nfinished\n"

        # The lifecycle reconciler must keep a session active while parallel commands run.
        async with handles[0].commands as commands:
            parallel_commands = [
                await commands.start(["python3", "-c", "import time; time.sleep(8)"])
                for _ in range(2)
            ]
            parallel_ids = [item["command_id"] for item in parallel_commands]
            parallel_deadline = asyncio.get_running_loop().time() + 30
            while True:
                states = [(await commands.get(command_id))["state"] for command_id in parallel_ids]
                if all(state == "running" for state in states):
                    break
                if asyncio.get_running_loop().time() >= parallel_deadline:
                    raise TimeoutError(f"parallel GKE commands did not start: {states!r}")
                await asyncio.sleep(0.25)
            reconciler = LifecycleReconciler(manager)
            assert await reconciler.reconcile_once() == ()
            current = await manager.get(keys[0])
            assert current is not None and current.state.value == "ready"
            with pytest.raises(SandboxBusyError):
                await manager.suspend(current)
            parallel_results = await asyncio.gather(*(commands.wait(command_id) for command_id in parallel_ids))
            assert all(result.exit_code == 0 for result in parallel_results)

        # Simultaneous command admission and suspend must resolve to one safe outcome.
        async with handles[0].commands as commands:
            submission_task = asyncio.create_task(commands.start([
                "python3", "-c", "import time; time.sleep(2); print('race-command-finished')",
            ]))
            suspension_task = asyncio.create_task(manager.suspend(handles[0]))
            submission, suspension = await asyncio.gather(
                submission_task, suspension_task, return_exceptions=True
            )
            if isinstance(submission, dict):
                assert isinstance(suspension, SandboxBusyError), (
                    f"accepted command must prevent suspend, got {suspension!r}"
                )
                race_result = await commands.wait(submission["command_id"])
                assert race_result.stdout == b"race-command-finished\n"
            else:
                assert isinstance(submission, ResourceOwnershipError), (
                    f"command rejected during completed suspend should have a known rejection, got {submission!r}"
                )
                assert not isinstance(suspension, BaseException), (
                    f"suspend should succeed when command admission is rejected, got {suspension!r}"
                )
                assert suspension.state.value == "suspended"
                handles[0] = await manager.resume(suspension)

        # A disconnected consumer can replay a multi-megabyte response through byte cursors.
        async with handles[0].commands as disconnected_client:
            buffered_command = await disconnected_client.start([
                "python3", "-c", "import sys; sys.stdout.buffer.write(b'x' * (12 * 1024 * 1024))",
            ])
        async with handles[0].commands as replay_client:
            with pytest.raises(CommandOutputLimitExceeded):
                await replay_client.wait(buffered_command["command_id"])
            replayed = bytearray()
            cursor = 0
            while True:
                page = await replay_client.read_output(
                    buffered_command["command_id"], cursor=cursor, limit=256 * 1024
                )
                replayed.extend(page.data)
                cursor = page.cursor
                if page.complete:
                    break
        assert replayed == b"x" * (12 * 1024 * 1024)

        # Suspending removes the runtime Pod but must retain this generation's PVC and contents.
        first_ref = handles[0].sandbox_ref
        first_pod_uid = runtime_pods[0].metadata.uid
        first_pvc_refs = handles[0].record.workspace_pvc_refs
        assert len(first_pvc_refs) == 1
        suspended_handle = await manager.suspend(handles[0])
        assert suspended_handle.state.value == "suspended"
        suspended_sandbox = await custom.get_namespaced_custom_object(
            "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", first_ref.name
        )
        suspended_annotations = suspended_sandbox["metadata"]["annotations"]
        assert suspended_annotations["session-sandbox.example.com/state"] == "suspended"
        assert suspended_annotations["session-sandbox.example.com/generation"] == str(handles[0].generation)
        assert suspended_annotations["session-sandbox.example.com/suspended-at"]
        assert suspended_annotations["session-sandbox.example.com/expires-at"]
        resumed_handle = await manager.resume(suspended_handle)
        assert resumed_handle.generation == handles[0].generation
        assert resumed_handle.sandbox_ref.uid == first_ref.uid
        assert resumed_handle.record.workspace_pvc_refs[0].uid == first_pvc_refs[0].uid
        resumed_sandbox = await custom.get_namespaced_custom_object(
            "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", resumed_handle.sandbox_ref.name
        )
        resumed_selector = resumed_sandbox.get("status", {}).get("selector")
        resumed_pods = await core.list_namespaced_pod(namespace, label_selector=resumed_selector)
        resumed_pod = next(item for item in resumed_pods.items if item.status.phase == "Running")
        assert resumed_pod.metadata.uid != first_pod_uid
        assert await LifecycleReconciler(manager).reconcile_once() == ()
        resumed_sandbox = await custom.get_namespaced_custom_object(
            "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", first_ref.name
        )
        resumed_annotations = resumed_sandbox["metadata"]["annotations"]
        assert resumed_annotations["session-sandbox.example.com/state"] == "ready"
        assert resumed_annotations["session-sandbox.example.com/generation"] == str(handles[0].generation)
        assert resumed_annotations["session-sandbox.example.com/runtime-instance-id"] == resumed_pod.metadata.uid
        assert resumed_annotations["session-sandbox.example.com/suspended-at"]
        assert resumed_annotations["session-sandbox.example.com/expires-at"]
        handles[0] = resumed_handle
        async with handles[0].files as files:
            assert await files.exists("only-in-first.txt")

        async with handles[0].commands as commands:
            limited_command = await commands.start(
                [
                    "python3", "-c",
                    "import sys; sys.stdout.buffer.write(b'x' * (17 * 1024 * 1024))",
                ]
            )
            with pytest.raises(CommandOutputLimitExceeded) as limit_error:
                await commands.wait(limited_command["command_id"])
            assert limit_error.value.limit_bytes == manager_config.lifecycle.command_output_limit_bytes
            limited_output = await commands.read_output(limited_command["command_id"], limit=1024)
            assert 0 < limited_output.total_bytes <= manager_config.lifecycle.command_output_limit_bytes
            assert limited_output.output_complete is False
            storage_failure = await commands.start([
                "python3", "-c",
                "import os; p='/workspace/.session-runtime/command-output'; "
                "os.makedirs(p, exist_ok=True); os.chmod(p, 0o500); print('storage-failure-probe')",
            ])
            with pytest.raises(OutputIncompleteError):
                await commands.wait(storage_failure["command_id"])
            storage_record = await commands.get(storage_failure["command_id"])
            assert storage_record["state"] == "finished"
            assert storage_record["output_error_code"] == "output_storage_error"
            assert storage_record["output_complete"] is False
            await commands.run([
                "python3", "-c",
                "import os; os.chmod('/workspace/.session-runtime/command-output', 0o700)",
            ])
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


@pytest.mark.gke
async def test_tracker_restart_keeps_unverifiable_command_unknown():
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
        lifecycle={"idle_timeout_seconds": 300, "retention_seconds": 3600},
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
    manager = SandboxManager(
        manager_config,
        SQLiteSessionRepository(f"/tmp/gke-pytest-unknown-{run_id}.sqlite3", require_mount=False),
        CoreSandboxBackend(custom, core, client.NetworkingV1Api(api)),
        template=template,
        pvc_manager=OwnedWorkspacePVCManager(core),
    )
    key = SessionKey(tenant_id=f"gke-pytest-unknown-{run_id}", session_id=run_id)
    try:
        handle = await manager.ensure(key)
        async with handle.commands as commands:
            accepted = await commands.start([
                "python3", "-c", "import time; time.sleep(120)",
            ])
        command_id = accepted["command_id"]
        deadline = asyncio.get_running_loop().time() + 30
        async with handle.commands as commands:
            while (await commands.get(command_id)).get("state") != "running":
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError("silent GKE command did not reach running state")
                await asyncio.sleep(0.25)

        sandbox = await custom.get_namespaced_custom_object(
            "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", handle.sandbox_ref.name
        )
        selector = sandbox.get("status", {}).get("selector")
        pods = await core.list_namespaced_pod(namespace, label_selector=selector)
        runtime_pod = next(item for item in pods.items if item.status.phase == "Running")
        ws_api = WsApiClient(api.configuration)
        ws_core = client.CoreV1Api(ws_api)
        try:
            rewrite_journal = (
                "import json,os,stat,sys,tempfile; "
                "p='/workspace/.session-runtime/commands.json'; "
                "d=json.load(open(p)); d['commands'][sys.argv[1]].pop('identity',None); "
                "fd,t=tempfile.mkstemp(dir=os.path.dirname(p),prefix='gke-unknown.'); "
                "os.fchmod(fd,stat.S_IMODE(os.stat(p).st_mode)); "
                "f=os.fdopen(fd,'w'); json.dump(d,f,separators=(',',':')); f.flush(); os.fsync(f.fileno()); "
                "f.close(); os.replace(t,p); print('identity-removed')"
            )
            changed = await ws_core.connect_get_namespaced_pod_exec(
                runtime_pod.metadata.name,
                namespace,
                command=["python3", "-c", rewrite_journal, command_id],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=20,
            )
            assert changed.strip() == "identity-removed"

            # Kill PID 1 so the whole container restarts without the supervisor
            # getting a chance to stop the tracker gracefully and flush memory.
            restart_container = "import os,signal; os.kill(1, signal.SIGKILL)"
            try:
                await ws_core.connect_get_namespaced_pod_exec(
                    runtime_pod.metadata.name,
                    namespace,
                    command=["python3", "-c", restart_container],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _request_timeout=15,
                )
            except Exception:
                # Killing PID 1 closes the exec stream as Kubernetes restarts the container.
                pass
        finally:
            await ws_api.close()

        restart_deadline = asyncio.get_running_loop().time() + 120
        while asyncio.get_running_loop().time() < restart_deadline:
            current_pods = await core.list_namespaced_pod(namespace, label_selector=selector)
            current = next((item for item in current_pods.items if item.status.phase == "Running"), None)
            if current:
                statuses = current.status.container_statuses or []
                sandboxd = next((item for item in statuses if item.name == manager_config.runtime.container_name), None)
                if sandboxd and sandboxd.restart_count >= 1 and sandboxd.ready:
                    break
            await asyncio.sleep(1)
        else:
            raise TimeoutError("sandbox runtime did not restart after killing its supervisor")

        unknown_deadline = asyncio.get_running_loop().time() + 30
        last_record = None
        last_error = None
        async with handle.commands as commands:
            while True:
                try:
                    record = await commands.get(command_id)
                    last_record = record
                    if record.get("state") == "unknown":
                        break
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                if asyncio.get_running_loop().time() >= unknown_deadline:
                    current_pods = await core.list_namespaced_pod(namespace, label_selector=selector)
                    current = next((item for item in current_pods.items if item.status.phase == "Running"), None)
                    diagnostics = ""
                    if current:
                        try:
                            diagnostics = await core.read_namespaced_pod_log(
                                current.metadata.name,
                                namespace,
                                container=manager_config.runtime.container_name,
                                tail_lines=80,
                            )
                        except Exception as exc:
                            diagnostics = f"log_error={type(exc).__name__}: {exc}"
                    raise TimeoutError(
                        f"tracker restart did not report the command as unknown; "
                        f"last_record={last_record!r} last_error={last_error!r} "
                        f"runtime_logs={diagnostics!r}"
                    )
                await asyncio.sleep(0.5)
            with pytest.raises(ExecutionOutcomeUnknown):
                await commands.wait(command_id)
        with pytest.raises(SandboxBusyError):
            await manager.suspend(handle)
    finally:
        current = await manager.get(key)
        if current is not None and current.state.value != "terminated":
            await manager.terminate(current, reason="gke-unknown-cleanup")
        await manager.close()
        await api.close()
