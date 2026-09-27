"""
Database configuration module with SQLite optimizations.
Provides a shared engine with WAL mode for better concurrency.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from core.config import settings
from core.logging import logger


def create_optimized_engine():
    """
    Create SQLite engine with WAL mode and optimized settings.
    
    Optimizations:
    - WAL mode: allows concurrent readers with one writer
    - busy_timeout: waits 30s if database is locked
    - synchronous=NORMAL: faster writes (safe with WAL)
    - cache_size: 64MB cache for faster reads
    - temp_store=MEMORY: keep temp tables in RAM
    - check_same_thread=False: allow multi-threaded access
    """
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={
            "timeout": 30,
            "check_same_thread": False
        },
        pool_pre_ping=True,
        echo=False
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Apply SQLite optimizations on each connection."""
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA wal_autocheckpoint=1000")
        except Exception as e:
            logger.error(f"Error setting SQLite pragmas: {str(e)}")
        finally:
            cursor.close()

    return engine


# Shared global engine
engine = create_optimized_engine()

# Shared session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)

logger.info("✅ Database engine initialized with WAL mode")
