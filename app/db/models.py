# app/db/models.py
"""
Veritabanı modelleri.
SQLAlchemy ORM modelleri + pgvector entegrasyonu.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

from app.config import settings

# Base class for all models
Base = declarative_base()


# ============================================================
# Pages Tablosu
# Confluence sayfalarının metadata ve içeriğini saklar
# ============================================================
class Page(Base):
    """
    Confluence sayfası modeli.

    Her sayfa için:
    - Temel metadata (id, title, url, space)
    - Temizlenmiş metin içeriği (body_text)
    - Versiyon bilgisi (değişiklik takibi için)
    """
    __tablename__ = "pages"

    # Primary key: Confluence content ID
    page_id = Column(String(64), primary_key=True)

    # Sayfa metadata
    space_key = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    url = Column(Text, nullable=False)

    # İçerik (HTML'den temizlenmiş metin)
    body_text = Column(Text)

    # Versiyon takibi
    version = Column(Integer, default=1)
    updated_at = Column(DateTime(timezone=True))

    # Sync metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    synced_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    chunks = relationship("Chunk", back_populates="page", cascade="all, delete-orphan")
    outgoing_links = relationship(
        "PageLink",
        back_populates="from_page",
        foreign_keys="PageLink.from_page_id",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Page(id={self.page_id}, title='{self.title[:30]}...')>"


# ============================================================
# Chunks Tablosu
# Sayfaların parçalanmış metinleri ve embedding'leri
# ============================================================
class Chunk(Base):
    """
    Metin chunk modeli.

    Her chunk:
    - Bir sayfaya ait
    - Heading path ile konumu belirli
    - Embedding vektörü ile aranabilir
    """
    __tablename__ = "chunks"

    # Primary key: UUID
    chunk_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Sayfa ilişkisi
    page_id = Column(
        String(64),
        ForeignKey("pages.page_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Chunk metadata
    space_key = Column(String(64), nullable=False)
    heading_path = Column(Text)  # "Başlık > Alt Başlık" formatı
    chunk_index = Column(Integer, nullable=False)  # Sayfa içindeki sıra

    # İçerik
    text = Column(Text, nullable=False)
    token_count = Column(Integer)

    # Embedding vektörü (pgvector)
    # Boyut config'den alınır (3072 veya 1536)
    embedding = Column(Vector(settings.embedding_dimensions))

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    page = relationship("Page", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.chunk_id}, page={self.page_id}, index={self.chunk_index})>"


# pgvector index - cosine similarity için
# ivfflat index (maks 2000 boyut destekler, text-embedding-3-small için uygun)
# NOT: Çok az veri varken (<1000 chunk) index oluşturulmaz, sonra manuel eklenebilir
# Index büyük veri setlerinde arama hızını artırır
Index(
    "idx_chunks_embedding",
    Chunk.embedding,
    postgresql_using="ivfflat",
    postgresql_with={"lists": 100},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)


# ============================================================
# Page Links Tablosu
# Sayfalar arası bağlantı grafı
# ============================================================
class PageLink(Base):
    """
    Sayfa bağlantısı modeli.

    Sayfalar arası link grafını saklar:
    - Internal linkler (to_page_id dolu)
    - External linkler (sadece URL)
    - Attachment linkler
    """
    __tablename__ = "page_links"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Kaynak sayfa
    from_page_id = Column(
        String(64),
        ForeignKey("pages.page_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hedef sayfa (internal link ise)
    to_page_id = Column(String(64), index=True, nullable=True)

    # Link detayları
    to_url = Column(Text, nullable=False)
    link_text = Column(Text)
    link_type = Column(String(32), default="internal")  # internal, external, attachment

    # İlişkiler
    from_page = relationship(
        "Page",
        back_populates="outgoing_links",
        foreign_keys=[from_page_id],
    )

    def __repr__(self) -> str:
        return f"<PageLink(from={self.from_page_id}, to={self.to_page_id or self.to_url[:30]})>"


# ============================================================
# Sync State Tablosu
# Son sync durumu ve istatistikleri
# ============================================================
class SyncState(Base):
    """
    Sync durumu modeli.

    Singleton tablo (id=1):
    - Son çalışma zamanı
    - Başarı durumu
    - İstatistikler
    """
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, default=1)

    # Son çalışma
    last_run_at = Column(DateTime(timezone=True))
    last_run_success = Column(Boolean, default=False)
    last_error = Column(Text)

    # İstatistikler
    pages_synced = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    spaces_synced = Column(Integer, default=0)

    def __repr__(self) -> str:
        status = "success" if self.last_run_success else "failed"
        return f"<SyncState(last_run={self.last_run_at}, status={status})>"


# ============================================================
# Chat Sessions Tablosu
# Kullanıcı sohbet oturumları
# ============================================================
class ChatSession(Base):
    """
    Chat session modeli.
    Her session birden fazla mesaj içerir.
    """
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True)
    title = Column(String(256), default="Yeni Sohbet")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # İlişkiler
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title='{self.title[:30]}')>"


# ============================================================
# Chat Messages Tablosu
# Sohbet mesajları
# ============================================================
class ChatMessage(Base):
    """
    Chat mesajı modeli.
    Her mesaj bir session'a ait.
    """
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(64),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    sources = Column(Text)  # JSON string
    stats = Column(Text)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role}, session={self.session_id})>"


# ============================================================
# Usage Stats Tablosu
# Kullanım istatistikleri (singleton)
# ============================================================
class UsageStats(Base):
    """
    Kullanım istatistikleri modeli.
    Singleton tablo (id=1).
    """
    __tablename__ = "usage_stats"

    id = Column(Integer, primary_key=True, default=1)
    total_requests = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost_usd = Column(Integer, default=0)  # Stored as micro-dollars (x1000000)
    total_confluence_requests = Column(Integer, default=0)
    total_db_requests = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<UsageStats(requests={self.total_requests}, tokens={self.total_tokens})>"


# ============================================================
# App Settings Tablosu
# Uygulama ayarları (key-value)
# ============================================================
class AppSettings(Base):
    """
    Uygulama ayarları modeli.
    Key-value çiftleri saklar.
    """
    __tablename__ = "app_settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<AppSettings(key={self.key})>"


# ============================================================
# Message Feedback Tablosu
# Kullanici geri bildirimleri (like/dislike)
# ============================================================
class MessageFeedback(Base):
    """
    Mesaj geri bildirimi modeli.
    Kullanicilarin mesajlari begenmesi/begenmemesi.
    """
    __tablename__ = "message_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    message_index = Column(Integer, nullable=False)  # Mesajin session icindeki sirasi
    feedback = Column(String(16), nullable=False)  # 'like' veya 'dislike'
    comment = Column(Text)  # Opsiyonel kullanici yorumu
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<MessageFeedback(session={self.session_id}, index={self.message_index}, feedback={self.feedback})>"


# ============================================================
# Yardımcı Fonksiyonlar
# ============================================================
def get_or_create_sync_state(db) -> SyncState:
    """
    SyncState kaydını getir veya oluştur.
    Singleton pattern - her zaman id=1.
    """
    state = db.query(SyncState).filter(SyncState.id == 1).first()
    if not state:
        state = SyncState(id=1)
        db.add(state)
        db.commit()
    return state


def get_or_create_usage_stats(db) -> UsageStats:
    """
    UsageStats kaydını getir veya oluştur.
    Singleton pattern - her zaman id=1.
    """
    stats = db.query(UsageStats).filter(UsageStats.id == 1).first()
    if not stats:
        stats = UsageStats(id=1)
        db.add(stats)
        db.commit()
    return stats
