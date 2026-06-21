from fastapi import APIRouter

from app.core.config import settings
from app.memory.store import report_store

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "backend": "fastapi",
        "workflow": "agent-mvp",
        "memory": "chromadb" if report_store.chroma_available else "persistent-json",
        "memory_path": settings.chroma_db_path,
        "providers": {
            "gemini": bool(settings.google_api_key),
            "tavily": bool(settings.tavily_api_key),
            "serper": bool(settings.serper_api_key),
            "alpha_vantage": bool(settings.alpha_vantage_api_key),
            "langfuse": bool(settings.langfuse_public_key and settings.langfuse_secret_key),
            "chromadb": report_store.chroma_available,
        },
    }
