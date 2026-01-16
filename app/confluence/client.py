# app/confluence/client.py
"""
Confluence Cloud REST API client.
Space ve page verilerini çekmek için.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator, Optional
from urllib.parse import urljoin

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Veri Yapıları
# ============================================================
@dataclass
class ConfluenceSpace:
    """Confluence space bilgisi."""
    key: str
    name: str
    type: str  # "global" veya "personal"
    status: str


@dataclass
class ConfluencePage:
    """Confluence sayfa bilgisi."""
    page_id: str
    space_key: str
    title: str
    url: str
    body_html: str  # storage format
    version: int
    updated_at: Optional[datetime]
    created_at: Optional[datetime]


# ============================================================
# Confluence API Client
# ============================================================
class ConfluenceClient:
    """
    Confluence Cloud REST API client.

    Özellikler:
    - Automatic pagination
    - Rate limiting / retry
    - Error handling
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
    ):
        """
        Client oluştur.

        Args:
            base_url: Confluence base URL (ör: https://site.atlassian.net/wiki)
            email: API erişimi için email
            api_token: Confluence API token
        """
        self.base_url = (base_url or settings.confluence_base_url).rstrip("/")
        self.email = email or settings.confluence_email
        self.api_token = api_token or settings.confluence_api_token

        # API base URL (v2 API kullanıyoruz)
        self.api_base = f"{self.base_url}/api/v2"

        # HTTP client
        self._client = httpx.Client(
            auth=(self.email, self.api_token),
            timeout=30.0,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms minimum aralık

    def close(self):
        """Client'ı kapat."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ============================================================
    # Space İşlemleri
    # ============================================================
    def get_all_spaces(self) -> Iterator[ConfluenceSpace]:
        """
        Tüm space'leri getir (pagination ile).

        Yields:
            ConfluenceSpace nesneleri
        """
        logger.info("Confluence space'leri getiriliyor...")
        cursor = None
        total = 0

        while True:
            # Request parametreleri
            params = {
                "limit": 250,  # Maximum allowed
                "status": "current",  # Sadece aktif space'ler
            }
            if cursor:
                params["cursor"] = cursor

            # API çağrısı
            response = self._request("GET", "/spaces", params=params)

            # Space'leri yield et
            for space_data in response.get("results", []):
                total += 1
                yield ConfluenceSpace(
                    key=space_data.get("key", ""),
                    name=space_data.get("name", ""),
                    type=space_data.get("type", "global"),
                    status=space_data.get("status", "current"),
                )

            # Sonraki sayfa var mı?
            links = response.get("_links", {})
            next_link = links.get("next")
            if not next_link:
                break

            # Cursor'ı çıkar
            cursor = self._extract_cursor(next_link)

        logger.info(f"Toplam {total} space bulundu")

    def get_space(self, space_key: str) -> Optional[ConfluenceSpace]:
        """
        Tek bir space getir.

        Args:
            space_key: Space anahtarı

        Returns:
            ConfluenceSpace veya None
        """
        try:
            response = self._request("GET", f"/spaces/{space_key}")
            return ConfluenceSpace(
                key=response.get("key", ""),
                name=response.get("name", ""),
                type=response.get("type", "global"),
                status=response.get("status", "current"),
            )
        except Exception as e:
            logger.warning(f"Space bulunamadı: {space_key} - {e}")
            return None

    # ============================================================
    # Page İşlemleri
    # ============================================================
    def get_pages_in_space(
        self,
        space_key: str,
        updated_since: Optional[datetime] = None,
    ) -> Iterator[ConfluencePage]:
        """
        Bir space'deki tüm sayfaları getir.

        Args:
            space_key: Space anahtarı
            updated_since: Bu tarihten sonra güncellenen sayfalar (incremental sync için)

        Yields:
            ConfluencePage nesneleri
        """
        logger.info(f"Space '{space_key}' sayfaları getiriliyor...")
        cursor = None
        total = 0

        while True:
            # Request parametreleri
            params = {
                "limit": 250,
                "status": "current",
                "body-format": "storage",  # HTML/storage format
            }
            if cursor:
                params["cursor"] = cursor

            # Space ID'yi al (v2 API space-key yerine space-id istiyor)
            endpoint = f"/spaces/{space_key}/pages"

            try:
                response = self._request("GET", endpoint, params=params)
            except Exception as e:
                # v2 API'de space key ile sorgu yapmayı dene
                logger.warning(f"Space pages endpoint hatası, alternatif denenecek: {e}")
                # Fallback: CQL ile sorgula
                yield from self._get_pages_by_cql(space_key, updated_since)
                return

            # Sayfaları yield et
            for page_data in response.get("results", []):
                page = self._parse_page_data(page_data, space_key)
                if page:
                    # updated_since filtresi
                    if updated_since and page.updated_at:
                        if page.updated_at < updated_since:
                            continue
                    total += 1
                    yield page

            # Sonraki sayfa var mı?
            links = response.get("_links", {})
            next_link = links.get("next")
            if not next_link:
                break

            cursor = self._extract_cursor(next_link)

        logger.info(f"Space '{space_key}': {total} sayfa bulundu")

    def _get_pages_by_cql(
        self,
        space_key: str,
        updated_since: Optional[datetime] = None,
    ) -> Iterator[ConfluencePage]:
        """
        CQL sorgusu ile sayfaları getir (fallback).
        v1 API kullanır.
        """
        logger.info(f"CQL ile space '{space_key}' sayfaları getiriliyor...")

        # CQL sorgusu oluştur
        cql = f'space = "{space_key}" AND type = "page"'
        if updated_since:
            date_str = updated_since.strftime("%Y-%m-%d")
            cql += f' AND lastModified >= "{date_str}"'

        start = 0
        limit = 50
        total = 0

        while True:
            params = {
                "cql": cql,
                "start": start,
                "limit": limit,
                "expand": "body.storage,version,history",
            }

            # v1 API endpoint
            url = f"{self.base_url}/rest/api/content/search"

            try:
                response = self._raw_request("GET", url, params=params)
            except Exception as e:
                logger.error(f"CQL sorgu hatası: {e}")
                break

            results = response.get("results", [])
            if not results:
                break

            for page_data in results:
                page = self._parse_page_data_v1(page_data, space_key)
                if page:
                    total += 1
                    yield page

            # Sonraki sayfa?
            if len(results) < limit:
                break
            start += limit

        logger.info(f"Space '{space_key}': {total} sayfa bulundu (CQL)")

    def get_page_by_id(self, page_id: str) -> Optional[ConfluencePage]:
        """
        Tek bir sayfayı ID ile getir.

        Args:
            page_id: Confluence page ID

        Returns:
            ConfluencePage veya None
        """
        try:
            params = {"body-format": "storage"}
            response = self._request("GET", f"/pages/{page_id}", params=params)
            return self._parse_page_data(response, response.get("spaceId", ""))
        except Exception as e:
            logger.warning(f"Sayfa bulunamadı: {page_id} - {e}")
            return None

    def get_updated_pages(
        self,
        since: datetime,
    ) -> Iterator[ConfluencePage]:
        """
        Belirli bir tarihten sonra güncellenen tüm sayfaları getir.
        Incremental sync için kullanılır.

        Args:
            since: Bu tarihten sonra güncellenen sayfalar

        Yields:
            ConfluencePage nesneleri
        """
        logger.info(f"'{since}' tarihinden sonra güncellenen sayfalar getiriliyor...")

        # CQL sorgusu ile
        date_str = since.strftime("%Y-%m-%d %H:%M")
        cql = f'type = "page" AND lastModified >= "{date_str}"'

        start = 0
        limit = 50
        total = 0

        while True:
            params = {
                "cql": cql,
                "start": start,
                "limit": limit,
                "expand": "body.storage,version,history,space",
            }

            url = f"{self.base_url}/rest/api/content/search"

            try:
                response = self._raw_request("GET", url, params=params)
            except Exception as e:
                logger.error(f"CQL sorgu hatası: {e}")
                break

            results = response.get("results", [])
            if not results:
                break

            for page_data in results:
                space_key = page_data.get("space", {}).get("key", "")
                page = self._parse_page_data_v1(page_data, space_key)
                if page:
                    total += 1
                    yield page

            if len(results) < limit:
                break
            start += limit

        logger.info(f"Toplam {total} güncellenmiş sayfa bulundu")

    # ============================================================
    # Yardımcı Metodlar
    # ============================================================
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        retries: int = 3,
    ) -> dict:
        """
        v2 API'ye request gönder.
        Rate limiting ve retry ile.
        """
        url = f"{self.api_base}{endpoint}"
        return self._raw_request(method, url, params, json, retries)

    def _raw_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        retries: int = 3,
    ) -> dict:
        """
        Ham HTTP request gönder.
        Rate limiting ve retry ile.
        """
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        # Retry loop
        last_error = None
        for attempt in range(retries):
            try:
                self._last_request_time = time.time()
                response = self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )

                # Rate limit response
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit aşıldı, {retry_after}s bekleniyor...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error - retry
                    wait = 2 ** attempt
                    logger.warning(f"Server hatası, {wait}s sonra tekrar denenecek: {e}")
                    time.sleep(wait)
                    continue
                raise

            except httpx.RequestError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"Request hatası, {wait}s sonra tekrar denenecek: {e}")
                time.sleep(wait)
                continue

        raise last_error or Exception("Request başarısız")

    def _parse_page_data(self, data: dict, space_key: str) -> Optional[ConfluencePage]:
        """
        v2 API response'unu ConfluencePage'e dönüştür.
        """
        try:
            page_id = str(data.get("id", ""))
            if not page_id:
                return None

            # Body
            body = data.get("body", {})
            body_html = ""
            if "storage" in body:
                body_html = body["storage"].get("value", "")
            elif "representation" in body:
                body_html = body.get("value", "")

            # Version
            version_info = data.get("version", {})
            version = version_info.get("number", 1) if isinstance(version_info, dict) else 1

            # Dates
            updated_at = self._parse_date(
                version_info.get("createdAt") if isinstance(version_info, dict) else None
            )
            created_at = self._parse_date(data.get("createdAt"))

            # URL
            web_ui = data.get("_links", {}).get("webui", "")
            url = f"{self.base_url}{web_ui}" if web_ui else ""

            # Space key (v2'de spaceId geliyor)
            if not space_key:
                space_key = str(data.get("spaceId", ""))

            return ConfluencePage(
                page_id=page_id,
                space_key=space_key,
                title=data.get("title", ""),
                url=url,
                body_html=body_html,
                version=version,
                updated_at=updated_at,
                created_at=created_at,
            )
        except Exception as e:
            logger.warning(f"Page parse hatası: {e}")
            return None

    def _parse_page_data_v1(self, data: dict, space_key: str) -> Optional[ConfluencePage]:
        """
        v1 API response'unu ConfluencePage'e dönüştür.
        """
        try:
            page_id = str(data.get("id", ""))
            if not page_id:
                return None

            # Body
            body = data.get("body", {}).get("storage", {})
            body_html = body.get("value", "")

            # Version
            version = data.get("version", {}).get("number", 1)

            # Dates
            history = data.get("history", {})
            updated_at = self._parse_date(history.get("lastUpdated", {}).get("when"))
            created_at = self._parse_date(history.get("createdDate"))

            # URL
            web_ui = data.get("_links", {}).get("webui", "")
            url = f"{self.base_url}{web_ui}" if web_ui else ""

            return ConfluencePage(
                page_id=page_id,
                space_key=space_key,
                title=data.get("title", ""),
                url=url,
                body_html=body_html,
                version=version,
                updated_at=updated_at,
                created_at=created_at,
            )
        except Exception as e:
            logger.warning(f"Page parse hatası (v1): {e}")
            return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """ISO 8601 tarih string'ini parse et."""
        if not date_str:
            return None

        try:
            # ISO 8601 format
            # 2024-01-15T10:30:00.000Z veya 2024-01-15T10:30:00+00:00
            date_str = date_str.replace("Z", "+00:00")
            return datetime.fromisoformat(date_str)
        except Exception:
            return None

    def _extract_cursor(self, next_link: str) -> Optional[str]:
        """Next link'ten cursor parametresini çıkar."""
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(next_link)
            params = parse_qs(parsed.query)
            cursors = params.get("cursor", [])
            return cursors[0] if cursors else None
        except Exception:
            return None

    # ============================================================
    # Health Check
    # ============================================================
    def check_connection(self) -> bool:
        """
        Confluence bağlantısını kontrol et.
        Health check için kullanılır.
        """
        try:
            # Basit bir API çağrısı
            self._request("GET", "/spaces", params={"limit": 1})
            return True
        except Exception as e:
            logger.error(f"Confluence bağlantı hatası: {e}")
            return False
