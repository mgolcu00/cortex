# app/config.py
"""
Uygulama konfigürasyonu.
Tüm environment variable'ları Pydantic Settings ile yönetir.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Uygulama ayarları.
    .env dosyasından veya environment variable'lardan okunur.
    """

    # ============================================================
    # OpenAI Ayarları
    # ============================================================
    openai_api_key: str  # Zorunlu: OpenAI API anahtarı
    chat_model: str = "gpt-4o"  # Chat için kullanılacak model (gpt-5 vs.)
    embedding_model: str = "text-embedding-3-small"  # Embedding modeli (small=1536 dim, large=3072 dim)

    # Embedding boyutları (model seçimine göre otomatik belirlenir)
    @property
    def embedding_dimensions(self) -> int:
        """Seçilen embedding modeline göre vektör boyutu döndür."""
        if "small" in self.embedding_model:
            return 1536  # text-embedding-3-small
        return 3072  # text-embedding-3-large (varsayılan)

    # ============================================================
    # Veritabanı Ayarları
    # ============================================================
    database_url: str  # Zorunlu: PostgreSQL bağlantı URL'i
    # Örnek: postgresql+psycopg://user:pass@localhost:5432/confluence_qa

    @property
    def database_url_fixed(self) -> str:
        """
        DATABASE_URL'yi psycopg3 driver'ı için düzelt.
        postgresql:// -> postgresql+psycopg://
        """
        url = self.database_url
        # psycopg3 driver'ını kullan
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    # ============================================================
    # Confluence Ayarları
    # ============================================================
    confluence_base_url: str  # Zorunlu: https://yoursite.atlassian.net/wiki
    confluence_email: str  # Zorunlu: API erişimi için email
    confluence_api_token: str  # Zorunlu: Confluence API token

    # ============================================================
    # Sync Ayarları
    # ============================================================
    sync_interval_minutes: int = 60  # Otomatik sync aralığı (dakika)
    sync_batch_size: int = 50  # Bir seferde işlenecek sayfa sayısı

    # ============================================================
    # Chunking Ayarları
    # ============================================================
    chunk_target_tokens: int = 750  # Hedef chunk boyutu (token)
    chunk_min_tokens: int = 100  # Minimum chunk boyutu
    chunk_max_tokens: int = 1000  # Maksimum chunk boyutu
    chunk_overlap_tokens: int = 100  # Chunk'lar arası overlap

    # ============================================================
    # Retrieval Ayarları
    # ============================================================
    search_top_k: int = 30  # Varsayılan arama sonuç sayısı
    search_max_pages: int = 12  # Maksimum sayfa sayısı

    # ============================================================
    # Loglama Ayarları
    # ============================================================
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

    # Pydantic Settings konfigürasyonu
    model_config = SettingsConfigDict(
        env_file=".env",  # .env dosyasından oku
        env_file_encoding="utf-8",
        case_sensitive=False,  # Environment variable'lar case-insensitive
        extra="ignore",  # Bilinmeyen alanları görmezden gel
    )


@lru_cache
def get_settings() -> Settings:
    """
    Singleton settings instance döndür.
    lru_cache ile bir kez yüklenir ve cache'lenir.
    """
    return Settings()


# Global erişim için kısayol
settings = get_settings()
