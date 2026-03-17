from logging import Logger

from app.repositories.delta_todo_repository import DeltaTodoRepository


class SqlDeltaService:
    def __init__(self, repo: DeltaTodoRepository, logger: Logger):
        self._repo = repo
        self._logger = logger

    def list_todos(self, limit: int = 100) -> list[dict]:
        self._logger.debug("Listing delta todos with limit %d", limit)
        return self._repo.list_todos(limit)

    def insert_todo(self, title: str) -> dict:
        self._logger.info("Inserting delta todo: %s", title)
        return self._repo.insert_todo(title)
