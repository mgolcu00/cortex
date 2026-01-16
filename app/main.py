import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.db.database import init_db, check_db_connection, get_db
from app.db.models import Page, Chunk, SyncState, MessageFeedback, AppSettings
from app.confluence.client import ConfluenceClient
from app.ingest.sync import SyncManager, get_sync_status, start_sync_scheduler, stop_sync_scheduler
from app.agent import (
    run_chat,
    get_total_stats,
    session_manager,
    get_instructions,
    set_instructions,
    reset_instructions,
    DEFAULT_INSTRUCTIONS,
)

# ============================================================
# Logging
# ============================================================
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uygulama başlatılıyor...")

    try:
        init_db()
        logger.info("Veritabanı hazır")
    except Exception as e:
        logger.error(f"Veritabanı hatası: {e}")
        raise

    try:
        start_sync_scheduler()
        logger.info("Sync scheduler başlatıldı")
    except Exception as e:
        logger.warning(f"Scheduler hatası: {e}")

    logger.info("Uygulama hazır!")
    yield

    logger.info("Kapatılıyor...")
    stop_sync_scheduler()


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="Cortex",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Models
# ============================================================
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class SyncRequest(BaseModel):
    mode: str = "incremental"


class InstructionsRequest(BaseModel):
    instructions: str


class FeedbackRequest(BaseModel):
    session_id: str
    message_index: int
    feedback: str  # 'like' or 'dislike'
    comment: Optional[str] = None


class StarterItem(BaseModel):
    title: str
    description: str
    icon: str = "Lightbulb"  # Lucide icon name


class StartersRequest(BaseModel):
    starters: list[StarterItem]


DEFAULT_STARTERS = [
    {"title": "Proje Yapisi", "description": "Kod organizasyonu nasil?", "icon": "Code"},
    {"title": "API Dokumantasyonu", "description": "Endpoint'ler ve kullanim", "icon": "FileText"},
    {"title": "Deployment Sureci", "description": "Production'a nasil cikarim?", "icon": "Rocket"},
    {"title": "Onboarding", "description": "Yeni baslayanlar icin rehber", "icon": "Lightbulb"},
]


# ============================================================
# Health & Stats
# ============================================================
@app.get("/health")
async def health_check():
    db_ok = check_db_connection()

    try:
        client = ConfluenceClient()
        confluence_ok = client.check_connection()
    except Exception:
        confluence_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "confluence": "connected" if confluence_ok else "disconnected",
    }


@app.get("/api/stats")
async def get_stats():
    """Toplam kullanım istatistikleri."""
    total = get_total_stats()

    page_count = 0
    chunk_count = 0
    last_sync = None
    last_sync_success = None

    try:
        with get_db() as db:
            page_count = db.query(Page).count()
            chunk_count = db.query(Chunk).count()
            sync_state = db.query(SyncState).first()
            if sync_state:
                last_sync = sync_state.last_run_at.isoformat() if sync_state.last_run_at else None
                last_sync_success = sync_state.last_run_success
    except Exception:
        pass

    return {
        "usage": total,
        "database": {
            "pages": page_count,
            "chunks": chunk_count,
            "last_sync": last_sync,
            "last_sync_success": last_sync_success,
        }
    }


# ============================================================
# Chat
# ============================================================
@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    message = request.message

    logger.info(f"Chat: {session_id[:8]}... - '{message[:30]}...'")

    try:
        result = await run_chat(message, session_id)

        if result.success:
            return {
                "success": True,
                "session_id": session_id,
                "answer": result.answer,
                "sources": result.sources,
                "stats": result.stats,
                "session_usage": result.session_usage,
            }
        else:
            return {
                "success": False,
                "session_id": session_id,
                "error": result.error,
                "stats": result.stats,
            }

    except Exception as e:
        logger.error(f"Chat hatası: {e}", exc_info=True)
        return {
            "success": False,
            "session_id": session_id,
            "error": str(e),
        }


# ============================================================
# Sessions (SQLite backed)
# ============================================================
@app.get("/sessions")
async def get_sessions():
    """Tüm session'ları listele."""
    sessions = await session_manager.get_all_sessions()
    result = []
    for s in sessions:
        messages = await session_manager.get_session_messages(s["id"])
        title = "Yeni Sohbet"
        for m in messages:
            if m["role"] == "user":
                title = m["content"][:50] + ("..." if len(m["content"]) > 50 else "")
                break

        result.append({
            "id": s["id"],
            "title": title,
            "started_at": s["started_at"],
            "last_message": s["last_message"],
            "message_count": s["message_count"],
        })

    return result


@app.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """Session detayı."""
    messages = await session_manager.get_session_messages(session_id)

    if not messages:
        raise HTTPException(status_code=404, detail="Session bulunamadı")

    title = "Sohbet"
    for m in messages:
        if m["role"] == "user":
            title = m["content"][:50] + ("..." if len(m["content"]) > 50 else "")
            break

    usage = await session_manager.get_session_usage(session_id)

    return {
        "id": session_id,
        "title": title,
        "messages": messages,
        "usage": usage,
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Session sil."""
    await session_manager.delete_session(session_id)
    return {"status": "deleted"}


# ============================================================
# Configuration
# ============================================================
@app.get("/api/config")
async def get_config():
    """Mevcut konfigürasyonu getir (hassas bilgiler gizlenir)."""
    return {
        "openai": {
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "api_key_set": bool(settings.openai_api_key and settings.openai_api_key.startswith("sk-")),
        },
        "confluence": {
            "base_url": settings.confluence_base_url,
            "email": settings.confluence_email,
            "api_token_set": bool(settings.confluence_api_token),
        },
        "database": {
            "url_set": bool(settings.database_url),
            "url_preview": settings.database_url.split("@")[-1] if "@" in settings.database_url else "configured",
        },
        "sync": {
            "interval_minutes": settings.sync_interval_minutes,
            "batch_size": settings.sync_batch_size,
        },
        "chunking": {
            "target_tokens": settings.chunk_target_tokens,
            "min_tokens": settings.chunk_min_tokens,
            "max_tokens": settings.chunk_max_tokens,
            "overlap_tokens": settings.chunk_overlap_tokens,
        },
        "search": {
            "top_k": settings.search_top_k,
            "max_pages": settings.search_max_pages,
        },
        "log_level": settings.log_level,
    }


# ============================================================
# Instructions / Settings
# ============================================================
@app.get("/api/instructions")
async def get_current_instructions():
    """Mevcut agent instructions'ı getir."""
    return {
        "current": get_instructions(),
        "default": DEFAULT_INSTRUCTIONS,
        "is_default": get_instructions() == DEFAULT_INSTRUCTIONS,
    }


@app.put("/api/instructions")
async def update_instructions(request: InstructionsRequest):
    """Agent instructions'ı güncelle."""
    set_instructions(request.instructions)
    return {
        "success": True,
        "message": "Instructions güncellendi",
    }


@app.post("/api/instructions/reset")
async def reset_to_default_instructions():
    """Default instructions'a dön."""
    reset_instructions()
    return {
        "success": True,
        "message": "Default instructions'a dönüldü",
    }


# ============================================================
# Conversation Starters
# ============================================================
@app.get("/api/starters")
async def get_conversation_starters():
    """Konu baslaticilari getir."""
    import json
    try:
        with get_db() as db:
            setting = db.query(AppSettings).filter(AppSettings.key == "conversation_starters").first()
            if setting and setting.value:
                starters = json.loads(setting.value)
                return {
                    "starters": starters,
                    "is_default": False,
                }
    except Exception as e:
        logger.error(f"Starters getirme hatası: {e}")

    return {
        "starters": DEFAULT_STARTERS,
        "is_default": True,
    }


@app.put("/api/starters")
async def update_conversation_starters(request: StartersRequest):
    """Konu baslaticilari guncelle."""
    import json
    try:
        with get_db() as db:
            setting = db.query(AppSettings).filter(AppSettings.key == "conversation_starters").first()
            if setting:
                setting.value = json.dumps([s.model_dump() for s in request.starters])
            else:
                setting = AppSettings(
                    key="conversation_starters",
                    value=json.dumps([s.model_dump() for s in request.starters])
                )
                db.add(setting)
            db.commit()

        return {"success": True, "message": "Starters guncellendi"}
    except Exception as e:
        logger.error(f"Starters guncelleme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/starters/reset")
async def reset_conversation_starters():
    """Default starters'a don."""
    try:
        with get_db() as db:
            db.query(AppSettings).filter(AppSettings.key == "conversation_starters").delete()
            db.commit()

        return {"success": True, "message": "Default starters'a donuldu"}
    except Exception as e:
        logger.error(f"Starters reset hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Database Viewer
# ============================================================
@app.get("/api/db/pages")
async def get_db_pages(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    space: Optional[str] = None,
    search: Optional[str] = None,
):
    try:
        with get_db() as db:
            query = db.query(Page)

            if space:
                query = query.filter(Page.space_key == space)

            if search:
                query = query.filter(Page.title.ilike(f"%{search}%"))

            total = query.count()
            pages = query.order_by(Page.updated_at.desc()).offset(offset).limit(limit).all()

            return {
                "total": total,
                "pages": [
                    {
                        "page_id": p.page_id,
                        "title": p.title,
                        "space_key": p.space_key,
                        "url": p.url,
                        "version": p.version,
                        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                        "synced_at": p.synced_at.isoformat() if p.synced_at else None,
                        "chunk_count": len(p.chunks) if p.chunks else 0,
                    }
                    for p in pages
                ]
            }
    except Exception as e:
        logger.error(f"DB pages hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/pages/{page_id}")
async def get_db_page_detail(page_id: str):
    try:
        with get_db() as db:
            page = db.query(Page).filter(Page.page_id == page_id).first()

            if not page:
                raise HTTPException(status_code=404, detail="Sayfa bulunamadı")

            chunks = [
                {
                    "chunk_id": str(c.chunk_id),
                    "chunk_index": c.chunk_index,
                    "heading_path": c.heading_path,
                    "text": c.text[:500] + "..." if len(c.text) > 500 else c.text,
                    "token_count": c.token_count,
                }
                for c in page.chunks
            ]

            return {
                "page_id": page.page_id,
                "title": page.title,
                "space_key": page.space_key,
                "url": page.url,
                "version": page.version,
                "body_text": page.body_text[:2000] + "..." if page.body_text and len(page.body_text) > 2000 else page.body_text,
                "updated_at": page.updated_at.isoformat() if page.updated_at else None,
                "synced_at": page.synced_at.isoformat() if page.synced_at else None,
                "chunks": chunks,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DB page detail hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/db/spaces")
async def get_db_spaces():
    try:
        with get_db() as db:
            from sqlalchemy import func
            spaces = db.query(
                Page.space_key,
                func.count(Page.page_id).label("page_count")
            ).group_by(Page.space_key).all()

            return {
                "spaces": [
                    {"space_key": s.space_key, "page_count": s.page_count}
                    for s in spaces
                ]
            }
    except Exception as e:
        logger.error(f"DB spaces hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Feedback
# ============================================================
@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Mesaj geri bildirimi kaydet."""
    if request.feedback not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="Feedback must be 'like' or 'dislike'")

    try:
        with get_db() as db:
            existing = db.query(MessageFeedback).filter(
                MessageFeedback.session_id == request.session_id,
                MessageFeedback.message_index == request.message_index,
            ).first()

            if existing:
                existing.feedback = request.feedback
                existing.comment = request.comment
            else:
                feedback = MessageFeedback(
                    session_id=request.session_id,
                    message_index=request.message_index,
                    feedback=request.feedback,
                    comment=request.comment,
                )
                db.add(feedback)

            db.commit()

        return {"success": True, "message": "Feedback kaydedildi"}
    except Exception as e:
        logger.error(f"Feedback hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/{session_id}")
async def get_session_feedback(session_id: str):
    """Session'a ait tum feedback'leri getir."""
    try:
        with get_db() as db:
            feedbacks = db.query(MessageFeedback).filter(
                MessageFeedback.session_id == session_id
            ).all()

            return {
                "feedbacks": {
                    f.message_index: f.feedback for f in feedbacks
                }
            }
    except Exception as e:
        logger.error(f"Feedback getirme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/feedback")
async def delete_feedback(session_id: str, message_index: int):
    """Feedback'i sil."""
    try:
        with get_db() as db:
            db.query(MessageFeedback).filter(
                MessageFeedback.session_id == session_id,
                MessageFeedback.message_index == message_index,
            ).delete()
            db.commit()

        return {"success": True, "message": "Feedback silindi"}
    except Exception as e:
        logger.error(f"Feedback silme hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Sync
# ============================================================
@app.post("/sync/run")
async def sync_run_endpoint(request: SyncRequest, background_tasks: BackgroundTasks):
    logger.info(f"Sync: mode={request.mode}")

    def run_sync():
        manager = SyncManager()
        if request.mode == "full":
            manager.run_full_sync()
        else:
            manager.run_incremental_sync()

    background_tasks.add_task(run_sync)

    return {
        "status": "started",
        "mode": request.mode,
    }


@app.get("/sync/status")
async def sync_status_endpoint():
    return get_sync_status()


# ============================================================
# Static Files / Frontend
# ============================================================
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


@app.get("/favicon.svg")
async def favicon():
    """Favicon serve et."""
    favicon_path = FRONTEND_DIR / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """React SPA catch-all route."""
    index_path = FRONTEND_DIR / "index.html"

    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

    # Frontend build yoksa basit bir hata sayfası göster
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Confluence Q&A</title>
            <style>
                body { font-family: system-ui; background: #0f0f0f; color: #fafafa; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .container { text-align: center; }
                h1 { color: #6366f1; }
                code { background: #1a1a1a; padding: 4px 8px; border-radius: 4px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Confluence Q&A</h1>
                <p>Frontend build bulunamadı.</p>
                <p>Lütfen <code>cd frontend && npm install && npm run build</code> komutunu çalıştırın.</p>
            </div>
        </body>
        </html>
        """,
        status_code=200
    )


# ============================================================
# Error Handler
# ============================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Hata: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
