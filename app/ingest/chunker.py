# app/ingest/chunker.py
"""
Text chunking modülü.
Confluence sayfalarını küçük parçalara böler.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

import tiktoken

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Veri Yapıları
# ============================================================
@dataclass
class TextChunk:
    """
    Metin parçası.

    Attributes:
        text: Chunk içeriği
        heading_path: Bu chunk'ın ait olduğu heading yolu (örn: "Giriş > Kurulum")
        chunk_index: Sayfa içindeki sıra numarası
        token_count: Token sayısı
    """
    text: str
    heading_path: Optional[str]
    chunk_index: int
    token_count: int


# ============================================================
# Text Chunker
# ============================================================
class TextChunker:
    """
    Metni akıllı parçalara bölen sınıf.

    Özellikler:
    - Heading'lere göre bölme
    - Token limiti kontrolü
    - Overlap ile parçalama
    """

    def __init__(
        self,
        target_tokens: int = None,
        min_tokens: int = None,
        max_tokens: int = None,
        overlap_tokens: int = None,
    ):
        """
        Chunker oluştur.

        Args:
            target_tokens: Hedef chunk boyutu (token)
            min_tokens: Minimum chunk boyutu
            max_tokens: Maksimum chunk boyutu
            overlap_tokens: Chunk'lar arası overlap
        """
        self.target_tokens = target_tokens or settings.chunk_target_tokens
        self.min_tokens = min_tokens or settings.chunk_min_tokens
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

        # Tiktoken encoder (OpenAI modelleri için)
        # cl100k_base: GPT-4, text-embedding-3 modelleri için
        self._encoder = tiktoken.get_encoding("cl100k_base")

    def chunk_text(self, text: str) -> list[TextChunk]:
        """
        Metni chunk'lara böl.

        Args:
            text: Bölünecek metin

        Returns:
            TextChunk listesi
        """
        if not text or not text.strip():
            return []

        # Önce heading'lere göre bölümlere ayır
        sections = self._split_by_headings(text)

        # Her bölümü token limitine göre chunk'la
        chunks = []
        for heading_path, section_text in sections:
            section_chunks = self._chunk_section(section_text, heading_path, len(chunks))
            chunks.extend(section_chunks)

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[Optional[str], str]]:
        """
        Metni heading'lere göre bölümlere ayır.

        Returns:
            List of (heading_path, section_text) tuples
        """
        # Markdown heading pattern: # Heading, ## Heading, etc.
        heading_pattern = r"^(#{1,6})\s+(.+)$"

        lines = text.split("\n")
        sections = []
        current_heading_stack = []  # (level, text) list
        current_section_lines = []

        for line in lines:
            match = re.match(heading_pattern, line)

            if match:
                # Önceki section'ı kaydet
                if current_section_lines:
                    heading_path = self._build_heading_path(current_heading_stack)
                    section_text = "\n".join(current_section_lines).strip()
                    if section_text:
                        sections.append((heading_path, section_text))
                    current_section_lines = []

                # Yeni heading'i stack'e ekle
                level = len(match.group(1))
                heading_text = match.group(2).strip()

                # Stack'i güncelle (daha yüksek veya eşit seviyedeki heading'leri kaldır)
                while current_heading_stack and current_heading_stack[-1][0] >= level:
                    current_heading_stack.pop()

                current_heading_stack.append((level, heading_text))
                current_section_lines.append(line)
            else:
                current_section_lines.append(line)

        # Son section'ı kaydet
        if current_section_lines:
            heading_path = self._build_heading_path(current_heading_stack)
            section_text = "\n".join(current_section_lines).strip()
            if section_text:
                sections.append((heading_path, section_text))

        # Eğer hiç section yoksa, tüm metni tek section olarak döndür
        if not sections:
            sections = [(None, text.strip())]

        return sections

    def _build_heading_path(self, heading_stack: list[tuple[int, str]]) -> Optional[str]:
        """
        Heading stack'inden path string'i oluştur.

        Örnek: [(1, "Giriş"), (2, "Kurulum")] -> "Giriş > Kurulum"
        """
        if not heading_stack:
            return None

        headings = [h[1] for h in heading_stack]
        return " > ".join(headings)

    def _chunk_section(
        self,
        text: str,
        heading_path: Optional[str],
        start_index: int,
    ) -> list[TextChunk]:
        """
        Bir section'ı token limitine göre chunk'lara böl.
        """
        tokens = self._encoder.encode(text)
        total_tokens = len(tokens)

        # Eğer metin yeterince kısaysa, tek chunk olarak döndür
        if total_tokens <= self.max_tokens:
            return [
                TextChunk(
                    text=text,
                    heading_path=heading_path,
                    chunk_index=start_index,
                    token_count=total_tokens,
                )
            ]

        # Token bazlı chunking
        chunks = []
        chunk_index = start_index
        pos = 0

        while pos < total_tokens:
            # Chunk için token aralığını belirle
            end_pos = min(pos + self.target_tokens, total_tokens)

            # Chunk text'ini oluştur
            chunk_tokens = tokens[pos:end_pos]
            chunk_text = self._encoder.decode(chunk_tokens)

            # Cümle sınırına göre ayarla (mümkünse)
            chunk_text = self._adjust_to_sentence_boundary(chunk_text, text, pos, end_pos)
            actual_tokens = len(self._encoder.encode(chunk_text))

            # Minimum token kontrolü
            if actual_tokens >= self.min_tokens or pos + self.target_tokens >= total_tokens:
                chunks.append(
                    TextChunk(
                        text=chunk_text.strip(),
                        heading_path=heading_path,
                        chunk_index=chunk_index,
                        token_count=actual_tokens,
                    )
                )
                chunk_index += 1

            # Sonraki pozisyon (overlap ile)
            pos = end_pos - self.overlap_tokens
            if pos <= 0 or pos >= total_tokens - self.min_tokens:
                pos = end_pos

        return chunks

    def _adjust_to_sentence_boundary(
        self,
        chunk_text: str,
        full_text: str,
        start_pos: int,
        end_pos: int,
    ) -> str:
        """
        Chunk'ı cümle sınırına göre ayarla.
        Kelime ortasında kesmemeye çalış.
        """
        # Son cümle sonu karakterini bul
        sentence_endings = [". ", ".\n", "? ", "?\n", "! ", "!\n"]

        best_end = len(chunk_text)
        for ending in sentence_endings:
            idx = chunk_text.rfind(ending)
            if idx > 0 and idx > len(chunk_text) * 0.5:  # En az yarısından sonra
                best_end = idx + 1
                break

        # Eğer cümle sonu bulunamadıysa, kelime sınırına göre kes
        if best_end == len(chunk_text):
            # Son boşluğu bul
            last_space = chunk_text.rfind(" ", 0, len(chunk_text) - 1)
            if last_space > len(chunk_text) * 0.8:
                best_end = last_space

        return chunk_text[:best_end]

    def count_tokens(self, text: str) -> int:
        """
        Metindeki token sayısını hesapla.

        Args:
            text: Sayılacak metin

        Returns:
            Token sayısı
        """
        if not text:
            return 0
        return len(self._encoder.encode(text))


# ============================================================
# Yardımcı Fonksiyonlar
# ============================================================
def estimate_chunks(text: str, target_tokens: int = 750) -> int:
    """
    Metin için tahmini chunk sayısı hesapla.
    """
    chunker = TextChunker(target_tokens=target_tokens)
    total_tokens = chunker.count_tokens(text)
    return max(1, total_tokens // target_tokens)
