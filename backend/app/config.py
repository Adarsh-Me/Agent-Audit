"""Application settings — env vars per TECHSPEC §3.1."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import AGENT_SPEND_CAP_INR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    opencode_zen_api_key: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    database_url: str = "sqlite+aiosqlite:///./agentaudit.db"
    cost_cap_usd: float = 30.0
    port: int = 8000
    # Agent money-policy (SAFETY.md): per-link spend ceiling + purchasable-SKU
    # allowlist override. Empty agent_allowed_skus → AGENT_DEFAULT_ALLOWED_SKUS.
    max_agent_spend_inr: int = AGENT_SPEND_CAP_INR
    agent_allowed_skus: str = ""  # comma-separated, e.g. "sku_007,sku_017"


@lru_cache
def get_settings() -> Settings:
    return Settings()
