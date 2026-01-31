from __future__ import annotations
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGW_", env_file=".env", extra="ignore")

    # Core
    instance_id: str = Field(default="agw-1", description="Unique instance id for lock ownership/tracing.")
    data_dir: str = Field(default="./data")
    sqlite_path: str = Field(default="./data/agent_gateway.sqlite")
    plugin_dir: str = Field(default="./plugins")

    # Network
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8787)
    ws_path: str = Field(default="/ws")
    metrics_path: str = Field(default="/metrics")
    health_path: str = Field(default="/healthz")

    # Security defaults
    # Deny-by-default: if allowlist empty, nothing is allowed.
    require_client_auth: bool = Field(default=True)
    client_api_keys: list[str] = Field(default_factory=list, description="Static API keys for WS control-plane clients.")
    # approvals
    require_approvals_for_write_tools: bool = Field(default=True)
    rate_limit_rps: float = Field(default=2.0, description="Requests per second per principal.")
    rate_limit_burst: int = Field(default=6)

    # Agent
    max_context_messages: int = Field(default=20)
    run_max_steps: int = Field(default=6)
    run_timeout_s: int = Field(default=45)
    run_retry: int = Field(default=1)
    agent_engine: str = Field(default="simple", description="Agent engine: simple|langgraph")

    # Logging
    log_level: str = Field(default="INFO")
    json_logs: bool = Field(default=True)

    # LLM
    llm_adapter: str = Field(default="mock", description="mock|openai|anthropic|local_http (only mock included).")

def load_settings() -> Settings:
    return Settings()
