from logging import Logger
from typing import Any

from databricks import sql

from app.core.config import Settings
from app.core.errors import SqlDeltaError
from app.core.observability import get_tracer, tag_exception

try:
    import pyarrow as pa  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pa = None  # noqa: N816


_tracer = get_tracer()


class SqlDeltaAdapter:
    """Adapter for Databricks SQL connector operations against Delta tables.

    Methods are synchronous. Controller endpoints using this adapter should
    be defined with ``def`` (not ``async def``) so FastAPI runs them in a
    threadpool automatically.
    """

    def __init__(self, settings: Settings, logger: Logger):
        self._settings = settings
        self._logger = logger

    def _connect(self):
        host = self._settings.lakebase_host
        if host and not host.startswith("https://"):
            hostname = f"https://{host}"
        else:
            hostname = host
        return sql.connect(
            server_hostname=hostname,
            http_path=self._settings.databricks_http_path,
            access_token=self._settings.databricks_token,
        )

    def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict]:
        """Execute a SELECT and return rows as list of dicts."""
        if pa is None:
            raise SqlDeltaError(
                "pyarrow is required for Delta table operations but is not installed"
            )
        with _tracer.start_as_current_span(
            "dependency.sql.query",
            attributes={"dependency": "sql", "operation": "query"},
        ) as span:
            try:
                self._logger.debug("Executing query: %s", query[:80])
                with self._connect() as conn, conn.cursor() as cur:
                    cur.execute(query, params or {})
                    tbl = cur.fetchall_arrow()
                span.set_attribute("result", "ok")
                return tbl.to_pandas().to_dict(orient="records")
            except SqlDeltaError:
                span.set_attribute("result", "error")
                raise
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise SqlDeltaError(str(exc), cause=exc) from exc

    def execute_statement(
        self, statement: str, params: dict[str, Any] | None = None
    ) -> None:
        """Execute an INSERT/UPDATE/DELETE statement."""
        with _tracer.start_as_current_span(
            "dependency.sql.execute",
            attributes={"dependency": "sql", "operation": "execute"},
        ) as span:
            try:
                self._logger.debug("Executing statement: %s", statement[:80])
                with self._connect() as conn, conn.cursor() as cur:
                    cur.execute(statement, params or {})
                span.set_attribute("result", "ok")
            except SqlDeltaError:
                span.set_attribute("result", "error")
                raise
            except Exception as exc:
                span.set_attribute("result", "error")
                tag_exception(span, exc)
                raise SqlDeltaError(str(exc), cause=exc) from exc
