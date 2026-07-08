"""Export the API sub-app OpenAPI spec to openapi.yaml."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The exported contract must include every optional module's endpoints, so
# the spec is built from a Settings instance with all modules activated —
# the values are placeholders, never used to make calls.
_ALL_MODULES_ENV = {
    "ENABLE_DATABRICKS_INTEGRATIONS": "true",
    "AI_GATEWAY_EMBEDDING_MODEL": "spec-export",
    "VECTOR_SEARCH_ENDPOINT_NAME": "spec-export",
    "VECTOR_SEARCH_INDEX_NAME": "spec-export",
}
for _key, _value in _ALL_MODULES_ENV.items():
    os.environ.setdefault(_key, _value)

from app.core.config import Settings  # noqa: E402  (env must be set first)
from app.main import build_api_app  # noqa: E402

settings = Settings()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec")
    parser.add_argument(
        "--output", "-o", default="openapi.yaml", help="Output file path"
    )
    args = parser.parse_args()

    api_app = build_api_app(settings)
    spec = api_app.openapi()

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.dump(spec, default_flow_style=False, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Exported OpenAPI spec to {target}")


if __name__ == "__main__":
    main()
