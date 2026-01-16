# app/db/database.py
"""
Veritabanı bağlantı yönetimi.
SQLAlchemy engine ve session factory.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# SQLAlchemy Engine
# ============================================================
# PostgreSQL bağlantısı için engine oluştur
# pool_pre_ping: bağlantı koptuğunda otomatik yeniden bağlan
engine = create_engine(
    settings.database_url_fixed,  # Otomatik olarak psycopg3 driver'ına dönüştürülür
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,  # SQL loglaması (DEBUG için True yapılabilir)
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================================
# Session Yönetimi
# ============================================================
@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Veritabanı session context manager.

    Kullanım:
        with get_db() as db:
            db.query(Page).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """
    FastAPI dependency injection için session döndür.

    Kullanım:
        @app.get("/")
        def endpoint(db: Session = Depends(get_db_session)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Veritabanı Başlatma
# ============================================================
def init_db() -> None:
    """
    Veritabanı tablolarını oluştur.
    pgvector extension'ı yükle ve tabloları create et.
    """
    from app.db.models import Base  # Circular import önlemek için

    logger.info("Veritabanı başlatılıyor...")

    # pgvector extension'ını yükle
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("pgvector extension yüklendi")
        except Exception as e:
            logger.warning(f"pgvector extension yüklenemedi: {e}")
            logger.warning("Manuel olarak 'CREATE EXTENSION vector;' çalıştırın")

    # Tabloları oluştur
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları oluşturuldu")


def check_db_connection() -> bool:
    """
    Veritabanı bağlantısını kontrol et.
    Health check için kullanılır.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Veritabanı bağlantı hatası: {e}")
        return False
