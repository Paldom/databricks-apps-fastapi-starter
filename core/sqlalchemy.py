from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from config import settings

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.lakebase_user}:{settings.lakebase_password}"
    f"@{settings.lakebase_host}:{settings.lakebase_port}/{settings.lakebase_db}"
)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
