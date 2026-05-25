"""Central settings — loaded once at startup via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Ignore empty-string env vars (e.g. shell sets ANTHROPIC_API_KEY='')
        # so the .env file value wins over an empty system env var.
        env_ignore_empty=True,
    )

    # ── Anthropic ─────────────────────────────────────────────────────────
    anthropic_api_key: str

    # ── Voyage AI ─────────────────────────────────────────────────────────
    voyage_api_key: str

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str
    database_sync_url: str

    # ── Neo4j ─────────────────────────────────────────────────────────────
    neo4j_uri: str
    neo4j_username: str = "neo4j"
    neo4j_password: str

    # ── Google Cloud / BigQuery ───────────────────────────────────────────
    google_application_credentials: str = "apps/api/secrets/gcp.json"
    gcp_project_id: str = "cis-gdelt"
    bigquery_max_bytes_billed: int = 5_368_709_120  # 5 GB

    # ── LangSmith ─────────────────────────────────────────────────────────
    langsmith_api_key: str = ""
    langsmith_project: str = "cis"
    langchain_tracing_v2: bool = True

    # ── Inngest ───────────────────────────────────────────────────────────
    inngest_signing_key: str = ""
    inngest_event_key: str = ""

    # ── Budget caps (USD/day) ─────────────────────────────────────────────
    budget_cap_haiku_usd: float = Field(default=5.0)
    budget_cap_opus_usd: float = Field(default=10.0)
    budget_cap_prices_agent_usd: float = Field(default=0.50)
    budget_cap_gdelt_agent_usd: float = Field(default=1.00)
    budget_cap_sec_agent_usd: float = Field(default=1.00)
    budget_cap_press_agent_usd: float = Field(default=1.00)
    budget_cap_demand_agent_usd: float = Field(default=1.00)
    budget_cap_logistics_agent_usd: float = Field(default=1.00)

    # ── App ───────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"

    # ── SEC EDGAR ─────────────────────────────────────────────────────────
    sec_user_agent: str = "cis-research/0.1 a.shablovskiy@gmail.com"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Module-level singleton — import this everywhere.
settings = Settings()
