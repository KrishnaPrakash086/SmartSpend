# Async SQLAlchemy engine, session factory, and base model for all ORM classes
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Pool tuned for moderate concurrency; pool_pre_ping guards against stale connections after idle
async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle_seconds,
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
            # Auto-commit on successful request; rollback on any unhandled exception
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
