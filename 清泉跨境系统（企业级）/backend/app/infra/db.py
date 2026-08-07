from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=settings.app_env == "dev", pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# public = 中心共用（shop / ingest_raw / task…）
# tk     = TikTok 事实表（与 temu schema 对称）
# temu   = Temu 监测（同事 schema，可同库共存）
@event.listens_for(engine.sync_engine, "connect")
def _set_search_path(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("SET search_path TO public, tk, temu")
    cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        # 保险：每个会话再设一次（连接池复用时 connect 钩子已够，双保险）
        await session.execute(text("SET search_path TO public, tk, temu"))
        yield session
