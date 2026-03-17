from logging import Logger

from app.repositories.lakebase_demo_repository import LakebaseDemoRepository


class LakebaseDemoService:
    def __init__(self, repo: LakebaseDemoRepository, logger: Logger):
        self._repo = repo
        self._logger = logger

    async def insert(self, text: str) -> dict:
        self._logger.debug("Inserting demo row")
        return await self._repo.insert_demo(text)
