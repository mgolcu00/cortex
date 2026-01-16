# app/db/__init__.py
"""
Veritabanı modülü.
SQLAlchemy + pgvector ile PostgreSQL işlemleri.
"""

from app.db.database import get_db, init_db, engine
from app.db.models import Page, Chunk, PageLink, SyncState

__all__ = [
    "get_db",
    "init_db",
    "engine",
    "Page",
    "Chunk",
    "PageLink",
    "SyncState",
]
