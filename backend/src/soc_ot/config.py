from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env.local",
        env_prefix="SOC_OT_",
        extra="ignore",
    )

    env: str = "local"
    authoring_mode: bool = False
    database_url: str = (
        "postgresql+psycopg://soc_ot_runtime:runtime_local@127.0.0.1:15432/soc_ot"
    )
    outcome_database_url: str = (
        "postgresql+psycopg://soc_ot_outcome:outcome_local@127.0.0.1:15432/soc_ot"
    )
    migration_database_url: str = (
        "postgresql+psycopg://soc_ot_admin:admin_local@127.0.0.1:15432/soc_ot"
    )
    api_host: str = "127.0.0.1"
    api_port: int = 18080
    frontend_port: int = 15173
    cors_allowed_origins: str = "http://127.0.0.1:15173"
    llm_mode: str = "replay"
    local_actor_id: str = "local-home-reviewer"
    role_model: str = "gpt-5.4-mini"
    challenger_model: str = "gpt-5.5"
    chair_model: str = "gpt-5.5"
    codex_cli_model: str = "gpt-5.6-luna"
    codex_cli_reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = (
        "high"
    )
    codex_cli_timeout_seconds: int = Field(default=180, ge=30, le=900)
    codex_cli_parallelism: int = Field(default=2, ge=1, le=8)
    max_case_runtime_seconds: int = 900
    role_timeout_seconds: int = 120
    max_case_cost_usd: float = 2.0
    max_evaluation_cost_usd: float = 25.0
    raw_provider_retention_days: int = 30
    role_input_cost_per_million_usd: float = 0.0
    role_output_cost_per_million_usd: float = 0.0
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
