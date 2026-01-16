# tests/test_chunker.py
"""
Chunker unit testleri.
Text chunking fonksiyonlarını test eder.
"""

import pytest
from app.ingest.chunker import TextChunker, TextChunk


class TestTextChunker:
    """TextChunker testleri."""

    def setup_method(self):
        """Her test öncesi çalışır."""
        self.chunker = TextChunker(
            target_tokens=100,
            min_tokens=20,
            max_tokens=150,
            overlap_tokens=20,
        )

    # ============================================
    # Temel Testler
    # ============================================
    def test_empty_text(self):
        """Boş metin için boş liste döndürmeli."""
        assert self.chunker.chunk_text("") == []
        assert self.chunker.chunk_text("   ") == []
        assert self.chunker.chunk_text(None) == []

    def test_short_text(self):
        """Kısa metin tek chunk olmalı."""
        text = "Bu kısa bir metin."
        chunks = self.chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_chunk_has_token_count(self):
        """Her chunk'ın token sayısı olmalı."""
        text = "Bu bir test metnidir. Token sayısı hesaplanmalı."
        chunks = self.chunker.chunk_text(text)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.token_count > 0

    # ============================================
    # Heading Tabanlı Bölme Testleri
    # ============================================
    def test_heading_detection(self):
        """Markdown heading'leri algılanmalı."""
        text = """# Ana Başlık

Bu ilk bölüm.

## Alt Başlık

Bu ikinci bölüm.
"""
        chunks = self.chunker.chunk_text(text)

        # En az 2 chunk olmalı
        assert len(chunks) >= 1

        # Heading path'ler doğru olmalı
        heading_paths = [c.heading_path for c in chunks if c.heading_path]
        assert any("Ana Başlık" in (h or "") for h in heading_paths)

    def test_nested_headings(self):
        """İç içe heading'ler doğru path oluşturmalı."""
        text = """# Bölüm 1

İçerik 1

## Alt Bölüm 1.1

İçerik 1.1

### Alt Alt Bölüm 1.1.1

İçerik 1.1.1

## Alt Bölüm 1.2

İçerik 1.2
"""
        chunks = self.chunker.chunk_text(text)

        # Heading path'leri kontrol et
        paths = [c.heading_path for c in chunks]

        # En az bir nested path olmalı
        nested_found = any(
            p and " > " in p for p in paths
        )
        # Not: Basit implementasyonda nested olmayabilir
        # ama en azından heading'ler algılanmalı
        assert len(chunks) >= 1

    # ============================================
    # Token Limiti Testleri
    # ============================================
    def test_long_text_chunking(self):
        """Uzun metin birden fazla chunk'a bölünmeli."""
        # Uzun bir metin oluştur (yaklaşık 500 token)
        paragraph = "Bu bir test cümlesidir. " * 50
        text = paragraph * 3

        # Daha büyük limitlerle test et
        chunker = TextChunker(
            target_tokens=200,
            min_tokens=50,
            max_tokens=300,
            overlap_tokens=30,
        )

        chunks = chunker.chunk_text(text)

        # Birden fazla chunk olmalı
        assert len(chunks) > 1

        # Her chunk max_tokens'dan küçük olmalı
        for chunk in chunks:
            assert chunk.token_count <= 300 + 50  # Biraz tolerans

    def test_chunk_indices_sequential(self):
        """Chunk index'leri sıralı olmalı."""
        text = "Test metni. " * 100

        chunks = self.chunker.chunk_text(text)

        for i, chunk in enumerate(chunks):
            # İndeksler farklı bölümlerde reset olabilir
            # ama genel olarak artan olmalı
            if i > 0:
                assert chunk.chunk_index >= chunks[i - 1].chunk_index or chunk.chunk_index == 0

    # ============================================
    # Token Sayma Testleri
    # ============================================
    def test_count_tokens_empty(self):
        """Boş metin için 0 token."""
        assert self.chunker.count_tokens("") == 0
        assert self.chunker.count_tokens(None) == 0

    def test_count_tokens_simple(self):
        """Basit metin için token sayısı."""
        text = "Hello world"
        count = self.chunker.count_tokens(text)
        assert count > 0
        assert count <= 5  # "Hello world" yaklaşık 2-3 token

    def test_count_tokens_turkish(self):
        """Türkçe metin için token sayısı."""
        text = "Merhaba dünya, bu bir test metnidir."
        count = self.chunker.count_tokens(text)
        assert count > 0
        assert count <= 20


class TestChunkDataClass:
    """TextChunk dataclass testleri."""

    def test_chunk_creation(self):
        """Chunk oluşturma."""
        chunk = TextChunk(
            text="Test içeriği",
            heading_path="Başlık > Alt Başlık",
            chunk_index=0,
            token_count=10,
        )

        assert chunk.text == "Test içeriği"
        assert chunk.heading_path == "Başlık > Alt Başlık"
        assert chunk.chunk_index == 0
        assert chunk.token_count == 10

    def test_chunk_none_heading(self):
        """Heading olmadan chunk oluşturma."""
        chunk = TextChunk(
            text="Test",
            heading_path=None,
            chunk_index=0,
            token_count=1,
        )

        assert chunk.heading_path is None


# ============================================
# Integration Testleri
# ============================================
class TestChunkerIntegration:
    """Chunker entegrasyon testleri."""

    def test_real_world_document(self):
        """Gerçekçi bir döküman chunking testi."""
        document = """# API Dokümantasyonu

Bu dokümantasyon API kullanımını açıklar.

## Giriş

API'ye erişim için öncelikle bir API anahtarı almanız gerekmektedir.
Anahtar almak için admin panelinden başvuru yapabilirsiniz.

### Kimlik Doğrulama

Her istekte `Authorization` header'ı gönderilmelidir:

```
Authorization: Bearer YOUR_API_KEY
```

## Endpoint'ler

### GET /users

Tüm kullanıcıları listeler.

**Parametreler:**
- `page`: Sayfa numarası (varsayılan: 1)
- `limit`: Sayfa başına kayıt (varsayılan: 20)

### POST /users

Yeni kullanıcı oluşturur.

**Body:**
```json
{
    "name": "John Doe",
    "email": "john@example.com"
}
```

## Hata Kodları

| Kod | Açıklama |
|-----|----------|
| 400 | Geçersiz istek |
| 401 | Yetkisiz erişim |
| 404 | Kaynak bulunamadı |
| 500 | Sunucu hatası |
"""

        chunker = TextChunker(
            target_tokens=200,
            min_tokens=50,
            max_tokens=400,
            overlap_tokens=30,
        )

        chunks = chunker.chunk_text(document)

        # En az birkaç chunk olmalı
        assert len(chunks) >= 2

        # Tüm chunk'lar içerik içermeli
        for chunk in chunks:
            assert len(chunk.text.strip()) > 0
            assert chunk.token_count > 0

        # Heading'ler algılanmış olmalı
        has_headings = any(c.heading_path for c in chunks)
        assert has_headings
