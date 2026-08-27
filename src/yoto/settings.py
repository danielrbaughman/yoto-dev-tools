"""Application configuration.

Precedence (first wins): explicit constructor kwargs (CLI flags) > environment
variables (YOTO_*, case-insensitive) > .env in the current directory >
~/.config/yoto/config.json > defaults.
"""

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# NB: yoto.dev documents the :manage scopes as including :view, but the API
# enforces the literal :view scope strings on some endpoints (observed live on
# GET /content/{cardId}: 403 wanting user:content:view/family:library:view),
# so request them explicitly.
DEFAULT_SCOPES = (
    "openid profile offline_access"
    " user:content:view user:content:manage user:icons:manage"
    " family:library:view family:library:manage"
    " family:devices:view family:devices:manage family:devices:control"
)


# Public OAuth client registered for yoto-dev-tools at https://dashboard.yoto.dev/
# (PKCE, no secret — safe to ship). Users may override it via YOTO_CLIENT_ID,
# .env, ~/.config/yoto/config.json, or `yoto auth login --client-id`.
DEFAULT_CLIENT_ID = "IWW7UabcNkTlZw5mwQBINqiWl3riIZXA"


def default_config_dir() -> Path:
    env = os.environ.get("YOTO_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    return Path("~/.config/yoto").expanduser()


class YotoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="yoto_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    client_id: str = DEFAULT_CLIENT_ID
    access_token: str | None = None  # YOTO_ACCESS_TOKEN: headless/CI override
    api_url: str = "https://api.yotoplay.com"
    auth_url: str = "https://login.yotoplay.com"
    mqtt_host: str = "aqrphjqbp3u2z-ats.iot.eu-west-2.amazonaws.com"
    mqtt_authorizer: str = "PublicJWTAuthorizer"
    redirect_port: int = 8787
    scopes: str = DEFAULT_SCOPES
    config_dir: Path = default_config_dir()
    timeout: float = 30.0

    @field_validator("config_dir")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()

    @property
    def tokens_path(self) -> Path:
        return self.config_dir / "tokens.json"

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.redirect_port}/callback"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        json_source = JsonConfigSettingsSource(
            settings_cls, json_file=default_config_dir() / "config.json"
        )
        return (init_settings, env_settings, dotenv_settings, json_source)
