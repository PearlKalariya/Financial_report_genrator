import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.schemas.report import Citation, ReportRecord


class PersistentReportStore:
    def __init__(self, *, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path or settings.chroma_db_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_path / "financial_reports.json"
        self._lock = threading.RLock()

    def add(
        self,
        *,
        session_id: str,
        query: str,
        ticker: str | None,
        company: str | None,
        report: str,
        citations: list[dict],
    ) -> ReportRecord:
        record = ReportRecord(
            report_id=str(uuid4()),
            session_id=session_id,
            query=query,
            ticker=ticker,
            company=company,
            report=report,
            citations=[Citation(**citation) for citation in citations],
            created_at=datetime.now(UTC).isoformat(),
        )

        with self._lock:
            records = self._read_all()
            records.append(record)
            self._write_all(records)
        return record

    def list_by_session(self, session_id: str) -> list[ReportRecord]:
        with self._lock:
            return [
                record
                for record in self._read_all()
                if record.session_id == session_id
            ]

    def find_related(self, *, session_id: str, ticker: str | None, limit: int) -> list[dict]:
        with self._lock:
            matches = [
                record
                for record in self._read_all()
                if record.session_id == session_id
                and (ticker is None or record.ticker == ticker)
            ]
        return [
            {
                "report_id": record.report_id,
                "query": record.query,
                "ticker": record.ticker,
                "company": record.company,
                "created_at": record.created_at,
            }
            for record in matches[-limit:]
        ]

    def _read_all(self) -> list[ReportRecord]:
        if not self.history_file.exists():
            return []

        try:
            payload = json.loads(self.history_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        return [ReportRecord(**item) for item in payload]

    def _write_all(self, records: list[ReportRecord]) -> None:
        payload = [record.model_dump(mode="json") for record in records]
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path,
                prefix=".financial_reports-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(payload, temporary_file, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)
            temporary_path.replace(self.history_file)
        finally:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink()


report_store = PersistentReportStore()
