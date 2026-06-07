from app.agents.query_agent import run_query_agent


def test_query_agent_maps_icici_to_icici_bank() -> None:
    state = run_query_agent({"query": "what do you think about ICICI and its sentiment"})

    assert state["ticker"] == "ICICI.NS"
    assert state["company"] == "ICICI Bank"
    assert state["region"] == "India"


def test_query_agent_detects_sentiment_intent() -> None:
    state = run_query_agent({"query": "what do you think about ICICI and its sentiment"})

    assert state["intent"] == "sentiment_analysis"


def test_query_agent_asks_clarification_for_ambiguous_tata() -> None:
    state = run_query_agent({"query": "Analyze Tata."})

    assert state["needs_clarification"] is True
    assert state["ticker"] == "UNKNOWN"
    assert "Tata Motors" in state["clarification_options"]
    assert "Tata Steel" in state["clarification_options"]


def test_query_agent_maps_apple_to_aapl() -> None:
    state = run_query_agent({"query": "Analyze Apple."})

    assert state["ticker"] == "AAPL"
    assert state["company"] == "Apple"


def test_query_agent_handles_misspelled_infosys() -> None:
    state = run_query_agent({"query": "Analze Infosis"})

    assert state["ticker"] == "INFY.NS"
    assert state["company"] == "Infosys"


def test_query_agent_maps_meta_nickname() -> None:
    state = run_query_agent({"query": "What do you think about Meta?"})

    assert state["ticker"] == "META"
    assert state["company"] == "Meta Platforms"


def test_query_agent_extracts_multiple_comparison_entities() -> None:
    state = run_query_agent({"query": "Compare Apple, Tesla and Nvidia."})

    assert state["intent"] == "comparison"
    assert state["ticker"] == "AAPL"
    assert state["entities"] == [
        {"ticker": "AAPL", "company": "Apple", "region": "United States"},
        {"ticker": "TSLA", "company": "Tesla", "region": "United States"},
        {"ticker": "NVDA", "company": "NVIDIA", "region": "United States"},
    ]


def test_query_agent_does_not_clarify_when_tata_motors_is_explicit() -> None:
    state = run_query_agent({"query": "Compare Reliance, Adani Ports, and Tata Motors."})

    assert state["needs_clarification"] is False
    assert state["intent"] == "comparison"
    assert state["entities"] == [
        {"ticker": "RELIANCE.NS", "company": "Reliance Industries", "region": "India"},
        {
            "ticker": "ADANIPORTS.NS",
            "company": "Adani Ports and Special Economic Zone",
            "region": "India",
        },
        {"ticker": "TATAMOTORS.NS", "company": "Tata Motors", "region": "India"},
    ]


def test_query_agent_extracts_meta_google_amazon_comparison() -> None:
    state = run_query_agent({"query": "Compare meta, google and amazon."})

    assert state["intent"] == "comparison"
    assert state["ticker"] == "META"
    assert state["entities"] == [
        {"ticker": "META", "company": "Meta Platforms", "region": "United States"},
        {"ticker": "GOOGL", "company": "Alphabet", "region": "United States"},
        {"ticker": "AMZN", "company": "Amazon", "region": "United States"},
    ]


def test_query_agent_asks_clarification_for_ambiguous_adani_group() -> None:
    state = run_query_agent({"query": "generate me financial report on profit and loss of adani"})

    assert state["needs_clarification"] is True
    assert state["ticker"] == "UNKNOWN"
    assert state["intent"] == "financial_statement_analysis"
    assert "Adani Enterprises" in state["clarification_options"]
    assert "Adani Ports and Special Economic Zone" in state["clarification_options"]


def test_query_agent_does_not_clarify_when_adani_ports_is_explicit() -> None:
    state = run_query_agent({"query": "generate profit and loss report for Adani Ports"})

    assert state["needs_clarification"] is False
    assert state["intent"] == "financial_statement_analysis"
    assert state["ticker"] == "ADANIPORTS.NS"
    assert state["company"] == "Adani Ports and Special Economic Zone"


def test_query_agent_detects_indian_market_geopolitical_impact() -> None:
    state = run_query_agent(
        {"query": "What affect does Iran Israel war have on Indian stock market?"}
    )

    assert state["intent"] == "macro_market_impact"
    assert state["ticker"] == "^NSEI"
    assert state["company"] == "Indian Stock Market"
    assert state["region"] == "India"
    assert state["entities"] == [
        {
            "ticker": "^NSEI",
            "company": "Indian Stock Market",
            "region": "India",
        }
    ]
