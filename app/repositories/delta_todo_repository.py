from app.core.databricks.sql_delta import SqlDeltaAdapter

TABLE = "main.default.todo_demo"


class DeltaTodoRepository:
    def __init__(self, adapter: SqlDeltaAdapter):
        self._adapter = adapter

    def list_todos(self, limit: int = 100) -> list[dict]:
        """List todos from the demo Delta table."""
        query = f"SELECT id, title, completed FROM {TABLE} LIMIT %(lim)s"
        return self._adapter.execute_query(query, {"lim": limit})

    def insert_todo(self, title: str) -> dict:
        """Insert a todo into the demo Delta table."""
        stmt = (
            f"INSERT INTO {TABLE} (id, title, completed) "
            "VALUES (gen_random_uuid(), %(title)s, false)"
        )
        self._adapter.execute_statement(stmt, {"title": title})
        return {"title": title}
