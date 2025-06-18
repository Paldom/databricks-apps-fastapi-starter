import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from workspace import w


def get_secret(key: str, *, scope: Optional[str] = None, allow_env: bool = True) -> Optional[str]:
    if allow_env and (val := os.getenv(key)) is not None:
        return val
    if scope:
        try:
            return w().secrets.get_secret(scope=scope, key=key).value
        except Exception:
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
    log_level: str = "INFO"


    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
            "environment": "ENVIRONMENT",
            "log_level": "LOG_LEVEL",
        }
        for attr, env_key in mapping.items():
            if getattr(self, attr) is not None:
                continue
            val = get_secret(env_key)
            if attr == "lakebase_port":
                if val is None:
                    continue
                try:
                    setattr(self, attr, int(val))
                except ValueError:
                    continue
            else:
                setattr(self, attr, val)


settings = Settings()
