from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    doc_api_base_url: str
    doc_api_key: str = ""
    db_connection_string: str
    model_name: str = "claude-sonnet-4-6"

    class Config:
        env_file = ".env"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Lazy initialisation ensures that importing this module does not
    immediately require environment variables to be present — useful
    in test environments where variables are patched at test time.
    """
    return Settings()


# Convenience proxy kept for backwards-compat with direct `settings.*` usage.
# Access is deferred until the attribute is first read, so import-time
# failures are avoided when the .env file / env vars are not yet set.
class _SettingsProxy:
    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


settings = _SettingsProxy()
