# Async SQLAlchemy engine, session factory, and base model for all ORM classes
import ssl as _ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# asyncpg doesn't understand ?sslmode=require — strip it and pass ssl=True via connect_args instead
database_url = settings.database_url
connect_args: dict = {}

if "sslmode=" in database_url:
    database_url = database_url.split("?")[0]
    connect_args["ssl"] = _ssl.create_default_context()

async_engine = create_async_engine(
    database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle_seconds,
    connect_args=connect_args,
)

AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_database_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
