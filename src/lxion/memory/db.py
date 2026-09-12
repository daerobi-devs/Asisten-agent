from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from lxion.core.config import settings
from lxion.core.logger import logger
from lxion.memory.models import Base

# Setup Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    """Initialize database tables and extensions."""
    try:
        async with engine.begin() as conn:
            # Check if pgvector is available (PostgreSQL only)
            if "postgresql" in settings.DATABASE_URL:
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    logger.info("[green]✓ pgvector extension initialized[/green]")
                except Exception as e:
                    logger.warning(f"Could not enable pgvector extension: {e}")
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("[green]✓ Database schema initialized successfully[/green]")
    except Exception as e:
        logger.error(f"[red]Database connection failed on {settings.DATABASE_URL}: {e}[/red]")
        logger.info("[yellow]⚠️ Hint: Run 'docker compose up -d postgres' to start PostgreSQL container.[/yellow]")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining async db session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()