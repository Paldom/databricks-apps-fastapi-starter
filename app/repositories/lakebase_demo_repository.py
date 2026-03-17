import asyncpg


class LakebaseDemoRepository:
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def insert_demo(self, text: str) -> dict:
        """Insert a demo row and return it as a dict."""
        row = await self._pool.fetchrow(
            "INSERT INTO demo(text) VALUES ($1) RETURNING id, text",
            text,
        )
        return dict(row)
