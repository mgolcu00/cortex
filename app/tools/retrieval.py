# app/tools/retrieval.py
"""
Agent retrieval tool'ları.
OpenAI Agents SDK için tool fonksiyonları.

Bu tool'lar agent'ın Confluence veritabanında arama yapmasını,
sayfa içeriklerini çekmesini ve link grafında gezinmesini sağlar.
"""

import logging
from typing import Annotated

from agents import function_tool, RunContextWrapper

from app.config import settings
from app.db.database import get_db
from app.db import vector_store
from app.utils.text import truncate_text

logger = logging.getLogger(__name__)


# ============================================================
# Tool 1: Vector Search
# ============================================================
@function_tool
def vector_search_tool(
    query: Annotated[str, "Arama sorgusu - kullanıcının sorusuna benzer dökümanları bulmak için"],
    top_k: Annotated[int, "Döndürülecek maksimum chunk sayısı"] = 30,
    max_pages: Annotated[int, "Döndürülecek maksimum sayfa sayısı"] = 12,
) -> str:
    """
    Confluence dökümanlarında vektör benzerliği ile arama yapar.

    Sorguyu embed eder ve en benzer chunk'ları bulur.
    Sonuçları sayfa bazında gruplar ve özet bilgi döndürür.

    Kullanım:
    - Kullanıcı sorusuna cevap bulmak için ilk adım olarak çağır
    - Dönen sayfa listesini inceleyip detaylı içerik için fetch_pages kullan
    """
    logger.info(f"vector_search_tool çağrıldı: query='{query[:50]}...', top_k={top_k}")

    try:
        with get_db() as db:
            results = vector_store.vector_search(
                db=db,
                query=query,
                top_k=top_k,
                max_pages=max_pages,
            )

        if not results:
            return "Arama sonucu bulunamadı. Farklı anahtar kelimelerle tekrar deneyin."

        # Sonuçları formatlı string olarak döndür
        output_lines = [f"**{len(results)} sayfa bulundu:**\n"]

        for i, page in enumerate(results, 1):
            # Her sayfa için özet bilgi
            output_lines.append(f"### {i}. {page.title}")
            output_lines.append(f"- **Page ID:** {page.page_id}")
            output_lines.append(f"- **Space:** {page.space_key}")
            output_lines.append(f"- **URL:** {page.url}")
            output_lines.append(f"- **Skor:** {page.score:.2f}")
            output_lines.append(f"- **İlgili Chunk Sayısı:** {page.chunk_count}")

            # Snippet göster (ilk 2)
            for j, snippet in enumerate(page.snippets[:2], 1):
                truncated = truncate_text(snippet, 200)
                output_lines.append(f"- **Snippet {j}:** {truncated}")

            output_lines.append("")

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"vector_search_tool hatası: {e}")
        return f"Arama sırasında hata oluştu: {str(e)}"


# ============================================================
# Tool 2: Fetch Pages
# ============================================================
@function_tool
def fetch_pages_tool(
    page_ids: Annotated[list[str], "Çekilecek sayfa ID'lerinin listesi"],
) -> str:
    """
    Belirtilen sayfa ID'lerine göre tam sayfa içeriklerini getirir.

    vector_search'ten dönen page_id'leri kullanarak
    sayfaların tam metnini alır.

    Kullanım:
    - vector_search sonuçlarından en ilgili sayfaları seç
    - page_id listesini bu tool'a gönder
    - Dönen tam içerikleri kullanarak cevap oluştur
    """
    logger.info(f"fetch_pages_tool çağrıldı: {len(page_ids)} sayfa")

    if not page_ids:
        return "Sayfa ID listesi boş."

    # Maksimum 10 sayfa çek (context limitini aşmamak için)
    page_ids = page_ids[:10]

    try:
        with get_db() as db:
            pages = vector_store.fetch_pages_by_ids(db, page_ids)

        if not pages:
            return "Belirtilen ID'lere sahip sayfa bulunamadı."

        # Sonuçları formatlı string olarak döndür
        output_lines = [f"**{len(pages)} sayfa içeriği:**\n"]

        for page in pages:
            output_lines.append(f"## {page['title']}")
            output_lines.append(f"**Space:** {page['space_key']} | **URL:** {page['url']}")
            output_lines.append("")

            # Body text (maksimum 3000 karakter)
            body = page.get("body_text", "")
            if body:
                if len(body) > 3000:
                    body = body[:3000] + "\n\n[...içerik kısaltıldı...]"
                output_lines.append(body)
            else:
                output_lines.append("(İçerik boş)")

            output_lines.append("\n---\n")

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"fetch_pages_tool hatası: {e}")
        return f"Sayfa içeriği çekilirken hata oluştu: {str(e)}"


# ============================================================
# Tool 3: Expand Via Links
# ============================================================
@function_tool
def expand_via_links_tool(
    page_ids: Annotated[list[str], "Başlangıç sayfa ID'lerinin listesi"],
    depth: Annotated[int, "Link takip derinliği (1 önerilir)"] = 1,
    limit: Annotated[int, "Maksimum döndürülecek linked sayfa sayısı"] = 20,
) -> str:
    """
    Verilen sayfaların linklendiği diğer sayfaları bulur.

    Sayfalar arası bağlantı grafını kullanarak
    ilişkili dökümanları keşfeder. Farklı space'lerdeki
    ilgili içerikleri bulmak için kullanışlıdır.

    Kullanım:
    - vector_search sonuçlarından gelen ana sayfaların ID'lerini gönder
    - Dönen linked sayfaları inceleyip gerekirse fetch_pages ile içeriklerini çek
    - Özellikle cross-space referansları bulmak için faydalı
    """
    logger.info(f"expand_via_links_tool çağrıldı: {len(page_ids)} seed sayfa")

    if not page_ids:
        return "Sayfa ID listesi boş."

    try:
        with get_db() as db:
            linked_pages = vector_store.get_linked_pages(
                db=db,
                page_ids=page_ids,
                depth=depth,
                limit=limit,
            )

        if not linked_pages:
            return "Bu sayfalardan herhangi bir internal link bulunamadı."

        # Sonuçları formatlı string olarak döndür
        output_lines = [f"**{len(linked_pages)} linked sayfa bulundu:**\n"]

        for i, page in enumerate(linked_pages, 1):
            output_lines.append(
                f"{i}. **{page['title']}** (Space: {page['space_key']})\n"
                f"   - Page ID: {page['page_id']}\n"
                f"   - URL: {page['url']}\n"
                f"   - Link Type: {page['link_type']}"
            )

        output_lines.append("\n\nBu sayfaların içeriklerini görmek için `fetch_pages` tool'unu kullanın.")

        return "\n".join(output_lines)

    except Exception as e:
        logger.error(f"expand_via_links_tool hatası: {e}")
        return f"Link genişletme sırasında hata oluştu: {str(e)}"


# ============================================================
# Tool Listesi (Agent için)
# ============================================================
RETRIEVAL_TOOLS = [
    vector_search_tool,
    fetch_pages_tool,
    expand_via_links_tool,
]
