from pathlib import Path

from app.memory.store import PersistentReportStore


def test_chroma_store_persists_reports_and_preserves_history_api(tmp_path: Path) -> None:
    store = PersistentReportStore(storage_path=tmp_path, enable_chroma=True)

    record = store.add(
        session_id="session-1",
        query="What is the outlook for TCS?",
        ticker="TCS.NS",
        company="Tata Consultancy Services",
        report="TCS report about Indian IT services demand.",
        citations=[],
    )

    reloaded = PersistentReportStore(storage_path=tmp_path, enable_chroma=True)
    history = reloaded.list_by_session("session-1")

    assert record.report_id
    assert reloaded.collection_name == "financial_reports"
    assert reloaded.chroma_available is True
    assert history[0].report_id == record.report_id
    assert history[0].report == "TCS report about Indian IT services demand."


def test_find_related_prioritizes_same_ticker_before_semantic_matches(tmp_path: Path) -> None:
    store = PersistentReportStore(storage_path=tmp_path, enable_chroma=True)
    store.add(
        session_id="session-1",
        query="Apple iPhone revenue outlook",
        ticker="AAPL",
        company="Apple",
        report="Apple report about iPhone revenue and services.",
        citations=[],
    )
    store.add(
        session_id="session-1",
        query="Meta advertising outlook",
        ticker="META",
        company="Meta Platforms",
        report="Meta report about advertising revenue.",
        citations=[],
    )

    related = store.find_related(
        session_id="session-1",
        ticker="AAPL",
        query="iPhone services revenue",
        limit=2,
    )

    assert related[0]["ticker"] == "AAPL"
    assert related[0]["match_type"] == "ticker"
    assert related[1]["match_type"] == "semantic"


def test_find_related_is_session_isolated(tmp_path: Path) -> None:
    store = PersistentReportStore(storage_path=tmp_path, enable_chroma=True)
    store.add(
        session_id="session-1",
        query="Apple",
        ticker="AAPL",
        company="Apple",
        report="Private Apple report.",
        citations=[],
    )

    related = store.find_related(
        session_id="session-2",
        ticker="AAPL",
        query="Apple",
        limit=3,
    )

    assert related == []


def test_existing_json_history_is_indexed_into_chroma_on_startup(tmp_path: Path) -> None:
    json_only_store = PersistentReportStore(storage_path=tmp_path, enable_chroma=False)
    record = json_only_store.add(
        session_id="session-1",
        query="Apple services outlook",
        ticker="AAPL",
        company="Apple",
        report="Apple services revenue has recurring subscription drivers.",
        citations=[],
    )

    chroma_store = PersistentReportStore(storage_path=tmp_path, enable_chroma=True)

    assert chroma_store.chroma_available is True
    assert chroma_store._collection.count() == 1
    related = chroma_store.find_related(
        session_id="session-1",
        ticker="MSFT",
        query="subscription services revenue",
        limit=1,
    )
    assert related[0]["report_id"] == record.report_id
    assert related[0]["match_type"] == "semantic"
