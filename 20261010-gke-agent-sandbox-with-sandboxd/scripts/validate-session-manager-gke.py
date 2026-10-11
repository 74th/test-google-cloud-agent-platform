"""Check public ensure/get/suspend/resume/terminate/close behavior on GKE."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from aiohttp import web

from kubernetes_asyncio import client, config as kube_config
from kubernetes_asyncio.client.exceptions import ApiException

from gke_session_sandbox import (
    CoreSandboxBackend,
    LifecycleReconciler,
    ManagerConfig,
    OwnedWorkspacePVCManager,
    SessionState,
    SandboxManager,
    SessionKey,
    SQLiteSessionRepository,
    SandboxBusyError,
    TemplateRenderer,
)
from gke_session_sandbox.gke_validation import collect_failure_artifacts, verify_target


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--idle-timeout-seconds",
        type=int,
        default=5,
        help="idle threshold for the primary session (use 300 to verify the production boundary)",
    )
    parser.add_argument(
        "--retention-seconds",
        type=int,
        default=30,
        help="real retention wait for the disposable expiry scenario; use 604800 for seven days",
    )
    parser.add_argument("--reconcile-interval-seconds", type=int, default=60)
    parser.add_argument("--agent-turn-wait-seconds", type=int, default=10)
    parser.add_argument("--artifact-dir", default="artifacts/gke-session-manager")
    parser.add_argument(
        "--verify-failure-artifacts",
        action="store_true",
        help="intentionally fail after namespace creation to test artifact capture and UID cleanup",
    )
    args = parser.parse_args()
    if min(
        args.idle_timeout_seconds,
        args.retention_seconds,
        args.reconcile_interval_seconds,
        args.agent_turn_wait_seconds,
    ) <= 0:
        parser.error("idle, retention, reconcile interval, and Agent turn wait values must be positive")
    project = os.environ["GKE_PROJECT_ID"]
    location = os.environ["GKE_LOCATION"]
    cluster = os.environ["GKE_CLUSTER_NAME"]
    current = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    active_project = subprocess.check_output(
        ["gcloud", "config", "get-value", "project"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    context = verify_target(project, location, cluster, current_context=current, active_project=active_project)
    run_id = uuid.uuid4().hex[:12]
    run_namespace = f"session-sandboxes-{run_id}"
    artifact_root = Path(args.artifact_dir).expanduser()
    if not artifact_root.is_absolute():
        artifact_root = Path(__file__).resolve().parents[1] / artifact_root
    artifact_root = artifact_root.resolve()
    await kube_config.load_kube_config(context=context)

    config = ManagerConfig(
        namespace=run_namespace,
        control_namespace="session-sandbox-system",
        workspace_storage_class="session-workspace-rwo",
        workspace_storage="1Gi",
        runtime={
            "container_name": "sandboxd",
            "image": os.environ.get(
                "SANDBOXD_IMAGE",
                "us-central1-docker.pkg.dev/nnyn-dev/research-gke-agent-sandbox-with-sandboxd-images/"
                "session-runtime@sha256:11eaa6651ef23b9a7e19a1138277a8e6b30b2400df461530a8016e043bc1baf3",
            ),
            "cpu_request": "100m", "cpu_limit": "500m",
            "memory_request": "128Mi", "memory_limit": "512Mi",
        },
        network={"allowed_fqdns": [{
            "name": "api.anthropic.com",
            "ports": [{"protocol": "TCP", "port": 443}],
        }]},
        lifecycle={
            "reconcile_interval_seconds": args.reconcile_interval_seconds,
            "idle_timeout_seconds": args.idle_timeout_seconds,
            "retention_seconds": 3600,
        },
    )
    template = TemplateRenderer().render_file(
        "templates/sandbox.yaml",
        parameters={
            "runtime": config.runtime.model_dump(),
            "workspace": {"storage_class": config.workspace_storage_class, "storage": config.workspace_storage},
        },
        image_overrides={"sandboxd": config.runtime.image},
    ).manifest

    async with client.ApiClient() as api_client:
        core = client.CoreV1Api(api_client)
        custom = client.CustomObjectsApi(api_client)
        networking = client.NetworkingV1Api(api_client)
        namespace_uid = None
        namespace_body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=run_namespace,
                labels={"app.kubernetes.io/part-of": "gke-session-sandbox-validation", "session-sandbox.example.com/run-id": run_id},
            )
        )
        key = SessionKey(tenant_id=f"python-manager-gke-{run_id}", session_id=run_id)
        repository_path = Path(tempfile.gettempdir()) / f"session-manager-validation-{key.session_id}.sqlite3"
        repository = SQLiteSessionRepository(
            repository_path,
            require_mount=False,
            max_pending_events=config.max_pending_events,
            lease_duration_seconds=config.session_lease_duration_seconds,
        )
        backend = CoreSandboxBackend(custom, core, networking)
        manager = SandboxManager(
            config,
            repository,
            backend,
            template=template,
            pvc_manager=OwnedWorkspacePVCManager(core),
        )
        pvc_manager = OwnedWorkspacePVCManager(core)
        second_manager = None
        ref = None
        volume_name = None
        shared = None
        bypass_job = None
        gate_proxy_runner = None
        original_runtime_endpoint = None
        lost_generation = None
        expired_generation = None
        try:
            created_namespace = await core.create_namespace(namespace_body)
            namespace_uid = created_namespace.metadata.uid
            if args.verify_failure_artifacts:
                await core.create_namespaced_config_map(
                    run_namespace,
                    client.V1ConfigMap(
                        metadata=client.V1ObjectMeta(
                            name="failure-artifact-probe",
                            labels={"app.kubernetes.io/part-of": "gke-session-sandbox-validation"},
                        ),
                        data={"probe": run_id},
                    ),
                )
                raise RuntimeError("intentional failure-artifact verification")
            shared = await core.read_namespaced_persistent_volume_claim("runtime-code-rom", "session-sandbox-fixtures")
            await run_sqlite_pvc_reopen_probe(
                core, run_namespace, config.runtime.image, config.workspace_storage_class, args.timeout
            )
            first, concurrent = await asyncio.gather(
                manager.ensure(key),
                manager.ensure(key),
            )
            ref = first.sandbox_ref
            assert ref is not None and ref == concurrent.sandbox_ref
            assert first.generation == concurrent.generation == 1
            pvc_refs = await pvc_manager.list_owned(ref)
            assert len(pvc_refs) == 1
            pvc = await core.read_namespaced_persistent_volume_claim(pvc_refs[0].name, ref.namespace)
            volume_name = pvc.spec.volume_name
            sandbox = await custom.get_namespaced_custom_object("agents.x-k8s.io", "v1beta1", ref.namespace, "sandboxes", ref.name)
            pods = await core.list_namespaced_pod(ref.namespace, label_selector=sandbox.get("status", {}).get("selector"))
            pod = next(item for item in pods.items if item.status.phase == "Running")
            if pod.spec.automount_service_account_token is not False:
                raise AssertionError("sandbox Pod automounts its Kubernetes service account token")
            if any(
                volume.projected and any(source.service_account_token for source in (volume.projected.sources or []))
                for volume in (pod.spec.volumes or [])
            ):
                raise AssertionError("sandbox Pod has a projected Kubernetes service account token volume")
            tracker_endpoint = await backend.runtime_endpoint(ref)
            original_runtime_endpoint = backend.runtime_endpoint
            gate_proxy_runner, gate_proxy_endpoint = await start_gate_proxy(ref.name, ref.namespace)

            async def manager_runtime_endpoint(sandbox_ref, *, tracker_port=8081):
                return gate_proxy_endpoint

            backend.runtime_endpoint = manager_runtime_endpoint
            active_probe_command = run_sandbox_network_probes(pod.metadata.name, ref.namespace)
            cancel_probe_command(pod.metadata.name, ref.namespace, active_probe_command)
            run_tracker_python_client_probe(
                config.control_namespace, config.runtime.image, tracker_endpoint
            )
            bypass_job = run_tracker_bypass_probe(ref.name, ref.namespace, pod.status.pod_ip)

            read = await manager.get(key)
            assert read is not None and read.sandbox_ref.uid == ref.uid
            suspend_deadline = time.monotonic() + min(args.timeout, 90)
            while True:
                try:
                    suspended = await manager.suspend(read)
                    break
                except SandboxBusyError:
                    if time.monotonic() >= suspend_deadline:
                        raise TimeoutError("tracker did not become idle after the runtime probes")
                    await asyncio.sleep(2)
            resumed = await manager.resume(suspended)
            assert suspended.state.value == "suspended" and resumed.state.value == "ready"
            await run_agent_lifecycle_e2e(
                manager,
                key,
                resumed,
                idle_timeout_seconds=config.lifecycle.idle_timeout_seconds,
                agent_turn_wait_seconds=args.agent_turn_wait_seconds,
            )
            backend.runtime_endpoint = original_runtime_endpoint
            lost_generation = await run_external_workspace_loss_e2e(
                manager, backend, core, custom, pvc_manager, run_namespace, run_id, args.timeout
            )
            expired_generation = await run_retention_expiry_e2e(
                manager, core, custom, pvc_manager, run_namespace, run_id, args.timeout,
                retention_seconds=args.retention_seconds,
            )

            await manager.close()
            subprocess.check_call(["kubectl", "get", "sandbox", ref.name, "-n", ref.namespace], stdout=subprocess.DEVNULL)

            # Reconnect through a fresh manager to verify close left the remote session intact.
            async with client.ApiClient() as second_api_client:
                second_core = client.CoreV1Api(second_api_client)
                second_repository = SQLiteSessionRepository(
                    repository_path,
                    require_mount=False,
                    lease_duration_seconds=config.session_lease_duration_seconds,
                )
                second_backend = CoreSandboxBackend(
                    client.CustomObjectsApi(second_api_client),
                    second_core,
                    client.NetworkingV1Api(second_api_client),
                )
                second_manager = SandboxManager(config, second_repository, second_backend, template=template)
                reconnected = await second_manager.get(key)
                assert reconnected is not None and reconnected.sandbox_ref.uid == ref.uid
                listed = await second_manager.list_sessions()
                assert any(item.key_hash == key.stable_hash() for item in listed)
                for generation_probe in (lost_generation, expired_generation):
                    if generation_probe is None:
                        continue
                    lost_key, lost_handle, lost_volume_name, lost_event_id = generation_probe
                    lost_reconnected = await second_manager.get(lost_key)
                    assert lost_reconnected is not None and lost_reconnected.sandbox_ref.uid == lost_handle.sandbox_ref.uid
                    assert lost_event_id in {item.event_id for item in lost_reconnected.pending_context_events}
                    assert await second_manager.ack_context_event(lost_key, lost_event_id) is True
                    assert await second_manager.ack_context_event(lost_key, lost_event_id) is False
                    assert await second_manager.pending_context_events(lost_key) == ()
                    lost_terminated = await second_manager.terminate(lost_reconnected, reason="validation-cleanup")
                    assert lost_terminated.state is SessionState.TERMINATED
                    await second_backend.wait_deleted(lost_handle.sandbox_ref, timeout_seconds=args.timeout)
                    await wait_for_workspace_cleanup(
                        second_core, run_namespace, lost_handle.sandbox_ref.uid, lost_volume_name, args.timeout
                    )
                    print(f"workspace-generation-reconnected-ok run_id={run_id} generation={lost_handle.generation} event_ack=true")
                terminated = await second_manager.terminate(reconnected, reason="gke-validation")
                assert terminated.state.value == "terminated"
                termination_event = next(
                    event for event in terminated.pending_context_events
                    if event.reason == "gke-validation" and event.event_type.value == "workspace_cleared"
                )
                assert "shared code remains mounted read-only" in termination_event.context_message.lower()
                await second_backend.wait_deleted(ref, timeout_seconds=args.timeout)
                await wait_for_workspace_cleanup(second_core, ref.namespace, ref.uid, volume_name, args.timeout)
                remaining_shared = await second_core.read_namespaced_persistent_volume_claim(
                    "runtime-code-rom", "session-sandbox-fixtures"
                )
                assert remaining_shared.metadata.uid == shared.metadata.uid
                await second_manager.close()
            print(f"session-manager-gke-ok run_id={run_id} namespace={run_namespace} sandbox_uid={ref.uid} generation=1 concurrent_ensure=one close_preserved=true")
        except BaseException as failure:
            try:
                artifact_dir = collect_failure_artifacts(
                    artifact_root,
                    run_id=run_id,
                    project=project,
                    context=context,
                    namespace=run_namespace,
                    namespace_uid=namespace_uid,
                    failure_details="".join(traceback.format_exception(failure)),
                )
                print(f"gke-validation-failure-artifacts={artifact_dir}")
            except Exception as artifact_error:
                print(f"could not save GKE failure artifacts: {type(artifact_error).__name__}: {artifact_error}")
            raise
        finally:
            if original_runtime_endpoint is not None:
                backend.runtime_endpoint = original_runtime_endpoint
            cleanup_manager = second_manager or manager
            if not cleanup_manager._closed:
                try:
                    current = await cleanup_manager.get(key)
                    if current is not None and current.state.value != "terminated":
                        if ref is None:
                            ref = current.sandbox_ref
                        if ref is not None:
                            await cleanup_manager.terminate(current, reason="validation-cleanup")
                except Exception as cleanup_error:
                    print(f"validation cleanup could not terminate the owned session: {cleanup_error}")
            if second_manager is not None:
                await second_manager.close()
            elif not manager._closed:
                await manager.close()
            key_hash = key.stable_hash()
            if bypass_job:
                subprocess.run(
                    ["kubectl", "delete", "job", bypass_job, "-n", config.control_namespace, "--ignore-not-found=true"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            if gate_proxy_runner is not None:
                await gate_proxy_runner.cleanup()
            for suffix in ("", "-wal", "-shm"):
                Path(f"{repository_path}{suffix}").unlink(missing_ok=True)
            if namespace_uid is not None:
                try:
                    await core.delete_namespace(
                        run_namespace,
                        body=client.V1DeleteOptions(
                            preconditions=client.V1Preconditions(uid=namespace_uid)
                        ),
                    )
                    deadline = time.monotonic() + args.timeout
                    while time.monotonic() < deadline:
                        try:
                            await core.read_namespace(run_namespace)
                        except ApiException as exc:
                            if exc.status == 404:
                                break
                            raise
                        await asyncio.sleep(2)
                    else:
                        raise TimeoutError(f"validation namespace {run_namespace} was not deleted")
                except ApiException as exc:
                    if exc.status != 404:
                        print(f"validation cleanup requires attention: namespace={run_namespace} uid={namespace_uid} error={exc}")
                        raise


def run_tracker_python_client_probe(namespace: str, image: str, endpoint: str) -> None:
    python = "\n".join([
        "import asyncio, json",
        "from gke_session_sandbox.commands import CommandTrackerClient",
        "from gke_session_sandbox.files import FileClient",
        "from gke_session_sandbox.errors import FileOperationError",
        f"endpoint = {endpoint!r}",
        "async def main():",
        "    import uuid",
        "    command_id = uuid.uuid4().hex",
        "    async with CommandTrackerClient(lambda: asyncio.sleep(0, result=endpoint)) as commands:",
        "        accepted = await commands.start(['sh', '-c', 'sleep 1; printf session-client-ok'], command_id=command_id, check=True, timeout_seconds=30)",
        "    async with CommandTrackerClient(lambda: asyncio.sleep(0, result=endpoint)) as commands:",
        "        result = await commands.wait(accepted['command_id'], check=True)",
        "        cursor, recovered = 0, bytearray()",
        "        while True:",
        "            page = await commands.read_output(accepted['command_id'], cursor=cursor, limit=4)",
        "            recovered.extend(page.data)",
        "            cursor = page.cursor",
        "            if page.complete:",
        "                break",
        "        await commands.run(['sh', '-c', 'mkdir -p /workspace/client-probe && ln -s /etc/passwd /workspace/client-probe/escape'], check=True, timeout_seconds=30)",
        "    file_endpoint = endpoint.rsplit(':', 1)[0] + ':8080'",
        "    async with FileClient(lambda: asyncio.sleep(0, result=file_endpoint)) as files:",
        "        await files.write('client-probe/write.txt', b'written-by-python')",
        "        written = await files.read('client-probe/write.txt')",
        "        streamed = bytearray()",
        "        copied = await files.read_to('client-probe/write.txt', streamed.extend)",
        "        size = (await files.stat('client-probe/write.txt')).size",
        "        entries = await files.list('client-probe')",
        "        try:",
        "            await files.read('client-probe/escape')",
        "        except FileOperationError as exc:",
        "            traversal_denied = exc.status == 403",
        "        else:",
        "            traversal_denied = False",
        "        await files.delete('client-probe', recursive=True)",
        "        print(json.dumps({'command_id': result.command_id, 'exit_code': result.exit_code, 'stdout': result.stdout.decode(), 'cursor_stdout': bytes(recovered).decode(), 'file_write_read': written.decode(), 'streamed': bytes(streamed).decode(), 'copied': copied, 'stat_size': size, 'listed': [item.path for item in entries], 'traversal_denied': traversal_denied, 'deleted': not await files.exists('client-probe')}))",
        "asyncio.run(main())",
    ])
    job_name = "tracker-client-" + uuid.uuid4().hex[:10]
    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": job_name, "namespace": namespace},
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 60,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "containers": [{"name": "client", "image": image, "command": ["python3", "-c", python]}],
                }
            },
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
        yaml.safe_dump(manifest, stream)
        manifest_path = stream.name
    try:
        subprocess.run(["kubectl", "apply", "-f", manifest_path], check=True, capture_output=True, text=True)
        completed = subprocess.run(
            ["kubectl", "wait", "--for=condition=complete", f"job/{job_name}", "-n", namespace, "--timeout=120s"],
            check=False, capture_output=True, text=True,
        )
        logs = subprocess.run(["kubectl", "logs", f"job/{job_name}", "-n", namespace], check=False,
                              capture_output=True, text=True)
        if completed.returncode:
            raise AssertionError(f"Python client Job did not complete: {logs.stdout}{logs.stderr}{completed.stderr}")
        payload = json.loads(logs.stdout)
        if (payload.get("stdout") != "session-client-ok" or payload.get("exit_code") != 0
                or payload.get("cursor_stdout") != "session-client-ok"
                or payload.get("file_write_read") != "written-by-python"
                or payload.get("streamed") != "written-by-python" or payload.get("copied") != 17
                or payload.get("stat_size") != 17 or not payload.get("traversal_denied")
                or not payload.get("deleted")):
            raise AssertionError(f"Python command/file client returned an unexpected result: {payload}")
        print(f"session-client-command-ok command_id={payload['command_id']} exit={payload['exit_code']}")
    finally:
        os.unlink(manifest_path)
        subprocess.run(["kubectl", "delete", "job", job_name, "-n", namespace, "--ignore-not-found=true"],
                       check=False, capture_output=True, text=True)


async def start_gate_proxy(sandbox_name: str, namespace: str):
    """Bridge local manager tracker calls through kubectl exec into a cluster-only Service."""
    async def proxy(request):
        body = await request.read()
        script = "\n".join([
            "import base64, json, sys, urllib.error, urllib.request",
            "port = 8080 if sys.argv[1].startswith('/v1/files/') else 8081",
            "url = f'http://127.0.0.1:{port}' + sys.argv[1]",
            "method = sys.argv[2]",
            "body = base64.b64decode(sys.argv[3]) if sys.argv[3] else None",
            "headers = {'Content-Type': sys.argv[4]} if body is not None and sys.argv[4] else {}",
            "request = urllib.request.Request(url, data=body, headers=headers, method=method)",
            "try:",
            "    response = urllib.request.urlopen(request, timeout=15)",
            "    status, content_type, payload = response.status, response.headers.get('Content-Type', 'application/json'), response.read()",
            "except urllib.error.HTTPError as error:",
            "    status, content_type, payload = error.code, error.headers.get('Content-Type', 'application/json'), error.read()",
            "print(json.dumps({'status': status, 'content_type': content_type, 'body': base64.b64encode(payload).decode()}))",
        ])
        process = await asyncio.create_subprocess_exec(
            "kubectl", "exec", sandbox_name, "-n", namespace, "-c", "sandboxd", "--",
            "python3", "-c", script, request.rel_url.path_qs, request.method,
            base64.b64encode(body).decode(),
            request.headers.get("Content-Type", ""),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            return web.Response(status=502, text=stderr.decode(errors="replace"))
        result = json.loads(stdout)
        return web.Response(
            status=result["status"],
            body=base64.b64decode(result["body"]),
            headers={"Content-Type": result["content_type"]},
        )

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", proxy)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return runner, f"http://127.0.0.1:{port}"


async def run_agent_lifecycle_e2e(
    manager, key: SessionKey, session, *, idle_timeout_seconds: int, agent_turn_wait_seconds: int
) -> None:
    fixture = Path(__file__).parents[1] / "examples" / "fixtures" / "one_turn_agent.py"
    async with session.files as files:
        await files.write("one_turn_agent.py", fixture.read_bytes())
    async with session.commands as commands:
        accepted = await commands.start(
            [
                "python3", "/workspace/one_turn_agent.py", "LLM wait simulation",
                "--wait-seconds", str(agent_turn_wait_seconds),
            ],
            timeout_seconds=180,
        )
        reconciler = LifecycleReconciler(manager)
        reserved = await manager.get(key)
        if (reserved is None or reserved.state is not SessionState.READY
                or accepted["command_id"] not in {item.command_id for item in reserved.record.active_commands}):
            raise AssertionError("Agent command was not durably reserved before lifecycle reconciliation")
        errors = await reconciler.reconcile_once()
        if errors:
            raise RuntimeError("reconciler failed while Agent runner was active: " + "; ".join(errors))
        current = await manager.get(key)
        if current is None or current.state is not SessionState.READY:
            details = "missing session" if current is None else f"state={current.state.value}"
            raise AssertionError("idle reconciler changed state during Agent runner wait: " + details)
        if accepted["command_id"] not in {item.command_id for item in current.record.active_commands}:
            raise AssertionError("reconciler lost the durable Agent command reservation while it was running")
        result = await commands.wait(accepted["command_id"], check=True)
    if b"turn complete: LLM wait simulation" not in result.stdout:
        raise AssertionError(f"one-turn Agent runner returned unexpected output: {result.stdout!r}")

    deadline = time.monotonic() + idle_timeout_seconds + 30
    while time.monotonic() < deadline:
        errors = await reconciler.reconcile_once()
        if errors:
            raise RuntimeError("reconciler failed after Agent runner finished: " + "; ".join(errors))
        current = await manager.get(key)
        if current is not None and current.state is SessionState.SUSPENDED:
            return
        await asyncio.sleep(1)
    raise TimeoutError("session did not suspend after the one-turn Agent runner completed and became idle")


async def wait_for_workspace_cleanup(core, namespace: str, sandbox_uid: str, volume_name: str | None, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        claims = await core.list_namespaced_persistent_volume_claim(namespace)
        owned = any(
            owner.uid == sandbox_uid
            for claim in claims.items
            for owner in (claim.metadata.owner_references or [])
        )
        pv_exists = False
        if volume_name:
            try:
                await core.read_persistent_volume(volume_name)
                pv_exists = True
            except ApiException as exc:
                if exc.status != 404:
                    raise
        if not owned and not pv_exists:
            return
        await asyncio.sleep(2)
    raise TimeoutError(f"workspace cleanup timed out for Sandbox UID {sandbox_uid}")


async def run_sqlite_pvc_reopen_probe(core, namespace: str, image: str, storage_class: str, timeout: int) -> None:
    """Exercise an RWO PVC mount and SQLite reopen across writer Pod replacement."""
    claim_name = "session-state-reopen-probe"
    await core.create_namespaced_persistent_volume_claim(namespace, client.V1PersistentVolumeClaim(
        metadata=client.V1ObjectMeta(name=claim_name, labels={"app.kubernetes.io/part-of": "gke-session-sandbox-validation"}),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"], storage_class_name=storage_class,
            resources=client.V1ResourceRequirements(requests={"storage": "1Gi"}),
        ),
    ))
    writer_script = "\n".join([
        "import pathlib, sqlite3",
        "mount = pathlib.Path('/var/lib/session-sandbox')",
        "assert mount.is_mount(), 'session repository path is not a mounted PVC'",
        "connection = sqlite3.connect(mount / 'sessions.sqlite3')",
        "connection.execute('CREATE TABLE session_state (session_id TEXT PRIMARY KEY, generation INTEGER, state TEXT)')",
        "connection.execute('INSERT INTO session_state VALUES (?, ?, ?)', ('pod-replacement', 7, 'suspended'))",
        "connection.commit()",
        "connection.close()",
        "print('sqlite-pvc-write-ok mounted=true')",
    ])
    reader_script = "\n".join([
        "import pathlib, sqlite3",
        "mount = pathlib.Path('/var/lib/session-sandbox')",
        "assert mount.is_mount(), 'session repository path is not a mounted PVC'",
        "connection = sqlite3.connect(mount / 'sessions.sqlite3')",
        "record = connection.execute('SELECT generation, state FROM session_state WHERE session_id = ?', ('pod-replacement',)).fetchone()",
        "assert record == (7, 'suspended'), f'unexpected persisted record: {record!r}'",
        "print('sqlite-pvc-reopen-ok generation=7 state=suspended')",
        "connection.close()",
    ])
    for name, script in (("session-state-writer", writer_script), ("session-state-reader", reader_script)):
        await core.create_namespaced_pod(namespace, client.V1Pod(
            metadata=client.V1ObjectMeta(name=name, labels={"app.kubernetes.io/part-of": "gke-session-sandbox-validation"}),
            spec=client.V1PodSpec(
                restart_policy="Never", security_context=client.V1PodSecurityContext(
                    run_as_non_root=True, run_as_user=1000, run_as_group=1000, fs_group=1000,
                ),
                containers=[client.V1Container(
                    name="sqlite-repository-probe", image=image, image_pull_policy="IfNotPresent",
                    command=["python3", "-c", script],
                    volume_mounts=[client.V1VolumeMount(name="session-state", mount_path="/var/lib/session-sandbox")],
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": "50m", "memory": "64Mi"}, limits={"cpu": "250m", "memory": "256Mi"},
                    ),
                )],
                volumes=[client.V1Volume(
                    name="session-state", persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name=claim_name),
                )],
            ),
        ))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pod = await core.read_namespaced_pod(name, namespace)
            phase = pod.status.phase
            if phase in {"Succeeded", "Failed"}:
                logs = await core.read_namespaced_pod_log(name, namespace)
                if phase != "Succeeded":
                    raise RuntimeError(f"SQLite PVC probe Pod {name} failed: {logs}")
                expected_log = (
                    "sqlite-pvc-write-ok mounted=true" if name == "session-state-writer"
                    else "sqlite-pvc-reopen-ok generation=7 state=suspended"
                )
                if expected_log not in logs:
                    raise AssertionError(f"SQLite PVC Pod {name} returned unexpected output: {logs!r}")
                print(logs.strip())
                break
            await asyncio.sleep(2)
        else:
            raise TimeoutError(f"SQLite PVC probe Pod {name} did not complete")
        await core.delete_namespaced_pod(
            name, namespace, body=client.V1DeleteOptions(grace_period_seconds=0)
        )
        while time.monotonic() < deadline:
            try:
                await core.read_namespaced_pod(name, namespace)
            except ApiException as exc:
                if exc.status == 404:
                    break
                raise
            await asyncio.sleep(1)
        else:
            raise TimeoutError(f"SQLite PVC probe Pod {name} was not removed before reusing the RWO claim")


async def run_external_workspace_loss_e2e(
    manager, backend, core, custom, pvc_manager, namespace: str, run_id: str, timeout: int,
):
    """Delete only a run-owned Sandbox and verify loss notification plus a fresh workspace generation."""
    key = SessionKey(tenant_id=f"validation-loss-{run_id}", session_id=f"external-delete-{run_id}")
    previous = await manager.ensure(key)
    old_ref = previous.sandbox_ref
    assert old_ref is not None
    old_claims = await pvc_manager.list_owned(old_ref)
    assert len(old_claims) == 1
    old_claim = await core.read_namespaced_persistent_volume_claim(old_claims[0].name, namespace)
    old_volume_name = old_claim.spec.volume_name

    old_sandbox = await custom.get_namespaced_custom_object(
        "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", old_ref.name
    )
    selector = old_sandbox.get("status", {}).get("selector")
    old_pods = await core.list_namespaced_pod(namespace, label_selector=selector)
    old_pod = next(pod for pod in old_pods.items if pod.status.phase == "Running")
    subprocess.run([
        "kubectl", "exec", old_pod.metadata.name, "-n", namespace, "-c", "sandboxd", "--",
        "python3", "-c", "from pathlib import Path; Path('/workspace/external-loss-marker').write_text('old generation')",
    ], check=True, capture_output=True, text=True, timeout=30)

    await custom.delete_namespaced_custom_object(
        "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", old_ref.name,
        body=client.V1DeleteOptions(preconditions=client.V1Preconditions(uid=old_ref.uid)),
    )
    await backend.wait_deleted(old_ref, timeout_seconds=timeout)
    await wait_for_workspace_cleanup(core, namespace, old_ref.uid, old_volume_name, timeout)

    errors = await LifecycleReconciler(manager).reconcile_once()
    if errors:
        raise RuntimeError("reconciler failed while detecting external workspace loss: " + "; ".join(errors))
    lost = await manager.get(key)
    if lost is None or lost.state.value != "lost":
        raise AssertionError("external Sandbox deletion was not recorded as a lost workspace")
    event = next((item for item in lost.pending_context_events if item.acked_at is None), None)
    if event is None or event.event_type.value != "workspace_lost":
        raise AssertionError("external Sandbox deletion did not create a pending workspace_lost event")
    if "shared code remains mounted read-only" not in event.context_message.lower():
        raise AssertionError("workspace loss context did not explain that shared code remains available")

    current = await manager.ensure(key)
    if current.generation != previous.generation + 1 or current.state is not SessionState.READY:
        raise AssertionError("workspace loss did not create a ready next generation")
    if current.pending_context_events[0].event_id != event.event_id:
        raise AssertionError("workspace loss event was not carried into the next generation")
    new_sandbox = await custom.get_namespaced_custom_object(
        "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", current.sandbox_ref.name
    )
    new_pods = await core.list_namespaced_pod(namespace, label_selector=new_sandbox.get("status", {}).get("selector"))
    new_pod = next(pod for pod in new_pods.items if pod.status.phase == "Running")
    empty_result = subprocess.run([
        "kubectl", "exec", new_pod.metadata.name, "-n", namespace, "-c", "sandboxd", "--",
        "python3", "-c", (
            "from pathlib import Path; "
            "assert not Path('/workspace/external-loss-marker').exists(), 'old workspace file survived generation replacement'; "
            "print('workspace-empty-after-loss-ok')"
        ),
    ], check=True, capture_output=True, text=True, timeout=30)
    print(empty_result.stdout.strip())
    new_claims = await pvc_manager.list_owned(current.sandbox_ref)
    if len(new_claims) != 1:
        raise AssertionError("new workspace generation did not get exactly one owned PVC")
    new_claim = await core.read_namespaced_persistent_volume_claim(new_claims[0].name, namespace)
    return key, current, new_claim.spec.volume_name, event.event_id


async def run_retention_expiry_e2e(
    manager, core, custom, pvc_manager, namespace: str, run_id: str, timeout: int,
    *, retention_seconds: int,
):
    """Wait the configured retention interval, then verify expiry cleanup and context delivery."""
    key = SessionKey(tenant_id=f"validation-expiry-{run_id}", session_id=f"retention-expired-{run_id}")
    previous = await manager.ensure(key)
    old_ref = previous.sandbox_ref
    assert old_ref is not None
    old_claims = await pvc_manager.list_owned(old_ref)
    assert len(old_claims) == 1
    old_claim = await core.read_namespaced_persistent_volume_claim(old_claims[0].name, namespace)
    old_volume_name = old_claim.spec.volume_name
    old_sandbox = await custom.get_namespaced_custom_object(
        "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", old_ref.name
    )
    old_pods = await core.list_namespaced_pod(namespace, label_selector=old_sandbox.get("status", {}).get("selector"))
    old_pod = next(pod for pod in old_pods.items if pod.status.phase == "Running")
    subprocess.run([
        "kubectl", "exec", old_pod.metadata.name, "-n", namespace, "-c", "sandboxd", "--",
        "python3", "-c", "from pathlib import Path; Path('/workspace/retention-marker').write_text('expired generation')",
    ], check=True, capture_output=True, text=True, timeout=30)

    test_lifecycle = manager.config.lifecycle.model_copy(update={"retention_seconds": retention_seconds})
    test_config = manager.config.model_copy(update={"lifecycle": test_lifecycle})
    retention_manager = SandboxManager(
        test_config,
        manager.repository,
        manager.backend,
        template=manager._template,
        pvc_manager=pvc_manager,
    )
    proxy_runner, proxy_endpoint = await start_gate_proxy(old_ref.name, namespace)
    original_runtime_endpoint = manager.backend.runtime_endpoint

    async def retention_runtime_endpoint(_sandbox_ref, *, tracker_port=8081):
        return proxy_endpoint

    manager.backend.runtime_endpoint = retention_runtime_endpoint
    try:
        suspended = await retention_manager.suspend(previous)
    finally:
        manager.backend.runtime_endpoint = original_runtime_endpoint
        await proxy_runner.cleanup()
    if (
        suspended.state is not SessionState.SUSPENDED
        or suspended.record.suspended_at is None
        or suspended.record.expires_at is None
    ):
        raise AssertionError("retention probe did not persist a suspended state and expiry deadline")
    deadline = suspended.record.expires_at
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining > 0:
        await asyncio.sleep(remaining)
    observed_at = datetime.now(timezone.utc)
    if observed_at < deadline:
        raise AssertionError("retention probe continued before the configured expiry deadline")
    print(
        "retention-deadline-reached "
        f"configured_seconds={retention_seconds} "
        f"suspended_at={suspended.record.suspended_at.isoformat()} "
        f"expires_at={deadline.isoformat()} observed_at={observed_at.isoformat()}"
    )

    current = await retention_manager.ensure(key)
    if current.generation != previous.generation + 1 or current.state is not SessionState.READY:
        raise AssertionError("expired retention record did not produce a ready next generation")
    event = next((item for item in current.pending_context_events if item.acked_at is None), None)
    if (event is None or event.event_type.value != "workspace_cleared"
            or event.reason != "retention-expired"):
        raise AssertionError("retention cleanup did not deliver a workspace_cleared event")
    if "previous workspace was cleared" not in event.context_message.lower():
        raise AssertionError("retention context message did not explain workspace loss")
    await retention_manager.backend.wait_deleted(old_ref, timeout_seconds=timeout)
    await wait_for_workspace_cleanup(core, namespace, old_ref.uid, old_volume_name, timeout)

    new_ref = current.sandbox_ref
    assert new_ref is not None
    new_sandbox = await custom.get_namespaced_custom_object(
        "agents.x-k8s.io", "v1beta1", namespace, "sandboxes", new_ref.name
    )
    new_pods = await core.list_namespaced_pod(namespace, label_selector=new_sandbox.get("status", {}).get("selector"))
    new_pod = next(pod for pod in new_pods.items if pod.status.phase == "Running")
    check = subprocess.run([
        "kubectl", "exec", new_pod.metadata.name, "-n", namespace, "-c", "sandboxd", "--",
        "python3", "-c", (
            "from pathlib import Path; "
            "assert not Path('/workspace/retention-marker').exists(), 'expired workspace file survived'; "
            "print('workspace-empty-after-retention-ok')"
        ),
    ], check=True, capture_output=True, text=True, timeout=30)
    print(check.stdout.strip())
    new_claims = await pvc_manager.list_owned(new_ref)
    if len(new_claims) != 1:
        raise AssertionError("retention-created generation did not get exactly one owned PVC")
    new_claim = await core.read_namespaced_persistent_volume_claim(new_claims[0].name, namespace)
    return key, current, new_claim.spec.volume_name, event.event_id


def run_sandbox_network_probes(pod_name: str, namespace: str) -> str:
    command = ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--",
               "python3", "-m", "gke_session_sandbox.network_probe"]
    for probe in (("dns", "example.com"), ("tcp", "api.anthropic.com", "443")):
        result = subprocess.run([*command, *probe], check=True, capture_output=True, text=True, timeout=15)
        print(result.stdout.strip())
    tracker_health = subprocess.run(
        [*command, "http", "http://127.0.0.1:8081/healthz"],
        check=True, capture_output=True, text=True, timeout=15,
    )
    health_payload = json.loads(tracker_health.stdout.split(" body=", 1)[1])
    if health_payload.get("tracker_generation") != 1 or health_payload.get("sandboxd") != "connected":
        raise AssertionError(f"tracker health did not report startup generation and sandboxd connection: {tracker_health.stdout}")
    print(tracker_health.stdout.strip())
    reservation = subprocess.run(
        [*command, "tracker", "http://127.0.0.1:8081"],
        check=False, capture_output=True, text=True, timeout=90,
    )
    if reservation.returncode:
        raise AssertionError(f"Python tracker runtime probe failed: {reservation.stdout}{reservation.stderr}")
    print(reservation.stdout.strip())
    active_id = next((part.removeprefix("active=") for part in reservation.stdout.split() if part.startswith("active=")), None)
    if not active_id:
        raise AssertionError(f"runtime probe did not report the active command ID: {reservation.stdout}")
    denied = subprocess.run([*command, "tcp", "neverssl.com", "443"], capture_output=True, text=True, timeout=15)
    if denied.returncode == 0 or "probe failed" not in denied.stderr:
        labels = subprocess.run(
            ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "jsonpath={.metadata.labels}"],
            capture_output=True, text=True,
        ).stdout
        fqdn_name = subprocess.run(
            ["kubectl", "get", "fqdnnetworkpolicy", "-n", namespace,
             "-l", "session-sandbox.example.com/managed=true", "-o", "jsonpath={.items[0].metadata.name}"],
            capture_output=True, text=True,
        ).stdout
        fqdn_status = subprocess.run(
            ["kubectl", "describe", "fqdnnetworkpolicy", fqdn_name, "-n", namespace],
            capture_output=True, text=True,
        ).stdout if fqdn_name else "no FQDNNetworkPolicy found"
        policies = subprocess.run(
            ["kubectl", "get", "fqdnnetworkpolicy,networkpolicy", "-n", namespace, "-l", "session-sandbox.example.com/managed=true", "-o", "yaml"],
            capture_output=True, text=True,
        ).stdout
        raise AssertionError(
            f"unconfigured FQDN egress unexpectedly succeeded: {denied.stdout}{denied.stderr}; "
            f"pod_labels={labels}; fqdn_status={fqdn_status}; policies={policies}"
        )
    print("fqdn-egress-denied host=neverssl.com port=443")
    run_tracker_restart_probe(pod_name, namespace, active_id)
    return active_id


def cancel_probe_command(pod_name: str, namespace: str, command_id: str) -> None:
    script = "\n".join([
        "import json, time, urllib.request",
        f"command_id = {command_id!r}",
        "base = 'http://127.0.0.1:8081/v1/commands/' + command_id",
        "with urllib.request.urlopen(base, timeout=5) as response: record = json.load(response)",
        "if record.get('state') == 'running':",
        "    request = urllib.request.Request(base + '/cancel', data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')",
        "    urllib.request.urlopen(request, timeout=5).read()",
        "    deadline = time.monotonic() + 15",
        "    while time.monotonic() < deadline:",
        "        with urllib.request.urlopen(base, timeout=5) as response: record = json.load(response)",
        "        if record.get('state') == 'finished': break",
        "        time.sleep(0.1)",
        "    else: raise SystemExit('probe command remained active')",
    ])
    subprocess.run(
        ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--", "python3", "-c", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def run_tracker_restart_probe(pod_name: str, namespace: str, interrupted_command_id: str) -> None:
    def restart_count() -> int:
        result = subprocess.run(
            ["kubectl", "get", "pod", pod_name, "-n", namespace,
             "-o", 'jsonpath={.status.containerStatuses[?(@.name=="sandboxd")].restartCount}'],
            check=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout or "0")

    initial = restart_count()
    subprocess.run(
        ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--",
         "/bin/sh", "-c", "pkill -TERM -f 'gke_session_sandbox[.]tracker'"],
        capture_output=True,
        text=True,
    )
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        if restart_count() > initial:
            subprocess.run(
                ["kubectl", "wait", "--for=condition=Ready", "pod", pod_name, "-n", namespace, "--timeout=120s"],
                check=False,
                capture_output=True,
                text=True,
            )
            health = subprocess.run(
                ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--",
                 "python3", "-m", "gke_session_sandbox.network_probe", "http", "http://127.0.0.1:8081/healthz"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout
            body_start = health.find("body=")
            payload = json.loads(health[body_start + len("body="):]) if body_start >= 0 else {}
            if payload.get("tracker_generation") != 2 or payload.get("sandboxd") != "connected":
                raise AssertionError(f"tracker did not recover at generation 2: {health}")
            identity = subprocess.run(
                ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--", "python3", "-c",
                 "import json,sys; d=json.load(open('/workspace/.session-runtime/commands.json')); print(json.dumps(d['commands'][sys.argv[1]].get('identity'))) ", interrupted_command_id],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            process_groups = subprocess.run(
                ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--", "ps", "-eo", "pid=,pgid=,comm="],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            reservation_result = subprocess.run(
                ["kubectl", "exec", pod_name, "-n", namespace, "-c", "sandboxd", "--",
                 "python3", "-m", "gke_session_sandbox.network_probe", "tracker", "http://127.0.0.1:8081", interrupted_command_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            reservation = reservation_result.stdout
            if reservation_result.returncode != 0 or "duplicate=200" not in reservation or "conflict=409" not in reservation or "exit=7" not in reservation or "recovered=tracker_restart" not in reservation:
                raise AssertionError(
                    f"finished command result was not recovered after tracker restart: {reservation}{reservation_result.stderr}; "
                    f"identity={identity}; visible_processes={process_groups}"
                )
            print(f"tracker-restart-recovered generation=2 container_restarts={restart_count() - initial}")
            return
        time.sleep(2)
    raise TimeoutError("sandbox container did not restart after its tracker exited")


def run_tracker_bypass_probe(sandbox_name: str, namespace: str, pod_ip: str) -> str:
    if not pod_ip:
        raise AssertionError("sandbox Pod has no IP for tracker bypass probe")
    control_namespace = "session-sandbox-system"
    job_name = f"tracker-bypass-{sandbox_name[-8:]}"
    image = os.environ.get(
        "RUNTIME_SMOKE_IMAGE",
        "us-central1-docker.pkg.dev/nnyn-dev/research-gke-agent-sandbox-with-sandboxd-images/"
        "runtime-smoke@sha256:28c5fa74e6e5545ab8ca83361ec4cd563d064270e722ea5eda58c18a05e40dcd",
    )
    job = {
        "apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": job_name, "namespace": control_namespace},
        "spec": {
            "backoffLimit": 0,
            "template": {"spec": {
                "restartPolicy": "Never", "automountServiceAccountToken": False,
                "containers": [{
                    "name": "runner", "image": image, "imagePullPolicy": "IfNotPresent",
                    "env": [{"name": "SANDBOX_TARGETS", "value": f"{sandbox_name}.{namespace}.svc.cluster.local,{pod_ip}"}],
                    "resources": {"requests": {"cpu": "50m", "memory": "64Mi"}, "limits": {"cpu": "250m", "memory": "128Mi"}},
                }],
            }},
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as stream:
        yaml.safe_dump(job, stream, sort_keys=False)
        manifest_path = stream.name
    try:
        subprocess.run(["kubectl", "apply", "-f", manifest_path], check=True, capture_output=True, text=True)
    finally:
        os.unlink(manifest_path)

    try:
        wait = subprocess.run(
            ["kubectl", "wait", "--for=condition=failed", f"job/{job_name}", "-n", control_namespace, "--timeout=45s"],
            capture_output=True,
            text=True,
        )
        if wait.returncode != 0:
            complete = subprocess.run(
                ["kubectl", "wait", "--for=condition=complete", f"job/{job_name}", "-n", control_namespace, "--timeout=1s"],
                capture_output=True,
                text=True,
            )
            if complete.returncode == 0:
                raise AssertionError("direct sandboxd gRPC on port 9090 unexpectedly succeeded")
        logs = subprocess.check_output(["kubectl", "logs", f"job/{job_name}", "-n", control_namespace], text=True)
        if "gRPC Execute" not in logs:
            raise AssertionError(f"direct gRPC probe failed for an unexpected reason: {logs}; {wait.stderr}")
        persisted = subprocess.check_output(
            ["kubectl", "exec", sandbox_name, "-n", namespace, "-c", "sandboxd", "--", "/bin/cat", "/workspace/management-runner.txt"],
            text=True,
        )
        if persisted != "written-by-rest-read-by-grpc\n":
            raise AssertionError(f"management REST ingress was not allowed: {persisted!r}")
        print("network-policy-rest-allowed tracker-direct-grpc-denied port=9090")
    finally:
        subprocess.run(
            ["kubectl", "delete", "job", job_name, "-n", control_namespace, "--ignore-not-found=true"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return job_name


if __name__ == "__main__":
    asyncio.run(main())
