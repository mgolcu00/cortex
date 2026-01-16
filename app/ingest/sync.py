# app/ingest/sync.py
"""
Confluence sync orchestrator.
Full ve incremental sync işlemlerini yönetir.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import Page, Chunk, PageLink, SyncState, get_or_create_sync_state
from app.confluence.client import ConfluenceClient, ConfluencePage
from app.ingest.chunker import TextChunker
from app.ingest.embedder import get_embedder
from app.utils.text import html_to_text, extract_links

logger = logging.getLogger(__name__)


# ============================================================
# Sync Manager
# ============================================================
class SyncManager:
    """
    Confluence sync orchestrator.

    Özellikler:
    - Full sync: Tüm space ve sayfaları çek
    - Incremental sync: Sadece değişenleri çek
    - Chunking + Embedding
    - Link graph çıkarma
    """

    def __init__(self):
        """Sync manager oluştur."""
        self.confluence = ConfluenceClient()
        self.chunker = TextChunker()
        self.embedder = get_embedder()

        # İstatistikler
        self.stats = {
            "spaces_synced": 0,
            "pages_synced": 0,
            "pages_skipped": 0,
            "chunks_created": 0,
            "links_created": 0,
            "errors": [],
        }

    def run_full_sync(self) -> dict:
        """
        Full sync çalıştır.
        Tüm space ve sayfaları Confluence'dan çeker.

        Returns:
            Sync istatistikleri
        """
        logger.info("=== FULL SYNC BAŞLIYOR ===")
        start_time = datetime.now(timezone.utc)
        self._reset_stats()

        try:
            with get_db() as db:
                # 1. Tüm space'leri al
                spaces = list(self.confluence.get_all_spaces())
                logger.info(f"Toplam {len(spaces)} space bulundu")

                # 2. Her space için sayfaları işle
                for space in spaces:
                    try:
                        self._sync_space(db, space.key)
                        self.stats["spaces_synced"] += 1
                    except Exception as e:
                        error_msg = f"Space sync hatası ({space.key}): {e}"
                        logger.error(error_msg)
                        self.stats["errors"].append(error_msg)

                # 3. Sync state güncelle
                self._update_sync_state(db, success=True)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"=== FULL SYNC TAMAMLANDI ({elapsed:.1f}s) ===")
            logger.info(f"Stats: {self.stats}")

            return self.stats

        except Exception as e:
            logger.error(f"Full sync hatası: {e}")
            with get_db() as db:
                self._update_sync_state(db, success=False, error=str(e))
            raise

    def run_incremental_sync(self) -> dict:
        """
        Incremental sync çalıştır.
        Sadece son sync'ten sonra değişen sayfaları çeker.

        Returns:
            Sync istatistikleri
        """
        logger.info("=== INCREMENTAL SYNC BAŞLIYOR ===")
        start_time = datetime.now(timezone.utc)
        self._reset_stats()

        try:
            with get_db() as db:
                # Son sync zamanını al
                sync_state = get_or_create_sync_state(db)
                since = sync_state.last_run_at

                if not since:
                    logger.info("İlk sync - full sync çalıştırılıyor")
                    return self.run_full_sync()

                logger.info(f"Son sync: {since}")

                # Değişen sayfaları al
                updated_pages = list(self.confluence.get_updated_pages(since))
                logger.info(f"Güncellenen sayfa sayısı: {len(updated_pages)}")

                # Sayfaları işle
                for page in updated_pages:
                    try:
                        self._process_page(db, page)
                        self.stats["pages_synced"] += 1
                    except Exception as e:
                        error_msg = f"Page sync hatası ({page.page_id}): {e}"
                        logger.error(error_msg)
                        self.stats["errors"].append(error_msg)

                # Sync state güncelle
                self._update_sync_state(db, success=True)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"=== INCREMENTAL SYNC TAMAMLANDI ({elapsed:.1f}s) ===")
            logger.info(f"Stats: {self.stats}")

            return self.stats

        except Exception as e:
            logger.error(f"Incremental sync hatası: {e}")
            with get_db() as db:
                self._update_sync_state(db, success=False, error=str(e))
            raise

    # ============================================================
    # Private Metodlar
    # ============================================================
    def _sync_space(self, db: Session, space_key: str) -> None:
        """Bir space'in tüm sayfalarını sync et."""
        logger.info(f"Space sync: {space_key}")

        pages = list(self.confluence.get_pages_in_space(space_key))
        logger.info(f"Space '{space_key}': {len(pages)} sayfa")

        for page in pages:
            try:
                self._process_page(db, page)
            except Exception as e:
                error_msg = f"Page hatası ({page.page_id}): {e}"
                logger.warning(error_msg)
                self.stats["errors"].append(error_msg)

    def _process_page(self, db: Session, confluence_page: ConfluencePage) -> None:
        """
        Tek bir sayfayı işle.
        - Veritabanına kaydet
        - Linkleri çıkar
        - Chunk'la ve embed et
        """
        # Mevcut sayfayı kontrol et
        existing_page = db.query(Page).filter(
            Page.page_id == confluence_page.page_id
        ).first()

        # Değişiklik kontrolü
        if existing_page and existing_page.version >= confluence_page.version:
            logger.debug(f"Sayfa değişmemiş: {confluence_page.title}")
            self.stats["pages_skipped"] += 1
            return

        # HTML'i temiz text'e dönüştür
        body_text = html_to_text(confluence_page.body_html)

        # Sayfayı kaydet/güncelle
        if existing_page:
            existing_page.title = confluence_page.title
            existing_page.url = confluence_page.url
            existing_page.body_text = body_text
            existing_page.version = confluence_page.version
            existing_page.updated_at = confluence_page.updated_at
            existing_page.synced_at = datetime.now(timezone.utc)
            page = existing_page
            logger.debug(f"Sayfa güncellendi: {confluence_page.title}")
        else:
            page = Page(
                page_id=confluence_page.page_id,
                space_key=confluence_page.space_key,
                title=confluence_page.title,
                url=confluence_page.url,
                body_text=body_text,
                version=confluence_page.version,
                updated_at=confluence_page.updated_at,
                synced_at=datetime.now(timezone.utc),
            )
            db.add(page)
            logger.debug(f"Yeni sayfa: {confluence_page.title}")

        db.flush()  # page_id'nin oluşmasını garantile

        # Linkleri işle
        self._process_links(db, confluence_page)

        # Chunk'la ve embed et
        self._create_chunks(db, page, body_text)

        self.stats["pages_synced"] += 1
        db.commit()

    def _process_links(self, db: Session, confluence_page: ConfluencePage) -> None:
        """Sayfadaki linkleri çıkar ve kaydet."""
        # Mevcut linkleri sil
        db.query(PageLink).filter(
            PageLink.from_page_id == confluence_page.page_id
        ).delete()

        # Yeni linkleri çıkar
        links = extract_links(
            confluence_page.body_html,
            settings.confluence_base_url,
            confluence_page.page_id,
        )

        # Linkleri kaydet
        for link in links:
            page_link = PageLink(
                from_page_id=confluence_page.page_id,
                to_page_id=link.page_id,
                to_url=link.url,
                link_text=link.text[:500] if link.text else None,
                link_type=link.link_type,
            )
            db.add(page_link)
            self.stats["links_created"] += 1

    def _create_chunks(self, db: Session, page: Page, body_text: str) -> None:
        """Sayfa metnini chunk'la ve embed et."""
        if not body_text or not body_text.strip():
            return

        # Mevcut chunk'ları sil
        db.query(Chunk).filter(Chunk.page_id == page.page_id).delete()

        # Yeni chunk'lar oluştur
        chunks = self.chunker.chunk_text(body_text)

        if not chunks:
            return

        # Embedding'leri batch olarak al
        chunk_texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_texts(chunk_texts)

        # Chunk'ları kaydet
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            db_chunk = Chunk(
                chunk_id=uuid.uuid4(),
                page_id=page.page_id,
                space_key=page.space_key,
                heading_path=chunk.heading_path,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                token_count=chunk.token_count,
                embedding=embedding,
            )
            db.add(db_chunk)
            self.stats["chunks_created"] += 1

    def _update_sync_state(
        self,
        db: Session,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Sync state'i güncelle."""
        state = get_or_create_sync_state(db)
        state.last_run_at = datetime.now(timezone.utc)
        state.last_run_success = success
        state.last_error = error
        state.pages_synced = self.stats["pages_synced"]
        state.chunks_created = self.stats["chunks_created"]
        state.spaces_synced = self.stats["spaces_synced"]
        db.commit()

    def _reset_stats(self) -> None:
        """İstatistikleri sıfırla."""
        self.stats = {
            "spaces_synced": 0,
            "pages_synced": 0,
            "pages_skipped": 0,
            "chunks_created": 0,
            "links_created": 0,
            "errors": [],
        }


# ============================================================
# Yardımcı Fonksiyonlar
# ============================================================
def get_sync_status() -> dict:
    """Mevcut sync durumunu getir."""
    with get_db() as db:
        state = get_or_create_sync_state(db)
        return {
            "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
            "last_run_success": state.last_run_success,
            "last_error": state.last_error,
            "pages_synced": state.pages_synced,
            "chunks_created": state.chunks_created,
            "spaces_synced": state.spaces_synced,
        }


# ============================================================
# Background Scheduler
# ============================================================
_scheduler = None


def start_sync_scheduler() -> None:
    """
    Background sync scheduler başlat.
    APScheduler ile periyodik sync.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler zaten çalışıyor")
        return

    from apscheduler.schedulers.background import BackgroundScheduler

    _scheduler = BackgroundScheduler()

    # Incremental sync job'ı ekle
    interval_minutes = settings.sync_interval_minutes
    _scheduler.add_job(
        _run_scheduled_sync,
        "interval",
        minutes=interval_minutes,
        id="confluence_sync",
        name="Confluence Incremental Sync",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Sync scheduler başlatıldı (interval: {interval_minutes} dakika)")


def stop_sync_scheduler() -> None:
    """Background sync scheduler durdur."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Sync scheduler durduruldu")


def _run_scheduled_sync() -> None:
    """Scheduled sync job fonksiyonu."""
    logger.info("Scheduled sync tetiklendi")
    try:
        manager = SyncManager()
        manager.run_incremental_sync()
    except Exception as e:
        logger.error(f"Scheduled sync hatası: {e}")
