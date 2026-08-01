from argparse import Namespace

from scripts.deploy_agent import VERTEX_HAIKU_MODEL, build_config


def test_deployment_uses_service_account_vertex_authentication() -> None:
    config = build_config(
        Namespace(
            display_name="bus-agent",
            image_uri="us-central1-docker.pkg.dev/nnyn-dev/agents/bus:latest",
            vertex_project="nnyn-dev",
            vertex_region="global",
            service_account="claude-agent-runtime@nnyn-dev.iam.gserviceaccount.com",
        )
    )
    env = config["env_vars"]
    assert env == {
        "CLAUDE_CODE_USE_VERTEX": "1",
        "ANTHROPIC_VERTEX_PROJECT_ID": "nnyn-dev",
        "CLOUD_ML_REGION": "global",
        "ANTHROPIC_MODEL": VERTEX_HAIKU_MODEL,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": VERTEX_HAIKU_MODEL,
        "VERTEX_REGION_CLAUDE_HAIKU_4_5": "us-east5",
    }
    assert "ANTHROPIC_API_KEY" not in env
    assert config["service_account"].startswith("claude-agent-runtime@")
