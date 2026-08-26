"""Base model for API-shaped domain entities."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """Wire-shaped model: camelCase aliases, unknown fields preserved.

    - ``extra="allow"`` keeps any field the API sends that we don't model, so
      fetch -> modify -> upsert round-trips are lossless.
    - ``alias_generator=to_camel`` maps snake_case attributes to the API's
      camelCase names; ``populate_by_name`` lets our own code construct models
      with snake_case keywords.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        alias_generator=to_camel,
    )

    def to_api(self) -> dict[str, Any]:
        """Serialize to the API's JSON shape (camelCase, no explicit nulls)."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)
