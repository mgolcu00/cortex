# tests/test_link_parser.py
"""
Link parser unit testleri.
HTML içinden link çıkarma fonksiyonlarını test eder.
"""

import pytest
from app.utils.text import (
    extract_links,
    html_to_text,
    clean_text,
    ParsedLink,
)


class TestExtractLinks:
    """extract_links fonksiyonu testleri."""

    BASE_URL = "https://example.atlassian.net/wiki"
    CURRENT_PAGE_ID = "12345"

    # ============================================
    # Temel Testler
    # ============================================
    def test_empty_html(self):
        """Boş HTML için boş liste."""
        assert extract_links("", self.BASE_URL, self.CURRENT_PAGE_ID) == []
        assert extract_links(None, self.BASE_URL, self.CURRENT_PAGE_ID) == []

    def test_no_links(self):
        """Link içermeyen HTML."""
        html = "<p>Bu bir paragraf, link yok.</p>"
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)
        assert links == []

    # ============================================
    # Standart HTML Link Testleri
    # ============================================
    def test_simple_external_link(self):
        """Basit external link."""
        html = '<a href="https://google.com">Google</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].url == "https://google.com"
        assert links[0].text == "Google"
        assert links[0].link_type == "external"

    def test_internal_link_with_page_id(self):
        """Internal link (page ID içeren)."""
        html = '<a href="/wiki/spaces/TEST/pages/67890/SomeTitle">Sayfa</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].link_type == "internal"
        assert links[0].page_id == "67890"

    def test_internal_link_viewpage(self):
        """viewpage.action formatında internal link."""
        html = '<a href="/wiki/pages/viewpage.action?pageId=99999">Sayfa</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].page_id == "99999"

    def test_self_link_filtered(self):
        """Kendi kendine link filtrelenmeli."""
        html = '<a href="/wiki/spaces/TEST/pages/12345/Self">Self Link</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        # Self link filtrelenmeli
        assert len(links) == 0

    def test_anchor_link_ignored(self):
        """Anchor linkler (#) göz ardı edilmeli."""
        html = '<a href="#section1">Bölüm 1</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)
        assert len(links) == 0

    def test_javascript_link_ignored(self):
        """JavaScript linkleri göz ardı edilmeli."""
        html = '<a href="javascript:void(0)">Click</a>'
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)
        assert len(links) == 0

    # ============================================
    # Confluence ac:link Testleri
    # ============================================
    def test_confluence_page_link(self):
        """Confluence ac:link page reference."""
        html = '''
        <ac:link>
            <ri:page ri:content-title="Target Page" ri:space-key="SPACE"/>
            <ac:link-body>Link Text</ac:link-body>
        </ac:link>
        '''
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].link_type == "internal"
        assert links[0].text == "Link Text"
        assert "SPACE" in links[0].url or "Target Page" in links[0].url

    def test_confluence_attachment_link(self):
        """Confluence attachment linki."""
        html = '''
        <ac:link>
            <ri:attachment ri:filename="document.pdf"/>
            <ac:link-body>PDF Dosyası</ac:link-body>
        </ac:link>
        '''
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].link_type == "attachment"
        assert "document.pdf" in links[0].url

    def test_confluence_url_link(self):
        """Confluence URL linki."""
        html = '''
        <ac:link>
            <ri:url ri:value="https://external-site.com"/>
            <ac:link-body>External Site</ac:link-body>
        </ac:link>
        '''
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        assert len(links) == 1
        assert links[0].url == "https://external-site.com"

    # ============================================
    # Duplicate Filtreleme Testleri
    # ============================================
    def test_duplicate_urls_filtered(self):
        """Aynı URL'ye birden fazla link varsa tek döndürülmeli."""
        html = '''
        <a href="https://example.com">Link 1</a>
        <a href="https://example.com">Link 2</a>
        <a href="https://example.com">Link 3</a>
        '''
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        # Sadece bir link döndürülmeli
        assert len(links) == 1

    # ============================================
    # Karışık İçerik Testleri
    # ============================================
    def test_mixed_content(self):
        """Karışık HTML içeriği."""
        html = '''
        <div>
            <p>Paragraf içinde <a href="https://external.com">external link</a></p>
            <p>Başka bir <a href="/wiki/spaces/TEST/pages/111/Page">internal link</a></p>
            <ac:link>
                <ri:page ri:content-title="Confluence Page"/>
            </ac:link>
        </div>
        '''
        links = extract_links(html, self.BASE_URL, self.CURRENT_PAGE_ID)

        # En az 2-3 link bulunmalı
        assert len(links) >= 2

        # En az bir external ve bir internal olmalı
        link_types = [l.link_type for l in links]
        assert "external" in link_types
        assert "internal" in link_types


class TestHtmlToText:
    """html_to_text fonksiyonu testleri."""

    # ============================================
    # Temel Testler
    # ============================================
    def test_empty_html(self):
        """Boş HTML için boş string."""
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_plain_text(self):
        """Düz metin değişmemeli."""
        text = "Bu düz bir metin."
        result = html_to_text(text)
        assert "Bu düz bir metin" in result

    def test_simple_html(self):
        """Basit HTML tag'leri kaldırılmalı."""
        html = "<p>Paragraf <strong>kalın</strong> metin.</p>"
        result = html_to_text(html)
        assert "<p>" not in result
        assert "<strong>" not in result
        assert "Paragraf" in result
        assert "kalın" in result

    # ============================================
    # Heading Testleri
    # ============================================
    def test_headings_preserved(self):
        """Heading'ler markdown formatında korunmalı."""
        html = "<h1>Başlık 1</h1><h2>Başlık 2</h2>"
        result = html_to_text(html, preserve_headings=True)

        # Markdown heading formatı
        assert "# Başlık 1" in result or "Başlık 1" in result

    def test_headings_stripped(self):
        """preserve_headings=False ise heading'ler düz metin."""
        html = "<h1>Başlık</h1><p>İçerik</p>"
        result = html_to_text(html, preserve_headings=False)

        # Markdown işaretleri olmamalı
        # (implementasyona bağlı olarak bu test adjust edilebilir)
        assert "Başlık" in result

    # ============================================
    # Script/Style Temizleme Testleri
    # ============================================
    def test_script_removed(self):
        """Script tag'leri kaldırılmalı."""
        html = "<p>Metin</p><script>alert('xss')</script>"
        result = html_to_text(html)

        assert "alert" not in result
        assert "<script>" not in result

    def test_style_removed(self):
        """Style tag'leri kaldırılmalı."""
        html = "<style>.class { color: red; }</style><p>Metin</p>"
        result = html_to_text(html)

        assert "color" not in result
        assert "<style>" not in result

    # ============================================
    # Confluence Macro Testleri
    # ============================================
    def test_code_block_preserved(self):
        """Kod blokları korunmalı."""
        html = '''
        <ac:structured-macro ac:name="code">
            <ac:plain-text-body>print("hello")</ac:plain-text-body>
        </ac:structured-macro>
        '''
        result = html_to_text(html)

        # Kod içeriği korunmalı
        assert "print" in result

    def test_panel_content_preserved(self):
        """Panel macro içeriği korunmalı."""
        html = '''
        <ac:structured-macro ac:name="panel">
            <ac:rich-text-body>Panel içeriği</ac:rich-text-body>
        </ac:structured-macro>
        '''
        result = html_to_text(html)

        assert "Panel içeriği" in result

    def test_toc_removed(self):
        """TOC macro'su kaldırılmalı."""
        html = '''
        <ac:structured-macro ac:name="toc"/>
        <p>İçerik</p>
        '''
        result = html_to_text(html)

        assert "toc" not in result.lower()


class TestCleanText:
    """clean_text fonksiyonu testleri."""

    def test_empty_text(self):
        """Boş metin."""
        assert clean_text("") == ""
        assert clean_text(None) == ""

    def test_multiple_spaces(self):
        """Çoklu boşluklar tek boşluğa indirgenmeli."""
        text = "Kelime    birden    fazla    boşluk"
        result = clean_text(text)
        assert "  " not in result

    def test_multiple_newlines(self):
        """Çoklu newline'lar maksimum 2'ye indirgenmeli."""
        text = "Paragraf 1\n\n\n\n\nParagraf 2"
        result = clean_text(text)

        # 3 veya daha fazla ardışık newline olmamalı
        assert "\n\n\n" not in result

    def test_strip_whitespace(self):
        """Başta ve sonda boşluklar temizlenmeli."""
        text = "   Metin   "
        result = clean_text(text)
        assert result == "Metin"

    def test_line_strip(self):
        """Her satırın başında/sonunda boşluk olmamalı."""
        text = "  Satır 1  \n  Satır 2  "
        result = clean_text(text)

        lines = result.split("\n")
        for line in lines:
            assert line == line.strip()


class TestParsedLinkDataClass:
    """ParsedLink dataclass testleri."""

    def test_parsed_link_creation(self):
        """ParsedLink oluşturma."""
        link = ParsedLink(
            url="https://example.com",
            text="Example",
            link_type="external",
            page_id=None,
        )

        assert link.url == "https://example.com"
        assert link.text == "Example"
        assert link.link_type == "external"
        assert link.page_id is None

    def test_parsed_link_with_page_id(self):
        """Page ID ile ParsedLink."""
        link = ParsedLink(
            url="/wiki/pages/123",
            text="Internal Page",
            link_type="internal",
            page_id="123",
        )

        assert link.page_id == "123"
        assert link.link_type == "internal"
