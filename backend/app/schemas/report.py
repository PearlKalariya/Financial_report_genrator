from pydantic import BaseModel


class Citation(BaseModel):
    title: str
    url: str
    source: str | None = None
    published_at: str | None = None


class ReportRecord(BaseModel):
    report_id: str
    session_id: str
    query: str
    ticker: str | None = None
    company: str | None = None
    report: str
    citations: list[Citation]
    created_at: str

