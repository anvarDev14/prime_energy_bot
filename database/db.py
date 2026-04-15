from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from contextlib import asynccontextmanager
from database.models import Base, User
import logging

logger = logging.getLogger(__name__)

engine = None
async_session_factory = None


async def init_db(database_url: str):
    global engine, async_session_factory

    engine = create_async_engine(
        database_url,
        echo=False,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    logger.info("✅ Database initialized")


@asynccontextmanager
async def get_session():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_or_create_user(telegram_id: int, username: str = None, full_name: str = None) -> User:
    async with get_session() as session:
        stmt = sqlite_insert(User).values(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        ).on_conflict_do_nothing(index_elements=["telegram_id"])
        await session.execute(stmt)

        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one()


async def get_user_by_phone(phone: str) -> User:
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.phone.contains(clean_phone[-9:]))
        )
        return result.scalar_one_or_none()
