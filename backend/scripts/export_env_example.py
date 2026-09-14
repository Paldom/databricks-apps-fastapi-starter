"""Write backend/env.example from Settings so the documented variables cannot drift.

Run through `make generate`. Values are the defaults; secrets are never included.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings

from app.core.config import Settings

HEADER = """# Generated from backend/app/core/config.py (make generate); edit the Settings class, not this file.
# Local development: copy to backend/.env. On Databricks Apps the bundle sets these (resources/fastapi_app.app.yml)
# and the platform injects PGHOST/PGPORT/PGDATABASE/PGUSER/PGSSLMODE, DATABRICKS_HOST and the
# app credentials; leave DATABASE_URL and the DATABRICKS_* auth variables unset there.
# The PG* values below match backend/docker-compose.yml (make dev-db); an empty value means unset.
"""

LOCAL_DEV = {  # ponytail: the compose defaults, so the quickstart works after `cp`
    "PGHOST": "localhost",
    "PGPORT": "5432",
    "PGDATABASE": "mydb",
    "PGUSER": "myuser",
    "PGPASSWORD": "mypassword  # pragma: allowlist secret",
    "PGSSLMODE": "disable",
}


def _env_name(field_name: str, field) -> str:  # type: ignore[no-untyped-def]
    alias = getattr(field, "validation_alias", None)
    choices = getattr(alias, "choices", None)
    if choices:
        return str(choices[0])
    return field_name.upper()


def render(settings_cls: type[BaseSettings]) -> str:
    lines = [HEADER]
    for name, field in settings_cls.model_fields.items():
        default = field.default
        comment = f"  # {field.description}" if field.description else ""
        env_name = _env_name(name, field)
        if env_name in LOCAL_DEV:
            value = LOCAL_DEV[env_name]
        elif default is None:
            value = ""
        elif isinstance(default, bool):
            value = str(default).lower()
        elif isinstance(default, (list, dict)):
            value = json.dumps(default)
        else:
            value = str(default)
        lines.append(f"{env_name}={value}{comment}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "env.example"
    target.write_text(render(Settings))
    print(f"wrote {target}")
