import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.query import QueryRequest
from app.services.orchestrator import orchestrator
from app.services.rate_limit_service import (
    report_ip_rate_limiter,
    report_rate_limiter,
)
from app.services.security_service import session_service

router = APIRouter()


@router.post("/query")
async def query(payload: QueryRequest, request: Request) -> StreamingResponse:
    session_id, cookie_value, _ = session_service.resolve(
        request.cookies.get(session_service.cookie_name)
    )
    decision = report_rate_limiter.acquire(session_id)
    if not decision.allowed:
        raise HTTPException(
            status_code=429,
            detail="Report request limit reached. Please retry shortly.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )
    client_key = request.client.host if request.client else "unknown"
    ip_decision = report_ip_rate_limiter.acquire(client_key)
    if not ip_decision.allowed:
        report_rate_limiter.release(session_id)
        raise HTTPException(
            status_code=429,
            detail="Client request limit reached. Please retry shortly.",
            headers={"Retry-After": str(ip_decision.retry_after_seconds)},
        )

    async def event_stream():
        try:
            async for event in orchestrator.stream_report(
                query=payload.query,
                session_id=session_id,
            ):
                yield f"data: {json.dumps(event.model_dump(exclude_none=True))}\n\n"
        finally:
            report_rate_limiter.release(session_id)
            report_ip_rate_limiter.release(client_key)

    response = StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        session_service.cookie_name,
        cookie_value,
        **session_service.cookie_options(),
    )
    return response
