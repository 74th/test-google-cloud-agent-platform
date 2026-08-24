from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    REGISTRY_DISCOVERY = "registry_discovery"
    METADATA_VALIDATION = "metadata_validation"
    TOKEN_GENERATION = "token_generation"
    GATEWAY_AUTHORIZATION = "gateway_authorization"
    ENDPOINT_AUTHORIZATION = "endpoint_authorization"
    MCP_PROTOCOL = "mcp_protocol"
    TOOL_EXECUTION = "tool_execution"


class ValidationError(RuntimeError):
    """An error safe to return without credential or token material."""

    def __init__(self, stage: Stage, message: str):
        super().__init__(message)
        self.stage = stage


def sanitize_exception(stage: Stage, error: BaseException) -> ValidationError:
    return ValidationError(stage, f"{stage.value} failed ({type(error).__name__})")
