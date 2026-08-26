"""Auth-related domain models."""

from pydantic import BaseModel, ConfigDict

from yoto.domain.base import ApiModel


class TokenSet(BaseModel):
    """An OAuth token bundle as persisted between runs.

    ``expires_at`` is absolute epoch seconds, computed when the tokens were
    obtained (Yoto's refresh tokens are single-use, so a TokenSet is immutable:
    every refresh produces a whole new set).
    """

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str | None = None
    expires_at: float

    def expires_within(self, seconds: float, *, now: float) -> bool:
        return self.expires_at - now <= seconds


class UserInfo(ApiModel):
    """Identity derived from the access token's JWT claims (+ optional userinfo)."""

    sub: str | None = None
    name: str | None = None
    email: str | None = None
    scope: str | None = None
    expires_at: float | None = None
