import logging
import re
import json
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime

from agents import Agent, Runner, function_tool, set_default_openai_key, ModelSettings
from openai.types.shared import Reasoning

from app.config import settings
from app.db.database import get_db
from app.db import vector_store
from app.db.models import (
    ChatSession,
    ChatMessage,
    UsageStats,
    AppSettings,
    get_or_create_usage_stats,
)

logger = logging.getLogger(__name__)

set_default_openai_key(settings.openai_api_key)


# ============================================================
# Configurable Instructions
# ============================================================
DEFAULT_INSTRUCTIONS = """Sen şirketin Confluence bilgi asistanısın. Şirket içi dokümanlara, prosedürlere ve teknik bilgilere erişimin var. Amacın çalışanlara hızlı ve doğru bilgi sağlamak.

## Kimliğin
- Adın: Confluence AI Asistan
- Rolün: Şirket içi bilgi yardımcısı
- Dil: Türkçe (teknik terimler İngilizce kalabilir)
- Ton: Profesyonel ama samimi, yardımsever

## Temel Prensipler
1. **Doğruluk Öncelikli**: Sadece Confluence'da bulunan bilgilere dayan. Emin olmadığın bilgiyi uydurma.
2. **Kaynak Göster**: Her zaman bilgiyi nereden aldığını belirt.
3. **Öz ve Net**: Gereksiz uzatma, konuya odaklan.
4. **Proaktif Yardım**: İlgili ek bilgileri de öner.

## Ne Zaman search_confluence Kullanmalısın?
✅ KULLAN:
- Spesifik bilgi, döküman veya prosedür soruları
- Teknik sorular (API, deployment, konfigürasyon, mimari)
- "Nasıl yapılır?", "Nerede bulunur?", "Ne anlama gelir?" soruları
- Proje, ürün veya süreç hakkında sorular
- Hata çözümü veya troubleshooting
- Onboarding, policy veya guideline soruları

❌ KULLANMA:
- Selamlaşma: "Merhaba", "Günaydın", "Nasılsın?"
- Teşekkür/Onay: "Teşekkürler", "Anladım", "Tamam", "Süper"
- Hakkında sorular: "Sen kimsin?", "Ne yapabilirsin?"
- Takip istekleri: "Devam et", "Daha fazla", "Başka?"
- Önceki cevabı açıklama: "Bunu biraz açar mısın?"
- Genel sohbet ve şakalar

## Arama Stratejisi
1. **search_confluence** ile en alakalı sayfaları bul
2. Sonuçlar yetersizse **get_page_content** ile detaylı içerik al
3. İlişkili bilgi gerekirse **find_related_pages** kullan
4. Birden fazla kaynak varsa sentezle, tek kaynak varsa özetle

## Cevap Formatı
- Kısa ve öz cevaplar ver (3-5 cümle ideal)
- Teknik detay gerekirse bullet point kullan
- Kod örnekleri için code block kullan
- Linkleri her zaman [Başlık](URL) formatında yaz

## Kaynak Gösterimi
Arama yaptıysan, cevabın sonunda kaynakları listele:

**Kaynaklar:**
- [Sayfa Adı](confluence_url)
- [Diğer Sayfa](confluence_url)

## Belirsizlik Durumları
- Bilgi bulamazsan: "Confluence'da bu konuda bir döküman bulamadım. [Alternatif öneri]"
- Kısmi bilgi varsa: "Şu kadarını bulabildim: ... Daha fazla bilgi için [X] sayfasına bakabilirsin."
- Çelişkili bilgi varsa: "Farklı kaynaklarda farklı bilgiler var. En güncel olan [X] sayfasına göre..."

## Özel Durumlar
- Gizli/hassas bilgi sorulursa: Sadece Confluence'da açıkça paylaşılan bilgileri ver
- Güncellenmemiş bilgi şüphesi: Dökümanın son güncellenme tarihini belirt
- Yetersiz context: Netleştirici soru sor

## Konuşma Örnekleri

👤 "Merhaba"
🤖 "Merhaba! Confluence dökümanları hakkında nasıl yardımcı olabilirim?"

👤 "Deployment nasıl yapılıyor?"
🤖 [search_confluence kullan] → Adım adım açıkla + kaynak göster

👤 "Teşekkürler, çok yardımcı oldun"
🤖 "Rica ederim! Başka bir sorun olursa yardımcı olmaktan memnuniyet duyarım."

👤 "API rate limit nedir?"
🤖 [search_confluence kullan] → Teknik detayları açıkla + kaynak göster
"""


def get_instructions() -> str:
    """Mevcut instructions'ı döndür (PostgreSQL'den)."""
    try:
        with get_db() as db:
            setting = db.query(AppSettings).filter(AppSettings.key == "instructions").first()
            if setting:
                return setting.value
    except Exception as e:
        logger.error(f"get_instructions hatası: {e}")
    return DEFAULT_INSTRUCTIONS


def set_instructions(new_instructions: str):
    """Instructions'ı güncelle (PostgreSQL'e kaydet)."""
    try:
        with get_db() as db:
            setting = db.query(AppSettings).filter(AppSettings.key == "instructions").first()
            if setting:
                setting.value = new_instructions
            else:
                setting = AppSettings(key="instructions", value=new_instructions)
                db.add(setting)
    except Exception as e:
        logger.error(f"set_instructions hatası: {e}")


def reset_instructions():
    """Default'a dön."""
    try:
        with get_db() as db:
            db.query(AppSettings).filter(AppSettings.key == "instructions").delete()
    except Exception as e:
        logger.error(f"reset_instructions hatası: {e}")


# ============================================================
# Statistics
# ============================================================
@dataclass
class RequestStats:
    """Tek bir istek için istatistikler."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    confluence_requests: int = 0
    db_requests: int = 0
    embedding_requests: int = 0
    tool_calls: list = field(default_factory=list)
    used_search: bool = False

    @property
    def estimated_cost(self) -> float:
        input_cost = (self.prompt_tokens / 1_000_000) * 5
        output_cost = (self.completion_tokens / 1_000_000) * 15
        embedding_cost = (self.embedding_requests * 500 / 1_000_000) * 0.02
        return input_cost + output_cost + embedding_cost

    @property
    def duration_ms(self) -> int:
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return 0

    def to_dict(self) -> dict:
        return {
            "duration_ms": self.duration_ms,
            "tokens": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
                "total": self.total_tokens
            },
            "api_calls": {
                "confluence": self.confluence_requests,
                "database": self.db_requests,
                "embedding": self.embedding_requests
            },
            "tool_calls": self.tool_calls,
            "used_search": self.used_search,
            "estimated_cost_usd": round(self.estimated_cost, 6)
        }


_current_stats: Optional[RequestStats] = None


def _init_stats():
    global _current_stats
    _current_stats = RequestStats()


def _finalize_stats():
    global _current_stats
    if _current_stats:
        _current_stats.end_time = datetime.now()
        try:
            with get_db() as db:
                usage = get_or_create_usage_stats(db)
                usage.total_requests += 1
                usage.total_tokens += _current_stats.total_tokens
                usage.total_cost_usd += int(_current_stats.estimated_cost * 1_000_000)
                usage.total_confluence_requests += _current_stats.confluence_requests
                usage.total_db_requests += _current_stats.db_requests
        except Exception as e:
            logger.error(f"Stats kaydetme hatası: {e}")


def get_total_stats() -> dict:
    """PostgreSQL'den toplam istatistikleri al."""
    try:
        with get_db() as db:
            usage = get_or_create_usage_stats(db)
            return {
                "total_requests": usage.total_requests,
                "total_tokens": usage.total_tokens,
                "total_cost_usd": round(usage.total_cost_usd / 1_000_000, 4),
                "total_confluence_requests": usage.total_confluence_requests,
                "total_db_requests": usage.total_db_requests,
            }
    except Exception as e:
        logger.error(f"get_total_stats hatası: {e}")

    return {
        "total_requests": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_confluence_requests": 0,
        "total_db_requests": 0,
    }


def _log_tool_call(tool_name: str, args: dict, result_preview: str):
    if _current_stats:
        _current_stats.tool_calls.append({
            "tool": tool_name,
            "args": {k: str(v)[:50] for k, v in args.items()},
            "result_preview": result_preview[:150] if result_preview else ""
        })
        _current_stats.used_search = True


def _increment_db_requests(count: int = 1):
    if _current_stats:
        _current_stats.db_requests += count


def _increment_embedding_requests(count: int = 1):
    if _current_stats:
        _current_stats.embedding_requests += count


# ============================================================
# Agent Tools
# ============================================================
@function_tool
def search_confluence(query: str, top_k: int = 15) -> str:
    """
    Confluence dökümanlarında arama yapar. Sadece bilgi gerektiğinde kullan.
    Selamlaşma veya genel sohbet için KULLANMA.

    Args:
        query: Arama sorgusu
        top_k: Maksimum sonuç sayısı

    Returns:
        Bulunan sayfaların listesi
    """
    logger.info(f"[TOOL] search_confluence: '{query[:50]}...'")

    try:
        _increment_embedding_requests(1)
        _increment_db_requests(1)

        with get_db() as db:
            results = vector_store.vector_search(
                db=db,
                query=query,
                top_k=top_k,
                max_pages=8,
            )

        if not results:
            result = "Arama sonucu bulunamadı."
            _log_tool_call("search_confluence", {"query": query}, result)
            return result

        output_lines = [f"{len(results)} sayfa bulundu:\n"]
        for i, page in enumerate(results, 1):
            output_lines.append(f"{i}. {page.title}")
            output_lines.append(f"   ID: {page.page_id}")
            output_lines.append(f"   URL: {page.url}")
            output_lines.append(f"   Benzerlik: %{int(page.score * 100)}")
            if page.snippets:
                snippet = page.snippets[0][:150] + "..." if len(page.snippets[0]) > 150 else page.snippets[0]
                output_lines.append(f"   Özet: {snippet}")
            output_lines.append("")

        result = "\n".join(output_lines)
        _log_tool_call("search_confluence", {"query": query}, f"{len(results)} sayfa")
        return result

    except Exception as e:
        logger.error(f"search_confluence hatası: {e}")
        error_msg = f"Arama hatası: {str(e)}"
        _log_tool_call("search_confluence", {"query": query}, error_msg)
        return error_msg


@function_tool
def get_page_content(page_ids: str) -> str:
    """
    Belirli sayfaların tam içeriğini getirir.

    Args:
        page_ids: Virgülle ayrılmış sayfa ID'leri (örn: "123,456")

    Returns:
        Sayfa içerikleri
    """
    logger.info(f"[TOOL] get_page_content: {page_ids}")

    ids = [pid.strip() for pid in page_ids.split(",") if pid.strip()]
    if not ids:
        return "Sayfa ID belirtilmedi."

    ids = ids[:5]
    _increment_db_requests(1)

    try:
        with get_db() as db:
            pages = vector_store.fetch_pages_by_ids(db, ids)

        if not pages:
            result = "Sayfa bulunamadı."
            _log_tool_call("get_page_content", {"page_ids": page_ids}, result)
            return result

        output_lines = []
        for page in pages:
            output_lines.append(f"=== {page['title']} ===")
            output_lines.append(f"URL: {page['url']}")
            output_lines.append("")

            body = page.get("body_text", "")
            if body:
                if len(body) > 3000:
                    body = body[:3000] + "\n[...kısaltıldı...]"
                output_lines.append(body)
            else:
                output_lines.append("(Boş içerik)")
            output_lines.append("\n" + "="*40 + "\n")

        result = "\n".join(output_lines)
        _log_tool_call("get_page_content", {"page_ids": page_ids}, f"{len(pages)} sayfa")
        return result

    except Exception as e:
        logger.error(f"get_page_content hatası: {e}")
        return f"Hata: {str(e)}"


@function_tool
def find_related_pages(page_ids: str) -> str:
    """
    Verilen sayfalarla ilişkili diğer sayfaları bulur.

    Args:
        page_ids: Kaynak sayfa ID'leri

    Returns:
        İlişkili sayfalar
    """
    logger.info(f"[TOOL] find_related_pages: {page_ids}")

    ids = [pid.strip() for pid in page_ids.split(",") if pid.strip()]
    if not ids:
        return "Sayfa ID belirtilmedi."

    _increment_db_requests(1)

    try:
        with get_db() as db:
            linked_pages = vector_store.get_linked_pages(
                db=db,
                page_ids=ids,
                depth=1,
                limit=10,
            )

        if not linked_pages:
            return "İlişkili sayfa bulunamadı."

        output_lines = [f"{len(linked_pages)} ilişkili sayfa:\n"]
        for i, page in enumerate(linked_pages, 1):
            output_lines.append(f"{i}. {page['title']}")
            output_lines.append(f"   ID: {page['page_id']}")
            output_lines.append(f"   URL: {page['url']}")

        result = "\n".join(output_lines)
        _log_tool_call("find_related_pages", {"page_ids": page_ids}, f"{len(linked_pages)} sayfa")
        return result

    except Exception as e:
        logger.error(f"find_related_pages hatası: {e}")
        return f"Hata: {str(e)}"


TOOLS = [search_confluence, get_page_content, find_related_pages]


# ============================================================
# Data Structures
# ============================================================
@dataclass
class ChatSource:
    title: str
    url: str


@dataclass
class ChatResult:
    session_id: str
    answer: str
    sources: list
    stats: dict
    success: bool
    session_usage: Optional[dict] = None
    error: Optional[str] = None


# ============================================================
# Session Manager
# ============================================================
class SessionManager:
    """PostgreSQL session yönetimi."""

    def create_or_get_session(self, session_id: str) -> dict:
        """Session al veya oluştur."""
        with get_db() as db:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

            if session:
                return {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                }

            session = ChatSession(id=session_id, title="Yeni Sohbet")
            db.add(session)

            return {
                "id": session_id,
                "title": "Yeni Sohbet",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

    def save_message(self, session_id: str, role: str, content: str, sources: list = None, stats: dict = None):
        """Mesajı kaydet."""
        with get_db() as db:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                session = ChatSession(id=session_id, title="Yeni Sohbet")
                db.add(session)
                db.flush()

            if role == "user":
                msg_count = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id,
                    ChatMessage.role == "user"
                ).count()
                if msg_count == 0:
                    title = content[:50] + ("..." if len(content) > 50 else "")
                    session.title = title

            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                sources=json.dumps(sources) if sources else None,
                stats=json.dumps(stats) if stats else None,
            )
            db.add(message)

    async def get_all_sessions(self) -> list:
        """Tüm session'ları listele."""
        try:
            with get_db() as db:
                sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()

                result = []
                for s in sessions:
                    msg_count = db.query(ChatMessage).filter(ChatMessage.session_id == s.id).count()
                    result.append({
                        "id": s.id,
                        "title": s.title,
                        "started_at": s.created_at.isoformat() if s.created_at else None,
                        "last_message": s.updated_at.isoformat() if s.updated_at else None,
                        "message_count": msg_count,
                    })
                return result
        except Exception as e:
            logger.error(f"get_all_sessions hatası: {e}")
            return []

    async def get_session_messages(self, session_id: str) -> list:
        """Session mesajlarını al."""
        try:
            with get_db() as db:
                messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).order_by(ChatMessage.created_at.asc()).all()

                return [
                    {
                        "role": m.role,
                        "content": m.content,
                        "sources": json.loads(m.sources) if m.sources else [],
                        "stats": json.loads(m.stats) if m.stats else None,
                        "timestamp": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ]
        except Exception as e:
            logger.error(f"get_session_messages hatası: {e}")
            return []

    async def get_session_usage(self, session_id: str) -> Optional[dict]:
        """Session kullanım istatistiklerini al."""
        try:
            with get_db() as db:
                messages = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session_id
                ).all()

                total_messages = len(messages)
                total_tokens = 0
                total_cost = 0.0

                for m in messages:
                    if m.stats:
                        try:
                            stats = json.loads(m.stats)
                            total_tokens += stats.get("tokens", {}).get("total", 0)
                            total_cost += stats.get("estimated_cost_usd", 0)
                        except:
                            pass

                return {
                    "total_messages": total_messages,
                    "total_tokens": total_tokens,
                    "total_cost_usd": round(total_cost, 6),
                }
        except Exception as e:
            logger.error(f"get_session_usage hatası: {e}")
        return None

    async def delete_session(self, session_id: str) -> bool:
        """Session sil."""
        try:
            with get_db() as db:
                db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
                db.query(ChatSession).filter(ChatSession.id == session_id).delete()
                return True
        except Exception as e:
            logger.error(f"delete_session hatası: {e}")
            return False


# Global session manager
session_manager = SessionManager()


# ============================================================
# Agent Factory
# ============================================================
def create_agent() -> Agent:
    """Agent oluştur."""
    model_settings = None
    if settings.chat_model.startswith("gpt-5"):
        model_settings = ModelSettings(reasoning=Reasoning(effort="minimal"), verbosity="low")
    return Agent(
        name="ConfluenceAssistant",
        instructions=get_instructions(),
        model=settings.chat_model,
        tools=TOOLS,
        model_settings=model_settings,
    )


def build_message_history(session_id: str) -> list:
    """Session'dan mesaj geçmişini al ve agent formatına çevir."""
    messages = []
    try:
        with get_db() as db:
            db_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()

            for m in db_messages:
                messages.append({
                    "role": m.role,
                    "content": m.content,
                })
    except Exception as e:
        logger.error(f"build_message_history hatası: {e}")

    return messages


# ============================================================
# Chat
# ============================================================
async def run_chat(message: str, session_id: str) -> ChatResult:
    """Session ile chat."""
    logger.info(f"Chat: session={session_id[:8]}..., message='{message[:30]}...'")

    _init_stats()
    agent = create_agent()
    session_manager.create_or_get_session(session_id)
    session_manager.save_message(session_id, "user", message)
    history = build_message_history(session_id)

    try:
        if len(history) > 1:
            result = await Runner.run(
                agent,
                history,
            )
        else:
            result = await Runner.run(
                agent,
                message,
            )

        response_text = result.final_output or ""
        sources = extract_sources(response_text)

        if _current_stats:
            if hasattr(result.context_wrapper, 'usage') and result.context_wrapper.usage:
                _current_stats.prompt_tokens = getattr(result.context_wrapper.usage, 'input_tokens', 0)
                _current_stats.completion_tokens = getattr(result.context_wrapper.usage, 'output_tokens', 0)
                _current_stats.total_tokens = _current_stats.prompt_tokens + _current_stats.completion_tokens
            else:
                _current_stats.prompt_tokens = len(message.split()) * 2 + 300
                _current_stats.completion_tokens = len(response_text.split()) * 2
                _current_stats.total_tokens = _current_stats.prompt_tokens + _current_stats.completion_tokens

        _finalize_stats()
        stats = _current_stats.to_dict() if _current_stats else {}

        session_manager.save_message(
            session_id,
            "assistant",
            response_text,
            sources=[asdict(s) for s in sources],
            stats=stats
        )

        session_usage = await session_manager.get_session_usage(session_id)

        logger.info(f"Chat OK: {len(sources)} kaynak, {stats.get('duration_ms', 0)}ms")

        return ChatResult(
            session_id=session_id,
            answer=response_text,
            sources=[asdict(s) for s in sources],
            stats=stats,
            session_usage=session_usage,
            success=True
        )

    except Exception as e:
        logger.error(f"Chat hatası: {e}", exc_info=True)
        _finalize_stats()
        stats = _current_stats.to_dict() if _current_stats else {}

        return ChatResult(
            session_id=session_id,
            answer="",
            sources=[],
            stats=stats,
            success=False,
            error=str(e)
        )


def extract_sources(response: str) -> list[ChatSource]:
    """Yanıttan kaynakları çıkar."""
    sources = []
    pattern = r'\[([^\]]+)\]\((https?://[^)]+)\)'
    matches = re.findall(pattern, response)

    seen = set()
    for title, url in matches:
        if url not in seen:
            seen.add(url)
            sources.append(ChatSource(title=title.strip(), url=url))

    return sources
