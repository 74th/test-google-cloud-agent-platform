"""Runtime request contracts for the combined Agent Gateway + long-running query verification."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

DEFAULT_DELAY_SECONDS = 10
MAX_DELAY_SECONDS = 3600
ClassMethod = Literal["query", "stream_query"]


class MessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class MessageRequest(BaseModel):
    """The synchronous Agent Platform request contract (`query` / `stream_query`)."""

    class_method: ClassMethod = Field(validation_alias=AliasChoices("class_method", "classMethod"))
    input: MessageInput


class QueryJobInput(BaseModel):
    """The object the query-job SDK writes to its GCS input object."""

    verification_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    delay_seconds: int = Field(default=DEFAULT_DELAY_SECONDS, ge=1, le=MAX_DELAY_SECONDS)

    @field_validator("verification_id")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("verification_id must not be blank")
        return value


class QueryJobRequest(BaseModel):
    """The root ``POST /`` body Agent Engine delivers for a query job."""

    input: QueryJobInput
    class_method: str | None = Field(default=None, validation_alias=AliasChoices("class_method", "classMethod"))

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
