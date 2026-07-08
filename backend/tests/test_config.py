"""Settings behavior: env binding, aliases, and coercion via pydantic-settings."""

from app.core.config import Settings


def test_env_binding_by_field_name(monkeypatch):
    monkeypatch.setenv("SERVING_ENDPOINT_NAME", "my-endpoint")
    assert Settings().serving_endpoint_name == "my-endpoint"


def test_bool_and_int_coercion(monkeypatch):
    monkeypatch.setenv("ENABLE_OBO", "true")
    monkeypatch.setenv("PGPORT", "5433")
    s = Settings()
    assert s.enable_obo is True
    assert s.pg_port == 5433


def test_pg_alias_choices(monkeypatch):
    monkeypatch.setenv("PG_HOST", "alias-host")
    monkeypatch.setenv("PGDATABASE", "canonical-db")
    s = Settings()
    assert s.pg_host == "alias-host"
    assert s.pg_database == "canonical-db"


def test_local_dev_auth_fallback_defaults_by_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert Settings().local_dev_auth_fallback_enabled() is True
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings().local_dev_auth_fallback_enabled() is False
