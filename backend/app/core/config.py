import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment configuration, read here and nowhere else.

    pydantic-settings binds each field to the upper-cased env var of the same
    name (e.g. ``serving_endpoint_name`` <- ``SERVING_ENDPOINT_NAME``) and
    handles bool/int coercion; ``AliasChoices`` covers the exceptions.
    """

    serving_endpoint_name: str | None = None
    job_id: str | None = None
    databricks_host: str | None = None
    databricks_client_id: str | None = None
    databricks_client_secret: str | None = None
    pg_host: str | None = Field(
        default=None, validation_alias=AliasChoices("PGHOST", "PG_HOST")
    )
    pg_port: int | None = Field(
        default=None, validation_alias=AliasChoices("PGPORT", "PG_PORT")
    )
    pg_database: str | None = Field(
        default=None, validation_alias=AliasChoices("PGDATABASE", "PG_DATABASE")
    )
    pg_user: str | None = Field(
        default=None, validation_alias=AliasChoices("PGUSER", "PG_USER")
    )
    # Schema the app owns and creates its tables in. Lakebase (Postgres 15+)
    # denies CREATE in `public` to non-owners, so the app uses its own schema.
    pg_app_schema: str = "starter"
    pg_password: str | None = Field(
        default=None, validation_alias=AliasChoices("PGPASSWORD", "PG_PASSWORD")
    )
    environment: str = "development"
    vector_search_endpoint_name: str | None = None
    vector_search_index_name: str | None = None
    databricks_warehouse_id: str | None = None
    databricks_token: str | None = None
    log_level: str = "INFO"
    volume_root: str = "/Volumes/main/default"
    enable_obo: bool = False
    enable_databricks_integrations: bool = False
    enable_local_dev_auth_fallback: bool | None = None
    local_dev_user_id: str = "local-dev-user"

    # Frontend serving
    enable_docs: bool = True
    serve_static: bool = False
    frontend_dist_dir: str = "public"

    # Request size limits
    max_request_body_bytes: int = 1_048_576  # 1 MiB
    max_upload_bytes: int = 52_428_800  # 50 MiB

    # Knowledge Assistant (Agent Bricks)
    knowledge_assistant_endpoint: str | None = None
    knowledge_assistant_timeout_seconds: int = 60

    # Chat orchestrator
    langgraph_memory_backend: str = "inmemory"  # "inmemory" | "lakebase"
    supervisor_model: str | None = None

    # Specialists
    app_agent_name: str | None = None
    serving_agent_endpoint: str | None = None
    mas_endpoint: str | None = None
    genie_space_id: str | None = None
    knowledge_volume_root: str | None = None
    ai_gateway_embedding_model: str | None = None

    # Title generation
    enable_chat_title_generation: bool = True
    title_model: str | None = None

    # MLflow
    mlflow_experiment_id: str | None = None

    # Timeouts (seconds)
    genie_timeout_seconds: int = 30
    serving_timeout_seconds: int = 30
    job_timeout_seconds: int = 120
    vector_timeout_seconds: int = 30
    openai_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def has_database_config(self) -> bool:
        return bool(os.getenv("DATABASE_URL") or self.has_pg_database_config())

    def has_ai_config(self) -> bool:
        return bool(self.serving_endpoint_name)

    def has_vector_search_config(self) -> bool:
        return bool(self.vector_search_endpoint_name and self.vector_search_index_name)

    def has_pg_database_config(self) -> bool:
        return all([self.pg_host, self.pg_database, self.pg_user])

    def databricks_integrations_enabled(self) -> bool:
        return self.enable_databricks_integrations

    def local_dev_auth_fallback_enabled(self) -> bool:
        if self.enable_local_dev_auth_fallback is not None:
            return self.enable_local_dev_auth_fallback
        return self.environment == "development"

    def has_explicit_databricks_auth(self) -> bool:
        return bool(
            self.databricks_host
            and (
                self.databricks_token
                or (self.databricks_client_id and self.databricks_client_secret)
            )
        )


settings = Settings()
