"""JSON serialization shared by the driving adapters (CLI --json, MCP tools).

Models dump API-native camelCase with explicit nulls dropped, so a `get`
result is valid `update` input and unknown API fields ride along untouched.
"""

from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value
