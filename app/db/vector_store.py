# app/db/vector_store.py
"""
pgvector ile vektör arama işlemleri.
Similarity search fonksiyonları.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Chunk, Page
from app.ingest.embedder import get_embedder

logger = logging.getLogger(__name__)


# ============================================================
# Veri Yapıları
# ============================================================
@dataclass
class SearchResult:
    """
    Arama sonucu.

    Attributes:
        chunk_id: Chunk UUID
        page_id: Sayfa ID
        space_key: Space anahtarı
        title: Sayfa başlığı
        url: Sayfa URL'i
        heading_path: Chunk'ın heading path'i
        text: Chunk metni
        score: Similarity skoru (0-1)
    """
    chunk_id: str
    page_id: str
    space_key: str
    title: str
    url: str
    heading_path: Optional[str]
    text: str
    score: float


@dataclass
class PageSearchResult:
    """
    Sayfa bazlı arama sonucu (gruplandırılmış).

    Attributes:
        page_id: Sayfa ID
        space_key: Space anahtarı
        title: Sayfa başlığı
        url: Sayfa URL'i
        score: En yüksek chunk skoru
        snippets: İlgili chunk metinleri
        chunk_count: Bu sayfadan bulunan chunk sayısı
    """
    page_id: str
    space_key: str
    title: str
    url: str
    score: float
    snippets: list[str]
    chunk_count: int


# ============================================================
# Vector Search Fonksiyonları
# ============================================================
def vector_search(
    db: Session,
    query: str,
    top_k: int = 30,
    max_pages: int = 12,
    min_score: float = 0.3,
) -> list[PageSearchResult]:
    """
    Sorgu metnine en benzer chunk'ları bul ve sayfa bazında grupla.

    Args:
        db: SQLAlchemy session
        query: Arama sorgusu
        top_k: Döndürülecek maksimum chunk sayısı
        max_pages: Döndürülecek maksimum sayfa sayısı
        min_score: Minimum similarity skoru (0-1)

    Returns:
        PageSearchResult listesi (skor sırasına göre)
    """
    logger.info(f"Vector search: '{query[:50]}...' (top_k={top_k})")

    # Sorguyu embed et
    embedder = get_embedder()
    query_embedding = embedder.embed_text(query)

    # pgvector cosine similarity sorgusu
    # 1 - cosine_distance = cosine_similarity
    sql = text("""
        SELECT
            c.chunk_id::text,
            c.page_id,
            c.space_key,
            c.heading_path,
            c.text,
            p.title,
            p.url,
            1 - (c.embedding <=> :embedding) as score
        FROM chunks c
        JOIN pages p ON c.page_id = p.page_id
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :embedding
        LIMIT :limit
    """)

    # Sorguyu çalıştır
    result = db.execute(
        sql,
        {
            "embedding": str(query_embedding),
            "limit": top_k,
        }
    )

    # Sonuçları topla
    chunk_results = []
    for row in result:
        score = float(row.score)
        if score >= min_score:
            chunk_results.append(
                SearchResult(
                    chunk_id=row.chunk_id,
                    page_id=row.page_id,
                    space_key=row.space_key,
                    title=row.title,
                    url=row.url,
                    heading_path=row.heading_path,
                    text=row.text,
                    score=score,
                )
            )

    # Sayfa bazında grupla
    page_results = _group_by_page(chunk_results, max_pages)

    logger.info(f"Bulunan: {len(chunk_results)} chunk, {len(page_results)} sayfa")
    return page_results


def _group_by_page(
    chunks: list[SearchResult],
    max_pages: int,
) -> list[PageSearchResult]:
    """
    Chunk sonuçlarını sayfa bazında grupla.
    """
    # Page ID'ye göre grupla
    pages_dict: dict[str, PageSearchResult] = {}

    for chunk in chunks:
        if chunk.page_id in pages_dict:
            # Mevcut sayfaya ekle
            page = pages_dict[chunk.page_id]
            if len(page.snippets) < 3:  # Maksimum 3 snippet
                page.snippets.append(chunk.text[:300])
            page.chunk_count += 1
            # En yüksek skoru güncelle
            if chunk.score > page.score:
                page.score = chunk.score
        else:
            # Yeni sayfa ekle
            pages_dict[chunk.page_id] = PageSearchResult(
                page_id=chunk.page_id,
                space_key=chunk.space_key,
                title=chunk.title,
                url=chunk.url,
                score=chunk.score,
                snippets=[chunk.text[:300]],
                chunk_count=1,
            )

    # Skora göre sırala ve limitle
    sorted_pages = sorted(
        pages_dict.values(),
        key=lambda p: p.score,
        reverse=True,
    )

    return sorted_pages[:max_pages]


def search_chunks_raw(
    db: Session,
    query_embedding: list[float],
    top_k: int = 30,
) -> list[SearchResult]:
    """
    Ham chunk araması (embedding ile).
    Agent tool'ları için düşük seviye fonksiyon.
    """
    sql = text("""
        SELECT
            c.chunk_id::text,
            c.page_id,
            c.space_key,
            c.heading_path,
            c.text,
            p.title,
            p.url,
            1 - (c.embedding <=> :embedding) as score
        FROM chunks c
        JOIN pages p ON c.page_id = p.page_id
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :embedding
        LIMIT :limit
    """)

    result = db.execute(
        sql,
        {
            "embedding": str(query_embedding),
            "limit": top_k,
        }
    )

    return [
        SearchResult(
            chunk_id=row.chunk_id,
            page_id=row.page_id,
            space_key=row.space_key,
            title=row.title,
            url=row.url,
            heading_path=row.heading_path,
            text=row.text,
            score=float(row.score),
        )
        for row in result
    ]


# ============================================================
# Page Fetch Fonksiyonları
# ============================================================
def fetch_pages_by_ids(
    db: Session,
    page_ids: list[str],
) -> list[dict]:
    """
    Sayfa ID'lerine göre tam içerik getir.

    Args:
        db: SQLAlchemy session
        page_ids: Sayfa ID listesi

    Returns:
        Sayfa bilgileri listesi
    """
    if not page_ids:
        return []

    pages = db.query(Page).filter(Page.page_id.in_(page_ids)).all()

    return [
        {
            "page_id": page.page_id,
            "space_key": page.space_key,
            "title": page.title,
            "url": page.url,
            "body_text": page.body_text,
        }
        for page in pages
    ]


# ============================================================
# Link Graph Fonksiyonları
# ============================================================
def get_linked_pages(
    db: Session,
    page_ids: list[str],
    depth: int = 1,
    limit: int = 30,
) -> list[dict]:
    """
    Verilen sayfaların linklendiği sayfaları getir.

    Args:
        db: SQLAlchemy session
        page_ids: Kaynak sayfa ID listesi
        depth: Link derinliği (şimdilik 1)
        limit: Maksimum sonuç sayısı

    Returns:
        Link bilgileri listesi
    """
    if not page_ids:
        return []

    # page_links tablosundan linked sayfaları bul
    sql = text("""
        SELECT DISTINCT
            pl.to_page_id,
            p.title,
            p.url,
            p.space_key,
            pl.link_type
        FROM page_links pl
        JOIN pages p ON pl.to_page_id = p.page_id
        WHERE pl.from_page_id = ANY(:page_ids)
          AND pl.to_page_id IS NOT NULL
          AND pl.to_page_id NOT IN (SELECT unnest(:page_ids))
        LIMIT :limit
    """)

    result = db.execute(
        sql,
        {
            "page_ids": page_ids,
            "limit": limit,
        }
    )

    return [
        {
            "page_id": row.to_page_id,
            "title": row.title,
            "url": row.url,
            "space_key": row.space_key,
            "link_type": row.link_type,
        }
        for row in result
    ]


# ============================================================
# İstatistik Fonksiyonları
# ============================================================
def get_chunk_stats(db: Session) -> dict:
    """
    Chunk istatistiklerini getir.
    """
    total_chunks = db.query(Chunk).count()
    embedded_chunks = db.query(Chunk).filter(Chunk.embedding.isnot(None)).count()
    total_pages = db.query(Page).count()

    return {
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "total_pages": total_pages,
    }
