import base64
import os
from typing import Dict, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _db_secret(scope: str, key: str) -> Optional[Dict[str, str]]:
    """Retrieve and decode a Databricks secret.

    Databricks stores secret values base64 encoded.  This helper reads the
    secret, decodes it and returns the plain text value.
    """
    try:
        from app.core.databricks.workspace import get_workspace_client_singleton

        encoded = (
            get_workspace_client_singleton()
            .secrets.get_secret(scope=scope, key=key)
            .value
        )
    except Exception:
        return None
    if encoded is None:
        return None
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return None
    return {"key": key, "value": decoded}


def get_secret(
    key: str, *, scope: Optional[str] = None, allow_env: bool = True
) -> Optional[str]:
    if allow_env and (val := os.getenv(key)) is not None:
        return val
    if scope:
        result = _db_secret(scope, key)
        if result is not None:
            return result["value"]
        return None
    return None


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
    environment: str = "development"
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
    frontend_dist_dir: str = "frontend/dist"

    # Request size limits
    max_request_body_bytes: int = 1_048_576  # 1 MiB
    max_upload_bytes: int = 10_485_760  # 10 MiB

    # Knowledge Assistant (Agent Bricks)
    knowledge_assistant_endpoint: Optional[str] = None
    knowledge_assistant_timeout_seconds: int = 60

    # Chat orchestrator
    langgraph_memory_backend: str = "inmemory"  # "inmemory" | "lakebase"
    supervisor_model: Optional[str] = None

    # Specialists
    app_agent_name: Optional[str] = None
    serving_specialist_endpoint: Optional[str] = None
    serving_specialist_api_mode: str = "chat_completions"  # "responses" | "chat_completions"
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
        return bool(
            os.getenv("DATABASE_URL")
            or self.has_pg_database_config()
        )

    def has_ai_config(self) -> bool:
        return bool(self.serving_endpoint_name)

    def has_knowledge_assistant_config(self) -> bool:
        return bool(self.knowledge_assistant_endpoint)

    def has_vector_search_config(self) -> bool:
        return bool(
            self.vector_search_endpoint_name and self.vector_search_index_name
        )

    def has_genie_config(self) -> bool:
        return bool(self.genie_space_id)

    def has_serving_specialist_config(self) -> bool:
        return bool(self.serving_specialist_endpoint)

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
                or (
                    self.databricks_client_id
                    and self.databricks_client_secret
                )
            )
        )

    def model_post_init(self, __context) -> None:
        mapping = {
            "serving_endpoint_name": "SERVING_ENDPOINT_NAME",
            "job_id": "JOB_ID",
            "databricks_host": "DATABRICKS_HOST",
            "databricks_client_id": "DATABRICKS_CLIENT_ID",
            "databricks_client_secret": "DATABRICKS_CLIENT_SECRET",
            "pg_host": "PGHOST",
            "pg_port": "PGPORT",
            "pg_database": "PGDATABASE",
            "pg_user": "PGUSER",
            "pg_password": "PGPASSWORD",
            "vector_search_endpoint_name": "VECTOR_SEARCH_ENDPOINT_NAME",
            "vector_search_index_name": "VECTOR_SEARCH_INDEX_NAME",
            "databricks_http_path": "DATABRICKS_HTTP_PATH",
            "databricks_token": "DATABRICKS_TOKEN",
            "environment": "ENVIRONMENT",
            "log_level": "LOG_LEVEL",
            "volume_root": "VOLUME_ROOT",
            "enable_obo": "ENABLE_OBO",
            "enable_databricks_integrations": "ENABLE_DATABRICKS_INTEGRATIONS",
            "enable_local_dev_auth_fallback": "ENABLE_LOCAL_DEV_AUTH_FALLBACK",
            "local_dev_user_id": "LOCAL_DEV_USER_ID",
            "enable_docs": "ENABLE_DOCS",
            "serve_static": "SERVE_STATIC",
            "frontend_dist_dir": "FRONTEND_DIST_DIR",
            "max_request_body_bytes": "MAX_REQUEST_BODY_BYTES",
            "max_upload_bytes": "MAX_UPLOAD_BYTES",
            "genie_timeout_seconds": "GENIE_TIMEOUT_SECONDS",
            "serving_timeout_seconds": "SERVING_TIMEOUT_SECONDS",
            "job_timeout_seconds": "JOB_TIMEOUT_SECONDS",
            "vector_timeout_seconds": "VECTOR_TIMEOUT_SECONDS",
            "openai_timeout_seconds": "OPENAI_TIMEOUT_SECONDS",
            "knowledge_assistant_endpoint": "KNOWLEDGE_ASSISTANT_ENDPOINT",
            "knowledge_assistant_timeout_seconds": "KNOWLEDGE_ASSISTANT_TIMEOUT_SECONDS",
            "langgraph_memory_backend": "LANGGRAPH_MEMORY_BACKEND",
            "supervisor_model": "SUPERVISOR_MODEL",
            "app_agent_name": "APP_AGENT_NAME",
            "serving_specialist_endpoint": "SERVING_SPECIALIST_ENDPOINT",
            "serving_specialist_api_mode": "SERVING_SPECIALIST_API_MODE",
            "genie_space_id": "GENIE_SPACE_ID",
            "knowledge_volume_root": "KNOWLEDGE_VOLUME_ROOT",
            "ai_gateway_embedding_model": "AI_GATEWAY_EMBEDDING_MODEL",
            "enable_chat_title_generation": "ENABLE_CHAT_TITLE_GENERATION",
            "title_model": "TITLE_MODEL",
            "mlflow_experiment_id": "MLFLOW_EXPERIMENT_ID",
        }
        _bool_fields = {
            "enable_obo",
            "enable_databricks_integrations",
            "enable_local_dev_auth_fallback",
            "enable_docs",
            "serve_static",
            "enable_chat_title_generation",
        }
        _int_fields = {
            "pg_port",
            "max_request_body_bytes",
            "max_upload_bytes",
            "genie_timeout_seconds",
            "serving_timeout_seconds",
            "job_timeout_seconds",
            "vector_timeout_seconds",
            "openai_timeout_seconds",
            "knowledge_assistant_timeout_seconds",
        }
        for attr, env_key in mapping.items():
            if getattr(self, attr) is not None:
                continue
            val = get_secret(env_key)
            if attr in _int_fields:
                if val is None:
                    continue
                try:
                    setattr(self, attr, int(val))
                except ValueError:
                    continue
            elif attr in _bool_fields:
                if val is None:
                    continue
                setattr(self, attr, str(val).lower() in {"1", "true", "yes", "y"})
            else:
                setattr(self, attr, val)


settings = Settings()
