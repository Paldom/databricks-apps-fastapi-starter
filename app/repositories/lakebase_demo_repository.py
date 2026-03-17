from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LakebaseDemoRepository:
    """Data-access layer for the Lakebase demo table.

    Uses raw SQL via SQLAlchemy :func:`text` execution — no ORM model
    required for the ``demo`` table.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_demo(self, text_val: str) -> dict:
        """Insert a demo row and return it as a dict."""
        result = await self.session.execute(
            text("INSERT INTO demo(text) VALUES (:text) RETURNING id, text"),
            {"text": text_val},
        )
        return dict(result.mappings().one())
