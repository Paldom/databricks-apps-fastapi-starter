"""Export the API sub-app OpenAPI spec to openapi.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.main import build_api_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI spec")
    parser.add_argument(
        "--output", "-o", default="openapi.json", help="Output file path"
    )
    args = parser.parse_args()

    api_app = build_api_app(settings)
    spec = api_app.openapi()

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Exported OpenAPI spec to {target}")


if __name__ == "__main__":
    main()
