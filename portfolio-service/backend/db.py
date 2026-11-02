from collections.abc import AsyncGenerator
import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

LOCAL_DATABASE_URL = os.getenv("PORTFOLIO_SQLITE_URL", "sqlite+aiosqlite:///./portfolio-service/portfolio.db")
REFERENCE_DATABASE_URL = os.getenv("REFERENCE_DB_CONN_STRING", os.getenv("PORTFOLIO_DB_CONN_STRING", "postgresql+asyncpg://localhost/reference"))
if REFERENCE_DATABASE_URL.startswith("postgresql://"):
    REFERENCE_DATABASE_URL = REFERENCE_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

portfolio_engine = create_async_engine(LOCAL_DATABASE_URL, pool_pre_ping=True)
reference_engine = create_async_engine(REFERENCE_DATABASE_URL, pool_pre_ping=True)
SessionFactory = async_sessionmaker(portfolio_engine, expire_on_commit=False)
ReferenceSessionFactory = async_sessionmaker(reference_engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        yield session


async def get_reference_session() -> AsyncGenerator[AsyncSession, None]:
    async with ReferenceSessionFactory() as session:
        yield session
