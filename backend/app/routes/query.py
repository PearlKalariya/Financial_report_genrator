import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.query import QueryRequest
from app.services.orchestrator import orchestrator

router = APIRouter()


@router.post("/query")
async def query(request: QueryRequest) -> StreamingResponse:
    async def event_stream():
        async for event in orchestrator.stream_report(
            query=request.query,
            session_id=request.session_id,
        ):
            yield f"data: {json.dumps(event.model_dump(exclude_none=True))}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

