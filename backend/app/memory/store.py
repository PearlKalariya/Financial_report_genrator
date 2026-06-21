import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from hashlib import blake2b
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.report import Citation, ReportRecord


EMBEDDING_DIMENSIONS = 64


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        return vector

    for token in tokens:
        digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


class PersistentReportStore:
    collection_name = "financial_reports"

    def __init__(
        self,
        *,
        storage_path: str | Path | None = None,
        enable_chroma: bool = True,
    ) -> None:
        self.storage_path = Path(storage_path or settings.chroma_db_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_path / "financial_reports.json"
        self._lock = threading.RLock()
        self.chroma_available = False
        self._collection = None
        if enable_chroma:
            self._initialize_chroma()
            self._backfill_chroma_from_history()

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
            self._upsert_chroma(record)
        return record

    def list_by_session(self, session_id: str) -> list[ReportRecord]:
        with self._lock:
            return [
                record
                for record in self._read_all()
                if record.session_id == session_id
            ]

    def find_related(
        self,
        *,
        session_id: str,
        ticker: str | None,
        limit: int,
        query: str | None = None,
    ) -> list[dict]:
        with self._lock:
            exact_matches = [
                record
                for record in self._read_all()
                if record.session_id == session_id
                and (ticker is None or record.ticker == ticker)
            ]
            related = [
                self._memory_item(record, match_type="ticker")
                for record in exact_matches[-limit:]
            ]
            if len(related) < limit:
                related.extend(
                    self._semantic_matches(
                        session_id=session_id,
                        query=query,
                        exclude_report_ids={
                            item["report_id"] for item in related
                        },
                        limit=limit - len(related),
                    )
                )
            return related[:limit]

    def _initialize_chroma(self) -> None:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(self.storage_path))
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self.chroma_available = True
        # Chroma's Rust layer can raise pyo3 panics that do not inherit Exception.
        except BaseException:
            self._collection = None
            self.chroma_available = False

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

    def _upsert_chroma(self, record: ReportRecord) -> None:
        if not self._collection:
            return
        try:
            document = self._document_text(record)
            self._collection.upsert(
                ids=[record.report_id],
                documents=[document],
                metadatas=[self._metadata(record)],
                embeddings=[embed_text(document)],
            )
        # Keep JSON history usable if Chroma rejects a record or store version.
        except BaseException:
            self.chroma_available = False

    def _backfill_chroma_from_history(self) -> None:
        if not self._collection:
            return
        try:
            for record in self._read_all():
                self._upsert_chroma(record)
        # Keep startup healthy even if a persisted Chroma index is incompatible.
        except BaseException:
            self.chroma_available = False

    def _semantic_matches(
        self,
        *,
        session_id: str,
        query: str | None,
        exclude_report_ids: set[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        if not self._collection or not query or limit <= 0:
            return []
        try:
            results = self._collection.query(
                query_embeddings=[embed_text(query)],
                n_results=max(limit + len(exclude_report_ids), limit),
                where={"session_id": session_id},
                include=["documents", "metadatas", "distances"],
            )
        # Chroma's Rust layer can raise pyo3 panics that do not inherit Exception.
        except BaseException:
            self.chroma_available = False
            return []

        matches = []
        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for report_id, metadata, distance in zip(ids, metadatas, distances, strict=False):
            if report_id in exclude_report_ids:
                continue
            matches.append(
                {
                    "report_id": report_id,
                    "query": metadata.get("query", ""),
                    "ticker": metadata.get("ticker") or None,
                    "company": metadata.get("company") or None,
                    "created_at": metadata.get("created_at", ""),
                    "match_type": "semantic",
                    "distance": distance,
                }
            )
            if len(matches) == limit:
                break
        return matches

    def _document_text(self, record: ReportRecord) -> str:
        return "\n".join(
            [
                record.query,
                record.ticker or "",
                record.company or "",
                record.report,
            ]
        )

    def _metadata(self, record: ReportRecord) -> dict[str, str]:
        return {
            "report_id": record.report_id,
            "session_id": record.session_id,
            "ticker": record.ticker or "",
            "company": record.company or "",
            "query": record.query,
            "created_at": record.created_at,
        }

    def _memory_item(self, record: ReportRecord, *, match_type: str) -> dict:
        return {
            "report_id": record.report_id,
            "query": record.query,
            "ticker": record.ticker,
            "company": record.company,
            "created_at": record.created_at,
            "match_type": match_type,
        }


report_store = PersistentReportStore()
