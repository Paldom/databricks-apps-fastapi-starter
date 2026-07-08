# Backend

FastAPI backend for the Databricks Apps starter. See the [repository README](../README.md)
for the full project documentation, local development setup, and deployment guide.

```bash
uv sync            # install runtime + dev dependencies
uv run uvicorn app.main:app --reload
```

## Quality gates

```bash
uv run ruff check . && uv run ruff format --check .   # lint + format
uv run mypy .                                          # type check
uv run pytest --cov                                    # tests + coverage gate
```

Type checking runs mypy in strict mode with a ratchet: legacy modules listed
under the `ignore_errors` override in `pyproject.toml` are exempt, tracked as
debt. When you touch one, fix its errors and delete it from the list — the
exemption list only ever shrinks. Suppressions must be error-code-scoped
(`# type: ignore[code]`); unused ignores fail the build.
