from logging import Logger

from httpx import AsyncClient, HTTPStatusError

from app.core.errors import GenieError


class GenieAdapter:
    """Adapter for the Databricks Genie conversational API."""

    def __init__(self, client: AsyncClient, logger: Logger):
        self._client = client
        self._logger = logger

    async def start_conversation(self, space_id: str, question: str) -> dict:
        """Start a new Genie conversation."""
        self._logger.info("Starting Genie conversation in space %s", space_id)
        try:
            resp = await self._client.post(
                f"/api/2.0/genie/spaces/{space_id}/start-conversation",
                json={"content": question},
            )
            resp.raise_for_status()
            return resp.json()
        except HTTPStatusError as exc:
            raise GenieError(
                f"Genie start-conversation failed: {exc.response.status_code}",
                cause=exc,
            ) from exc
        except Exception as exc:
            raise GenieError(str(exc), cause=exc) from exc

    async def follow_up(
        self, space_id: str, conversation_id: str, question: str
    ) -> dict:
        """Send a follow-up message in an existing conversation."""
        self._logger.info(
            "Following up in Genie conversation %s/%s", space_id, conversation_id
        )
        try:
            resp = await self._client.post(
                f"/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages",
                json={"content": question},
            )
            resp.raise_for_status()
            return resp.json()
        except HTTPStatusError as exc:
            raise GenieError(
                f"Genie follow-up failed: {exc.response.status_code}",
                cause=exc,
            ) from exc
        except Exception as exc:
            raise GenieError(str(exc), cause=exc) from exc
