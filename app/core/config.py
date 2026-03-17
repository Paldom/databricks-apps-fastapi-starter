import base64
import os
from typing import Dict, Optional

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
    lakebase_host: Optional[str] = None
    lakebase_port: int = 5432
    lakebase_db: Optional[str] = None
    lakebase_user: Optional[str] = None
    lakebase_password: Optional[str] = None
    environment: str = "development"
    vector_search_endpoint_name: Optional[str] = None
    vector_search_index_name: Optional[str] = None
    databricks_http_path: Optional[str] = None
    databricks_token: Optional[str] = None
    log_level: str = "INFO"
    volume_root: str = "/Volumes/main/default"
    enable_obo: bool = False

    # Frontend serving
    enable_docs: bool = True
    serve_static: bool = False
    frontend_dist_dir: str = "frontend/dist"
    enable_legacy_api: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True

    # Request size limits
    max_request_body_bytes: int = 1_048_576  # 1 MiB
    max_upload_bytes: int = 10_485_760  # 10 MiB

    # Timeouts (seconds)
    genie_timeout_seconds: int = 30
    serving_timeout_seconds: int = 30
    job_timeout_seconds: int = 120
    vector_timeout_seconds: int = 30
    openai_timeout_seconds: int = 30

    # Health
    health_ready_cache_ttl: int = 30

    # Cache
    cache_enabled: bool = True
    cache_backend: str = "memory"
    cache_namespace: str = "databricks-apps-fastapi-starter"
    cache_default_ttl: int = 60
    cache_timeout: int = 1
    cache_redis_endpoint: str = "localhost"
    cache_redis_port: int = 6379
    cache_redis_db: int = 0
    cache_redis_password: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def has_database_config(self) -> bool:
        return bool(
            os.getenv("DATABASE_URL")
            or all(
                [
                    self.lakebase_host,
                    self.lakebase_db,
                    self.lakebase_user,
                    self.lakebase_password,
                ]
            )
        )

    def has_ai_config(self) -> bool:
        return bool(self.serving_endpoint_name)

    def has_vector_search_config(self) -> bool:
        return bool(
            self.vector_search_endpoint_name and self.vector_search_index_name
        )

    def model_post_init(self, __context) -> None:
        mapping = {
            "serving_endpoint_name": "SERVING_ENDPOINT_NAME",
            "job_id": "JOB_ID",
            "lakebase_host": "LAKEBASE_HOST",
            "lakebase_port": "LAKEBASE_PORT",
            "lakebase_db": "LAKEBASE_DB",
            "lakebase_user": "LAKEBASE_USER",
            "lakebase_password": "LAKEBASE_PASSWORD",
            "vector_search_endpoint_name": "VECTOR_SEARCH_ENDPOINT_NAME",
            "vector_search_index_name": "VECTOR_SEARCH_INDEX_NAME",
            "databricks_http_path": "DATABRICKS_HTTP_PATH",
            "databricks_token": "DATABRICKS_TOKEN",
            "environment": "ENVIRONMENT",
            "log_level": "LOG_LEVEL",
            "volume_root": "VOLUME_ROOT",
            "enable_obo": "ENABLE_OBO",
            "cache_enabled": "CACHE_ENABLED",
            "cache_backend": "CACHE_BACKEND",
            "cache_namespace": "CACHE_NAMESPACE",
            "cache_default_ttl": "CACHE_DEFAULT_TTL",
            "cache_timeout": "CACHE_TIMEOUT",
            "cache_redis_endpoint": "CACHE_REDIS_ENDPOINT",
            "cache_redis_port": "CACHE_REDIS_PORT",
            "cache_redis_db": "CACHE_REDIS_DB",
            "cache_redis_password": "CACHE_REDIS_PASSWORD",
            "enable_docs": "ENABLE_DOCS",
            "serve_static": "SERVE_STATIC",
            "frontend_dist_dir": "FRONTEND_DIST_DIR",
            "enable_legacy_api": "ENABLE_LEGACY_API",
            "rate_limit_enabled": "RATE_LIMIT_ENABLED",
            "max_request_body_bytes": "MAX_REQUEST_BODY_BYTES",
            "max_upload_bytes": "MAX_UPLOAD_BYTES",
            "genie_timeout_seconds": "GENIE_TIMEOUT_SECONDS",
            "serving_timeout_seconds": "SERVING_TIMEOUT_SECONDS",
            "job_timeout_seconds": "JOB_TIMEOUT_SECONDS",
            "vector_timeout_seconds": "VECTOR_TIMEOUT_SECONDS",
            "openai_timeout_seconds": "OPENAI_TIMEOUT_SECONDS",
            "health_ready_cache_ttl": "HEALTH_READY_CACHE_TTL",
        }
        _bool_fields = {
            "enable_obo",
            "cache_enabled",
            "rate_limit_enabled",
            "enable_docs",
            "serve_static",
            "enable_legacy_api",
        }
        _int_fields = {
            "lakebase_port",
            "cache_default_ttl",
            "cache_timeout",
            "cache_redis_port",
            "cache_redis_db",
            "max_request_body_bytes",
            "max_upload_bytes",
            "genie_timeout_seconds",
            "serving_timeout_seconds",
            "job_timeout_seconds",
            "vector_timeout_seconds",
            "openai_timeout_seconds",
            "health_ready_cache_ttl",
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
                setattr(self, attr, str(val).lower() in {"1", "true", "yes", "y"})
            else:
                setattr(self, attr, val)


settings = Settings()
