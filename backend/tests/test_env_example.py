"""backend/env.example is generated from Settings and must load as a local .env file."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.core.config import Settings

BACKEND = Path(__file__).resolve().parents[1]


def _render() -> str:
    spec = importlib.util.spec_from_file_location(
        "export_env_example", BACKEND / "scripts" / "export_env_example.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render(Settings)


def test_env_example_matches_settings():
    assert (BACKEND / "env.example").read_text() == _render(), "run `make generate`"


def test_env_example_loads_as_a_local_env_file():
    loaded = Settings(_env_file=str(BACKEND / "env.example"))  # type: ignore[call-arg]
    assert loaded.has_database_config()
    assert loaded.pg_host == "localhost"
    assert loaded.environment == "development"
