# app/utils/text.py
"""
Metin işleme yardımcıları.
HTML'den temiz text'e dönüştürme ve link çıkarma.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


# ============================================================
# Veri Yapıları
# ============================================================
@dataclass
class ParsedLink:
    """
    Parse edilmiş link bilgisi.

    Attributes:
        url: Link URL'i
        text: Link metni
        link_type: internal, external, veya attachment
        page_id: Internal link ise Confluence page ID (nullable)
    """
    url: str
    text: str
    link_type: str  # "internal", "external", "attachment"
    page_id: Optional[str] = None


# ============================================================
# HTML -> Text Dönüşümü
# ============================================================
def html_to_text(html_content: str, preserve_headings: bool = True) -> str:
    """
    HTML/Confluence storage format'ını temiz text'e dönüştür.

    Args:
        html_content: HTML veya Confluence storage format içerik
        preserve_headings: Heading'leri markdown formatında koru

    Returns:
        Temizlenmiş düz metin
    """
    if not html_content:
        return ""

    # BeautifulSoup ile parse et
    soup = BeautifulSoup(html_content, "html.parser")

    # Script ve style tag'lerini kaldır
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Confluence macro'larını işle
    _process_confluence_macros(soup)

    # Heading'leri işaretle (opsiyonel)
    if preserve_headings:
        _mark_headings(soup)

    # Text'i çıkar
    text = soup.get_text(separator="\n")

    # Temizle ve döndür
    return clean_text(text)


def _process_confluence_macros(soup: BeautifulSoup) -> None:
    """
    Confluence macro'larını işle.
    Bazı macro'ları kaldır, bazılarının içeriğini koru.
    """
    # Kod blokları - içeriği koru
    for code_block in soup.find_all("ac:structured-macro", {"ac:name": "code"}):
        code_body = code_block.find("ac:plain-text-body")
        if code_body:
            # Kod bloğunu işaretle
            code_text = f"\n```\n{code_body.get_text()}\n```\n"
            code_block.replace_with(code_text)
        else:
            code_block.decompose()

    # Panel macro'ları - içeriği koru
    for panel in soup.find_all("ac:structured-macro", {"ac:name": "panel"}):
        body = panel.find("ac:rich-text-body")
        if body:
            panel.replace_with(body)
        else:
            panel.decompose()

    # Info/warning/note macro'ları - içeriği koru
    for macro_name in ["info", "warning", "note", "tip"]:
        for macro in soup.find_all("ac:structured-macro", {"ac:name": macro_name}):
            body = macro.find("ac:rich-text-body")
            if body:
                macro.replace_with(body)
            else:
                macro.decompose()

    # Expand macro'ları - içeriği koru
    for expand in soup.find_all("ac:structured-macro", {"ac:name": "expand"}):
        body = expand.find("ac:rich-text-body")
        if body:
            expand.replace_with(body)
        else:
            expand.decompose()

    # TOC ve diğer navigation macro'larını kaldır
    for macro_name in ["toc", "toc-zone", "children", "pagetree"]:
        for macro in soup.find_all("ac:structured-macro", {"ac:name": macro_name}):
            macro.decompose()


def _mark_headings(soup: BeautifulSoup) -> None:
    """
    Heading tag'lerini markdown formatında işaretle.
    """
    for i in range(1, 7):
        for heading in soup.find_all(f"h{i}"):
            text = heading.get_text(strip=True)
            if text:
                # Markdown heading formatı
                marker = "#" * i
                heading.replace_with(f"\n\n{marker} {text}\n\n")


# ============================================================
# Link Çıkarma
# ============================================================
def extract_links(
    html_content: str,
    base_url: str,
    current_page_id: str,
) -> list[ParsedLink]:
    """
    HTML içeriğinden linkleri çıkar.

    Args:
        html_content: HTML veya Confluence storage format içerik
        base_url: Confluence base URL (internal link tespiti için)
        current_page_id: Şu anki sayfa ID'si (self-link filtreleme için)

    Returns:
        ParsedLink listesi
    """
    if not html_content:
        return []

    links: list[ParsedLink] = []
    soup = BeautifulSoup(html_content, "html.parser")

    # Confluence internal linkler (ac:link)
    for ac_link in soup.find_all("ac:link"):
        link = _parse_confluence_link(ac_link, base_url)
        if link and link.page_id != current_page_id:
            links.append(link)

    # Standart HTML linkler
    for a_tag in soup.find_all("a", href=True):
        link = _parse_html_link(a_tag, base_url, current_page_id)
        if link:
            links.append(link)

    # Duplicate'leri kaldır (URL bazlı)
    seen_urls = set()
    unique_links = []
    for link in links:
        if link.url not in seen_urls:
            seen_urls.add(link.url)
            unique_links.append(link)

    return unique_links


def _parse_confluence_link(ac_link: Tag, base_url: str) -> Optional[ParsedLink]:
    """
    Confluence ac:link elementini parse et.
    """
    try:
        # Page reference
        page_ref = ac_link.find("ri:page")
        if page_ref:
            page_title = page_ref.get("ri:content-title", "")
            space_key = page_ref.get("ri:space-key", "")

            # Link metni
            link_body = ac_link.find("ac:link-body") or ac_link.find("ac:plain-text-link-body")
            text = link_body.get_text(strip=True) if link_body else page_title

            # URL oluştur (gerçek page_id'yi sync sırasında çözeceğiz)
            if space_key:
                url = f"{base_url}/spaces/{space_key}/pages?title={page_title}"
            else:
                url = f"{base_url}/pages?title={page_title}"

            return ParsedLink(
                url=url,
                text=text,
                link_type="internal",
                page_id=None,  # Sync sırasında çözülecek
            )

        # Attachment reference
        attachment = ac_link.find("ri:attachment")
        if attachment:
            filename = attachment.get("ri:filename", "")
            link_body = ac_link.find("ac:link-body")
            text = link_body.get_text(strip=True) if link_body else filename

            return ParsedLink(
                url=f"attachment:{filename}",
                text=text,
                link_type="attachment",
            )

        # URL reference
        url_ref = ac_link.find("ri:url")
        if url_ref:
            url = url_ref.get("ri:value", "")
            link_body = ac_link.find("ac:link-body")
            text = link_body.get_text(strip=True) if link_body else url

            link_type = _determine_link_type(url, base_url)
            return ParsedLink(url=url, text=text, link_type=link_type)

    except Exception as e:
        logger.warning(f"Confluence link parse hatası: {e}")

    return None


def _parse_html_link(
    a_tag: Tag,
    base_url: str,
    current_page_id: str,
) -> Optional[ParsedLink]:
    """
    Standart HTML <a> tag'ini parse et.
    """
    try:
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)

        # Boş veya anchor-only linkleri atla
        if not href or href.startswith("#"):
            return None

        # JavaScript linklerini atla
        if href.startswith("javascript:"):
            return None

        # Link tipini belirle
        link_type = _determine_link_type(href, base_url)

        # Internal link ise page_id çıkarmaya çalış
        page_id = None
        if link_type == "internal":
            page_id = _extract_page_id_from_url(href)
            if page_id == current_page_id:
                return None  # Self-link

        return ParsedLink(
            url=href,
            text=text or href,
            link_type=link_type,
            page_id=page_id,
        )

    except Exception as e:
        logger.warning(f"HTML link parse hatası: {e}")

    return None


def _determine_link_type(url: str, base_url: str) -> str:
    """
    URL'nin tipini belirle: internal, external, attachment.
    """
    # Attachment check
    if url.startswith("attachment:") or "/attachments/" in url:
        return "attachment"

    # Internal check
    try:
        parsed_base = urlparse(base_url)
        parsed_url = urlparse(url)

        # Aynı domain = internal
        if parsed_url.netloc == "" or parsed_url.netloc == parsed_base.netloc:
            if "/wiki/" in url or "/pages/" in url or "/spaces/" in url:
                return "internal"
    except:
        pass

    return "external"


def _extract_page_id_from_url(url: str) -> Optional[str]:
    """
    URL'den Confluence page ID'sini çıkarmaya çalış.
    """
    # /pages/viewpage.action?pageId=12345
    match = re.search(r"pageId=(\d+)", url)
    if match:
        return match.group(1)

    # /spaces/SPACE/pages/12345/...
    match = re.search(r"/pages/(\d+)", url)
    if match:
        return match.group(1)

    # /wiki/spaces/SPACE/pages/12345/...
    match = re.search(r"/wiki/spaces/\w+/pages/(\d+)", url)
    if match:
        return match.group(1)

    return None


# ============================================================
# Text Temizleme
# ============================================================
def clean_text(text: str) -> str:
    """
    Metni temizle:
    - Fazla boşlukları kaldır
    - Çoklu newline'ları birleştir
    - Başta/sonda boşlukları temizle
    """
    if not text:
        return ""

    # Çoklu boşlukları tek boşluğa indir
    text = re.sub(r"[ \t]+", " ", text)

    # Çoklu newline'ları maksimum 2'ye indir
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    # Her satırın başındaki/sonundaki boşlukları temizle
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Başta/sonda boşluk temizle
    return text.strip()


# ============================================================
# Yardımcı Fonksiyonlar
# ============================================================
def extract_headings(html_content: str) -> list[tuple[int, str]]:
    """
    HTML'den heading'leri çıkar.

    Returns:
        List of (level, text) tuples
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    headings = []

    for i in range(1, 7):
        for heading in soup.find_all(f"h{i}"):
            text = heading.get_text(strip=True)
            if text:
                headings.append((i, text))

    # Orijinal sırayı korumak için document order'a göre sırala
    # (BeautifulSoup zaten document order'da döndürür)
    return headings


def truncate_text(text: str, max_chars: int = 500) -> str:
    """
    Metni belirli karakter sayısında kes.
    Kelime sınırına dikkat eder.
    """
    if len(text) <= max_chars:
        return text

    # Kelime sınırına göre kes
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated + "..."
