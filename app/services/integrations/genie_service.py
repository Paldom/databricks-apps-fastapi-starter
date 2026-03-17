from logging import Logger

from app.core.databricks.genie import GenieAdapter


class GenieService:
    def __init__(self, adapter: GenieAdapter, logger: Logger):
        self._adapter = adapter
        self._logger = logger

    async def start_conversation(self, space_id: str, question: str) -> dict:
        return await self._adapter.start_conversation(space_id, question)

    async def follow_up(
        self, space_id: str, conversation_id: str, question: str
    ) -> dict:
        return await self._adapter.follow_up(space_id, conversation_id, question)
