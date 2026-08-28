from pathlib import Path


TERRAFORM = Path(__file__).resolve().parents[1] / "terraform"


def test_common_gateway_is_an_explicit_validated_input() -> None:
    variables = (TERRAFORM / "variables.tf").read_text()
    example = (TERRAFORM / "terraform.tfvars.example").read_text()
    assert 'variable "agent_gateway_id"' in variables
    assert "projects/nnyn-dev/locations/us-central1/agentGateways/" in variables
    assert "agent_gateway_id" in example
    assert "common-egress" in example
    assert "gateway_name" not in variables


def test_consumer_owns_only_runtime_supporting_resources() -> None:
    source = "\n".join(path.read_text() for path in TERRAFORM.glob("*.tf"))
    for forbidden in (
        "google_network_services_agent_gateway",
        "google_compute_network",
        "google_compute_subnetwork",
        "google_compute_network_attachment",
        "google_network_services_authz_extension",
        "google_network_security_authz_policy",
        "google_network_security_gateway_security_policy",
        "google_agent_registry_service",
        "import {",
    ):
        assert forbidden not in source
    assert 'resource "google_artifact_registry_repository" "agent_images"' in source
    assert 'resource "google_service_account" "runtime"' in source
    assert 'resource "google_project_iam_member" "runtime_platform_user"' in source


def test_common_registry_ownership_keeps_cabinet_office_default_deny() -> None:
    policy = (TERRAFORM / "egress-policy.yaml").read_text()
    common_readme = TERRAFORM.parents[1] / "common" / "README.md"
    assert "default_action: DENY" in policy
    assert "host: github.com" in policy
    assert "www8.cao.go.jp" not in policy
    assert "共通 Registry Service" in common_readme.read_text()
    assert "github.com" in common_readme.read_text()
    assert "www8.cao.go.jp" not in common_readme.read_text()


def test_provider_and_runtime_api_boundary_is_documented() -> None:
    versions = (TERRAFORM / "versions.tf").read_text()
    runtime = (TERRAFORM / "runtime.tf").read_text()
    contract = (Path(__file__).parents[1] / "evidence/20260828-provider-runtime-schema.md").read_text()
    assert 'source  = "hashicorp/google"' in versions
    assert 'source  = "hashicorp/google-nightly"' in versions
    assert "agentGateway" in contract
    assert 'provider = google-nightly' in runtime
    assert 'resource "google_vertex_ai_reasoning_engine" "runtime"' in runtime
    assert "agent_to_anywhere_config" in runtime


def test_ca_bundle_contract_is_present() -> None:
    dockerfile = (Path(__file__).parents[1] / "Dockerfile").read_text()
    build = (Path(__file__).parents[1] / "scripts/build_push.sh").read_text()
    assert "AGENT_GATEWAY_ROOT_CERTIFICATES" in dockerfile
    assert "update-ca-certificates" in dockerfile
    assert "agentGatewayCard.rootCertificates" in build
    assert "--secret" in build
