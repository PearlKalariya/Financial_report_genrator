from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    session_id: str = Field(default="demo-session", max_length=100)

