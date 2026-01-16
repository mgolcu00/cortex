# app/ingest/__init__.py
"""
Veri alma ve işleme modülü.
Confluence verilerini çekme, chunking, embedding.
"""

from app.ingest.chunker import TextChunker, TextChunk
from app.ingest.embedder import Embedder
from app.ingest.sync import SyncManager

__all__ = [
    "TextChunker",
    "TextChunk",
    "Embedder",
    "SyncManager",
]
