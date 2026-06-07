from fastapi import APIRouter, Request, Response

from app.memory.store import report_store
from app.services.security_service import session_service

router = APIRouter()


@router.get("/history")
async def history(request: Request, response: Response) -> dict:
    session_id, cookie_value, created = session_service.resolve(
        request.cookies.get(session_service.cookie_name)
    )
    if created:
        response.set_cookie(
            session_service.cookie_name,
            cookie_value,
            **session_service.cookie_options(),
        )
    return {"items": report_store.list_by_session(session_id)}
