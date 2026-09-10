"""Write backend/env.example from Settings so the documented variables cannot drift.

Run through `make generate`. Values are the defaults; secrets are never included.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

from app.core.config import Settings

HEADER = """# Generated from backend/app/core/config.py (make generate); edit the Settings class, not this file.
# Local development: copy to backend/.env. On Databricks Apps the bundle sets these (resources/app.yml)
# and the platform injects PGHOST/PGPORT/PGDATABASE/PGUSER/PGSSLMODE, DATABRICKS_HOST and the
# app credentials; leave DATABASE_URL and the DATABRICKS_* auth variables unset there.
"""


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
        value = (
            ""
            if default is None or default == []
            else str(default).lower()
            if isinstance(default, bool)
            else str(default)
        )
        lines.append(f"{_env_name(name, field)}={value}{comment}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "env.example"
    target.write_text(render(Settings))
    print(f"wrote {target}")
