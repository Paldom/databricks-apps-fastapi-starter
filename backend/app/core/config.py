from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    serving_endpoint_name: Optional[str] = None
    job_id: Optional[str] = None
    databricks_host: Optional[str] = None
    databricks_client_id: Optional[str] = None
    databricks_client_secret: Optional[str] = None
    pg_host: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("PGHOST", "PG_HOST")
    )
    pg_port: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("PGPORT", "PG_PORT")
    )
    pg_database: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("PGDATABASE", "PG_DATABASE")
    )
    pg_user: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("PGUSER", "PG_USER")
    )
    pg_password: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("PGPASSWORD", "PG_PASSWORD")
    )
    database_url: Optional[str] = (
        None  # local Docker Postgres; Lakebase uses PG* + OAuth
    )
    environment: str = "development"
    app_version: Optional[str] = None  # set by the bundle from the git commit
    vector_search_endpoint_name: Optional[str] = None
    vector_search_index_name: Optional[str] = None
    databricks_http_path: Optional[str] = None
    databricks_token: Optional[str] = None
    log_level: str = "INFO"
    volume_root: str = "/Volumes/main/default"
    enable_obo: bool = False
    enable_databricks_integrations: bool = False
    enable_local_dev_auth_fallback: Optional[bool] = None
    local_dev_user_id: str = "local-dev-user"

    # Frontend serving
    enable_docs: bool = True
    serve_static: bool = False
    frontend_dist_dir: str = "public"

    # Request size limits
    max_request_body_bytes: int = 1_048_576  # 1 MiB
    max_upload_bytes: int = 52_428_800  # 50 MiB

    # Knowledge Assistant (Agent Bricks)
    knowledge_assistant_endpoint: Optional[str] = None
    knowledge_assistant_timeout_seconds: int = 60

    # Chat orchestrator
    langgraph_memory_backend: str = "inmemory"  # "inmemory" | "lakebase"
    supervisor_model: Optional[str] = None

    # Specialists
    app_agent_name: Optional[str] = None
    serving_agent_endpoint: Optional[str] = None
    genie_space_id: Optional[str] = None
    knowledge_volume_root: Optional[str] = None
    ai_gateway_embedding_model: Optional[str] = None

    # Title generation
    enable_chat_title_generation: bool = True
    title_model: Optional[str] = None

    # MLflow
    mlflow_experiment_id: Optional[str] = None

    # Timeouts (seconds)
    genie_timeout_seconds: int = 30
    serving_timeout_seconds: int = 30
    job_timeout_seconds: int = 120
    vector_timeout_seconds: int = 30
    openai_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def has_database_config(self) -> bool:
        return bool(self.database_url or self.has_pg_database_config())

    def has_ai_config(self) -> bool:
        return bool(self.serving_endpoint_name)

    def has_knowledge_assistant_config(self) -> bool:
        return bool(self.knowledge_assistant_endpoint)

    def has_vector_search_config(self) -> bool:
        return bool(self.vector_search_endpoint_name and self.vector_search_index_name)

    def has_genie_config(self) -> bool:
        return bool(self.genie_space_id)

    def has_serving_agent_config(self) -> bool:
        return bool(self.serving_agent_endpoint)

    def has_knowledge_specialist_config(self) -> bool:
        return bool(self.ai_gateway_embedding_model and self.has_vector_search_config())

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
