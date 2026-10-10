"""Run opt-in pytest integration tests in an isolated GKE Job."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import traceback
import uuid
from pathlib import Path

from kubernetes_asyncio import client, config as kube_config
from kubernetes_asyncio.client.exceptions import ApiException

from gke_session_sandbox.gke_validation import collect_failure_artifacts, verify_target


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=os.environ.get("GKE_PYTEST_IMAGE"))
    parser.add_argument("--control-namespace", default=os.environ.get("GKE_TEST_CONTROL_NAMESPACE", "session-sandbox-system"))
    parser.add_argument(
        "--runtime-image",
        default=os.environ.get(
            "GKE_SANDBOXD_IMAGE",
            "us-central1-docker.pkg.dev/nnyn-dev/research-gke-agent-sandbox-with-sandboxd-images/"
            "session-runtime@sha256:11eaa6651ef23b9a7e19a1138277a8e6b30b2400df461530a8016e043bc1baf3",
        ),
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--retention-seconds", type=int, default=30)
    parser.add_argument("--artifact-dir", default="artifacts/gke-pytest")
    parser.add_argument(
        "--verify-failure-artifacts",
        action="store_true",
        help="make the integration test fail intentionally to verify artifact capture and cleanup",
    )
    args = parser.parse_args()
    if not args.image:
        parser.error("set --image or GKE_PYTEST_IMAGE")
    if "@sha256:" not in args.image:
        parser.error("--image must be pinned by digest (repository@sha256:...)")
    if "@sha256:" not in args.runtime_image:
        parser.error("--runtime-image must be pinned by digest (repository@sha256:...)")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.retention_seconds <= 0:
        parser.error("--retention-seconds must be positive")

    project = os.environ["GKE_PROJECT_ID"]
    location = os.environ["GKE_LOCATION"]
    cluster = os.environ["GKE_CLUSTER_NAME"]
    current_context = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    active_project = subprocess.check_output(
        ["gcloud", "config", "get-value", "project"], text=True, stderr=subprocess.DEVNULL
    ).strip()
    context = verify_target(
        project, location, cluster, current_context=current_context, active_project=active_project
    )

    run_id = uuid.uuid4().hex[:12]
    namespace = f"gke-pytest-{run_id}"
    job_name = f"gke-pytest-{run_id}"
    service_account_name = f"gke-pytest-{run_id}"
    labels = {
        "app.kubernetes.io/part-of": "gke-session-sandbox-validation",
        "session-sandbox.example.com/run-id": run_id,
    }
    artifact_root = Path(args.artifact_dir).expanduser()
    if not artifact_root.is_absolute():
        artifact_root = Path(__file__).resolve().parents[1] / artifact_root
    artifact_root = artifact_root.resolve()

    await kube_config.load_kube_config(context=context)
    async with client.ApiClient() as api:
        core = client.CoreV1Api(api)
        rbac = client.RbacAuthorizationV1Api(api)
        batch = client.BatchV1Api(api)
        namespace_uid: str | None = None
        service_account_uid: str | None = None
        job_uid: str | None = None
        primary_failure: BaseException | None = None
        pytest_logs = ""
        try:
            created_namespace = await core.create_namespace(
                client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace, labels=labels))
            )
            namespace_uid = created_namespace.metadata.uid
            service_account = await core.create_namespaced_service_account(
                args.control_namespace,
                client.V1ServiceAccount(metadata=client.V1ObjectMeta(name=service_account_name, labels=labels)),
            )
            service_account_uid = service_account.metadata.uid
            await rbac.create_namespaced_role(
                namespace,
                client.V1Role(
                    metadata=client.V1ObjectMeta(name="gke-pytest", labels=labels),
                    rules=[
                        client.V1PolicyRule(
                            api_groups=[""],
                            resources=[
                                "configmaps", "events", "jobs", "persistentvolumeclaims", "pods", "pods/log",
                                "pods/exec",
                                "services",
                            ],
                            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
                        ),
                        client.V1PolicyRule(
                            api_groups=["agents.x-k8s.io"], resources=["sandboxes"],
                            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
                        ),
                        client.V1PolicyRule(
                            api_groups=["networking.k8s.io"], resources=["networkpolicies"],
                            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
                        ),
                        client.V1PolicyRule(
                            api_groups=["networking.gke.io"], resources=["fqdnnetworkpolicies"],
                            verbs=["get", "list", "watch", "create", "update", "patch", "delete"],
                        ),
                    ],
                ),
            )
            await rbac.create_namespaced_role_binding(
                namespace,
                client.V1RoleBinding(
                    metadata=client.V1ObjectMeta(name="gke-pytest", labels=labels),
                    role_ref=client.V1RoleRef(
                        api_group="rbac.authorization.k8s.io", kind="Role", name="gke-pytest"
                    ),
                    subjects=[client.RbacV1Subject(
                        kind="ServiceAccount", name=service_account_name, namespace=args.control_namespace
                    )],
                ),
            )
            job = client.V1Job(
                metadata=client.V1ObjectMeta(name=job_name, namespace=args.control_namespace, labels=labels),
                spec=client.V1JobSpec(
                    backoff_limit=0,
                    active_deadline_seconds=args.timeout,
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={**labels, "job-name": job_name}),
                        spec=client.V1PodSpec(
                            service_account_name=service_account_name,
                            automount_service_account_token=True,
                            restart_policy="Never",
                            containers=[client.V1Container(
                                name="pytest",
                                image=args.image,
                                image_pull_policy="IfNotPresent",
                                env=[
                                    client.V1EnvVar(name="GKE_TEST_NAMESPACE", value=namespace),
                                    client.V1EnvVar(name="GKE_TEST_RUN_ID", value=run_id),
                                    client.V1EnvVar(name="GKE_TEST_CONTROL_NAMESPACE", value=args.control_namespace),
                                    client.V1EnvVar(name="GKE_SANDBOXD_IMAGE", value=args.runtime_image),
                                    client.V1EnvVar(
                                        name="GKE_RETENTION_SECONDS", value=str(args.retention_seconds)
                                    ),
                                    client.V1EnvVar(
                                        name="GKE_TEST_FORCE_FAILURE",
                                        value="1" if args.verify_failure_artifacts else "0",
                                    ),
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "250m", "memory": "512Mi"},
                                    limits={"cpu": "1", "memory": "2Gi"},
                                ),
                            )],
                        ),
                    ),
                ),
            )
            created_job = await batch.create_namespaced_job(args.control_namespace, job)
            job_uid = created_job.metadata.uid
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                current_job = await batch.read_namespaced_job(job_name, args.control_namespace)
                conditions = current_job.status.conditions or []
                if any(item.type == "Complete" and item.status == "True" for item in conditions):
                    pods = await core.list_namespaced_pod(args.control_namespace, label_selector=f"job-name={job_name}")
                    for pod in pods.items:
                        logs = await core.read_namespaced_pod_log(
                            pod.metadata.name, args.control_namespace, container="pytest"
                        )
                        print(logs, end="" if logs.endswith("\n") else "\n")
                    print(f"gke-pytest-ok run_id={run_id} namespace={namespace} job_uid={job_uid}")
                    break
                if any(item.type == "Failed" and item.status == "True" for item in conditions):
                    pods = await core.list_namespaced_pod(
                        args.control_namespace, label_selector=f"job-name={job_name}"
                    )
                    for pod in pods.items:
                        try:
                            pytest_logs += await core.read_namespaced_pod_log(
                                pod.metadata.name, args.control_namespace, container="pytest"
                            )
                        except ApiException as log_error:
                            pytest_logs += f"could not collect pytest log for {pod.metadata.name}: {log_error}\n"
                    raise RuntimeError(
                        f"pytest Job failed: {json.dumps(current_job.status.to_dict(), sort_keys=True, default=str)}"
                    )
                await asyncio.sleep(2)
            else:
                raise TimeoutError(f"pytest Job exceeded {args.timeout} seconds")
        except BaseException as exc:
            primary_failure = exc
            try:
                if job_uid is not None and not pytest_logs:
                    try:
                        pods = await core.list_namespaced_pod(
                            args.control_namespace, label_selector=f"job-name={job_name}"
                        )
                        for pod in pods.items:
                            try:
                                pytest_logs += await core.read_namespaced_pod_log(
                                    pod.metadata.name, args.control_namespace, container="pytest"
                                )
                            except ApiException as log_error:
                                pytest_logs += f"could not collect pytest log for {pod.metadata.name}: {log_error}\n"
                    except ApiException as log_error:
                        pytest_logs += f"could not list pytest Job Pods: {log_error}\n"
                output = collect_failure_artifacts(
                    artifact_root,
                    run_id=run_id,
                    project=project,
                    context=context,
                    namespace=namespace,
                    namespace_uid=namespace_uid,
                    failure_details=(
                        "".join(traceback.format_exception(exc))
                        + (f"\n--- pytest Job logs ---\n{pytest_logs}\n" if pytest_logs else "")
                    ),
                )
                print(f"gke-pytest-failure-artifacts={output}")
            except Exception as artifact_error:
                print(f"could not save GKE pytest artifacts: {type(artifact_error).__name__}: {artifact_error}")
            raise
        finally:
            cleanup_errors: list[str] = []
            if job_uid is not None:
                try:
                    await batch.delete_namespaced_job(
                        job_name,
                        args.control_namespace,
                        body=client.V1DeleteOptions(
                            propagation_policy="Foreground",
                            preconditions=client.V1Preconditions(uid=job_uid),
                        ),
                    )
                    cleanup_deadline = time.monotonic() + min(args.timeout, 120)
                    while time.monotonic() < cleanup_deadline:
                        try:
                            await batch.read_namespaced_job(job_name, args.control_namespace)
                        except ApiException as exc:
                            if exc.status == 404:
                                break
                            raise
                        await asyncio.sleep(2)
                    else:
                        raise TimeoutError(f"pytest Job {job_name} was not deleted")
                except ApiException as exc:
                    if exc.status != 404:
                        cleanup_errors.append(f"Job {job_name} uid={job_uid}: {exc}")
                except TimeoutError as exc:
                    cleanup_errors.append(str(exc))
                except Exception as exc:
                    cleanup_errors.append(f"Job {job_name} uid={job_uid}: {type(exc).__name__}: {exc}")
            if service_account_uid is not None:
                try:
                    await core.delete_namespaced_service_account(
                        service_account_name,
                        args.control_namespace,
                        body=client.V1DeleteOptions(preconditions=client.V1Preconditions(uid=service_account_uid)),
                    )
                except ApiException as exc:
                    if exc.status != 404:
                        cleanup_errors.append(
                            f"ServiceAccount {service_account_name} uid={service_account_uid}: {exc}"
                        )
                except Exception as exc:
                    cleanup_errors.append(
                        f"ServiceAccount {service_account_name} uid={service_account_uid}: "
                        f"{type(exc).__name__}: {exc}"
                    )
            if namespace_uid is not None:
                try:
                    await core.delete_namespace(
                        namespace,
                        body=client.V1DeleteOptions(preconditions=client.V1Preconditions(uid=namespace_uid)),
                    )
                    deadline = time.monotonic() + args.timeout
                    while time.monotonic() < deadline:
                        try:
                            await core.read_namespace(namespace)
                        except ApiException as exc:
                            if exc.status == 404:
                                break
                            raise
                        await asyncio.sleep(2)
                    else:
                        raise TimeoutError(f"pytest namespace {namespace} was not deleted")
                except ApiException as exc:
                    if exc.status != 404:
                        cleanup_errors.append(f"namespace {namespace} uid={namespace_uid}: {exc}")
                except Exception as exc:
                    cleanup_errors.append(
                        f"namespace {namespace} uid={namespace_uid}: {type(exc).__name__}: {exc}"
                    )
            for cleanup_error in cleanup_errors:
                print(f"GKE pytest cleanup requires attention: {cleanup_error}")
            if cleanup_errors and primary_failure is None:
                raise RuntimeError("; ".join(cleanup_errors))


if __name__ == "__main__":
    asyncio.run(main())
