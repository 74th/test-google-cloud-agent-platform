"""Runtime request contract and operation definitions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

DEFAULT_DELAY_SECONDS = 10
MAX_DELAY_SECONDS = 3600
UNARY_METHODS = frozenset({"query", "async_query"})
STREAM_METHODS = frozenset({"stream_query", "async_stream_query"})
SUPPORTED_METHODS = UNARY_METHODS | STREAM_METHODS
ClassMethod = Literal["query", "async_query", "stream_query", "async_stream_query"]


class QueryInput(BaseModel):
    verification_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    delay_seconds: int = Field(default=DEFAULT_DELAY_SECONDS, ge=1, le=MAX_DELAY_SECONDS)

    @field_validator("verification_id")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("verification_id must not be blank")
        return value


class RuntimeRequest(BaseModel):
    class_method: ClassMethod = Field(validation_alias=AliasChoices("class_method", "classMethod"))
    input: QueryInput

    @model_validator(mode="before")
    @classmethod
    def unwrap_agent_platform_input(cls, value: Any) -> Any:
        """Accept the SDK's documented outer ``input`` argument without logging it."""
        if isinstance(value, dict) and isinstance(value.get("input"), dict):
            input_value = value["input"]
            if isinstance(input_value.get("input"), dict) and "verification_id" not in input_value:
                return {**value, "input": input_value["input"]}
        return value


class LongRunningRequest(BaseModel):
    """The object written by the query-job SDK to its GCS input object."""

    input: QueryInput
    class_method: ClassMethod | None = Field(
        default=None, validation_alias=AliasChoices("class_method", "classMethod")
    )

    @model_validator(mode="before")
    @classmethod
    def unwrap_agent_platform_input(cls, value: Any) -> Any:
        if isinstance(value, dict) and isinstance(value.get("input"), dict):
            nested = value["input"]
            if isinstance(nested.get("input"), dict) and "verification_id" not in nested:
                return {**value, "input": nested["input"]}
        return value


def json_response(output: str) -> dict[str, str]:
    return {"output": output}


def request_metadata(request: RuntimeRequest) -> dict[str, Any]:
    return {
        "class_method": request.class_method,
        "verification_id": request.input.verification_id,
        "delay_seconds": request.input.delay_seconds,
    }
