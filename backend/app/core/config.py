"""App settings, read from environment variables, backend/.env or the repo-root .env."""

import re
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Later files win, so backend/.env overrides the repo-root .env.
ENV_FILES = (BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, extra="ignore")

    app_name: str = "PersonalIQ"
    version: str = "0.1.0"
    environment: str = "development"

    # Any Postgres URL works; the driver is normalised to psycopg in database.py.
    database_url: str = ""

    frontend_origin: str = "http://localhost:3000"

    # LLM: any OpenAI-compatible endpoint. Default is NVIDIA's (build.nvidia.com).
    llm_base_url: str = Field("https://integrate.api.nvidia.com/v1", validation_alias=AliasChoices("LLM_BASE_URL", "NVIDIA_BASE_URL"))
    llm_api_key: str = Field("", validation_alias=AliasChoices("LLM_API_KEY", "NVIDIA_API_KEY"))
    llm_model: str = Field("nvidia/nemotron-3-nano-30b-a3b", validation_alias=AliasChoices("LLM_MODEL", "NVIDIA_MODEL"))
    llm_provider: str = "NVIDIA"
    llm_timeout_seconds: float = 12

    # OpenRouter (also OpenAI-compatible, serves Nemotron). Used when its key is set and LLM_API_KEY isn't.
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-nano-30b-a3b"
    openrouter_timeout_seconds: str | None = None  # accepts "90" or "90s"
    openrouter_base_url: str = Field(
        "https://openrouter.ai/api/v1", validation_alias=AliasChoices("OPENROUTER_BASE_URL", "OPENROUTER_URL", "OPENROUTER_API_URL")
    )

    @model_validator(mode="after")
    def _pick_llm(self) -> "Settings":
        if not self.llm_api_key and self.openrouter_api_key:
            self.llm_api_key = self.openrouter_api_key
            self.llm_model = self.openrouter_model
            self.llm_base_url = self.openrouter_base_url
            self.llm_provider = "OpenRouter"
            digits = re.sub(r"[^\d.]", "", self.openrouter_timeout_seconds or "")
            if digits:
                self.llm_timeout_seconds = float(digits)
        # Accept a pasted full endpoint like ".../v1/chat/completions": the client adds that part itself.
        self.llm_base_url = self.llm_base_url.strip().removesuffix("/").removesuffix("/chat/completions")
        return self

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_mode: str = "sandbox"  # this build refuses anything else
    paypal_webhook_id: str = ""
    # Currency PayPal charges in. Orders are shown in the user's home currency and converted at the
    # fixed demo rate. USD by default because PayPal only accepts INR for PayPal India accounts.
    paypal_currency: str = "USD"
    paypal_timeout_seconds: float = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
