from fastapi import APIRouter

from app.memory.store import report_store

router = APIRouter()


@router.get("/history/{session_id}")
async def history(session_id: str) -> dict:
    return {"items": report_store.list_by_session(session_id)}

