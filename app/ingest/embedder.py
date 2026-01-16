# app/ingest/embedder.py
"""
OpenAI embedding modülü.
Metinleri vektörlere dönüştürür.
"""

import logging
import time
from typing import Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Embedder
# ============================================================
class Embedder:
    """
    OpenAI embedding client.

    Özellikler:
    - Batch embedding (çoklu metin)
    - Rate limiting / retry
    - Model seçimi (text-embedding-3-large veya small)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Embedder oluştur.

        Args:
            api_key: OpenAI API anahtarı
            model: Embedding modeli
        """
        self.model = model or settings.embedding_model
        self._client = OpenAI(api_key=api_key or settings.openai_api_key)

        # Batch limitleri
        # OpenAI API limiti: 8191 token/input, 2048 input/batch
        self.max_batch_size = 100  # Güvenli batch boyutu
        self.max_retries = 3
        self.retry_delay = 1.0

    @property
    def dimensions(self) -> int:
        """Embedding vektör boyutu."""
        return settings.embedding_dimensions

    def embed_text(self, text: str) -> list[float]:
        """
        Tek bir metni embed et.

        Args:
            text: Embed edilecek metin

        Returns:
            Embedding vektörü (float listesi)
        """
        if not text or not text.strip():
            # Boş metin için sıfır vektör döndür
            return [0.0] * self.dimensions

        result = self.embed_texts([text])
        return result[0] if result else [0.0] * self.dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Birden fazla metni batch olarak embed et.

        Args:
            texts: Embed edilecek metinler

        Returns:
            Embedding vektörleri listesi
        """
        if not texts:
            return []

        # Boş metinleri filtrele ve indexlerini kaydet
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
                valid_indices.append(i)

        if not valid_texts:
            return [[0.0] * self.dimensions] * len(texts)

        # Batch'lere böl
        all_embeddings = {}
        for batch_start in range(0, len(valid_texts), self.max_batch_size):
            batch_end = min(batch_start + self.max_batch_size, len(valid_texts))
            batch_texts = valid_texts[batch_start:batch_end]
            batch_indices = valid_indices[batch_start:batch_end]

            # Batch embed et
            batch_embeddings = self._embed_batch(batch_texts)

            # Sonuçları kaydet
            for idx, embedding in zip(batch_indices, batch_embeddings):
                all_embeddings[idx] = embedding

        # Tüm sonuçları orijinal sıraya göre düzenle
        result = []
        for i in range(len(texts)):
            if i in all_embeddings:
                result.append(all_embeddings[i])
            else:
                # Boş metin için sıfır vektör
                result.append([0.0] * self.dimensions)

        return result

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Tek bir batch'i embed et (retry ile).
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Embedding batch: {len(texts)} metin")

                response = self._client.embeddings.create(
                    model=self.model,
                    input=texts,
                )

                # Sonuçları sıraya göre düzenle
                embeddings = [None] * len(texts)
                for item in response.data:
                    embeddings[item.index] = item.embedding

                logger.debug(f"Embedding tamamlandı: {len(texts)} metin")
                return embeddings

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Embedding hatası (deneme {attempt + 1}/{self.max_retries}): {e}"
                )

                # Rate limit veya server error için bekle
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Rate limit, {wait_time}s bekleniyor...")
                    time.sleep(wait_time)
                elif "500" in str(e) or "502" in str(e) or "503" in str(e):
                    wait_time = self.retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    # Diğer hatalar için hemen raise et
                    raise

        # Tüm denemeler başarısız
        raise last_error or Exception("Embedding başarısız")


# ============================================================
# Singleton Instance
# ============================================================
_embedder_instance: Optional[Embedder] = None


def get_embedder() -> Embedder:
    """
    Singleton embedder instance döndür.
    """
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder()
    return _embedder_instance
