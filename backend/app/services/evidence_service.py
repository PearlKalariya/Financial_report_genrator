import re
from datetime import UTC, datetime
from urllib.parse import urlparse


METRIC_ALIASES = {
    "revenue": ["revenue", "total income", "sales"],
    "ebitda": ["ebitda", "operating profit"],
    "net_profit": ["net profit", "profit after tax", "pat", "net income"],
    "expenses": ["total expenses", "operating expenses", "expenses"],
    "eps": ["earnings per share", "eps"],
    "operating_margin": ["operating margin"],
    "ebitda_margin": ["ebitda margin"],
    "net_profit_margin": ["net profit margin", "pat margin"],
}

REQUIRED_FINANCIAL_METRICS = [
    "revenue",
    "ebitda",
    "net_profit",
    "expenses",
    "eps",
    "operating_margin",
    "ebitda_margin",
]


class FinancialEvidenceService:
    def rank_sources(self, articles: list[dict], *, company: str) -> list[dict]:
        ranked = []
        for index, article in enumerate(articles):
            tier, score = self._source_quality(article, company=company)
            ranked.append(
                {
                    **article,
                    "source_tier": tier,
                    "source_score": score,
                    "_original_order": index,
                }
            )

        ranked.sort(key=lambda item: (-item["source_score"], item["_original_order"]))
        return [
            {key: value for key, value in article.items() if key != "_original_order"}
            for article in ranked
        ]

    def build_evidence(
        self,
        *,
        company: str,
        ticker: str,
        articles: list[dict],
        market_data: dict,
    ) -> dict:
        ranked_articles = self.rank_sources(articles, company=company)
        sources = [
            {
                "source_id": f"S{index}",
                "title": article.get("title", "Untitled source"),
                "url": article.get("url", ""),
                "publisher": article.get("source", "Unknown"),
                "published_at": article.get("published_at", "Unknown"),
                "tier": article.get("source_tier", "general_web"),
                "score": article.get("source_score", 10),
            }
            for index, article in enumerate(ranked_articles, start=1)
        ]

        facts = []
        seen = set()
        source_observations = []
        seen_observations = set()
        for index, article in enumerate(ranked_articles, start=1):
            source_id = f"S{index}"
            text = " ".join(
                value
                for value in [article.get("title", ""), article.get("snippet", "")]
                if value
            )
            period = self._extract_period(text)
            for fact in self._extract_facts(text):
                identity = (
                    fact["metric"],
                    fact["value"],
                    fact.get("unit"),
                    period,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                facts.append(
                    {
                        "fact_id": f"F{len(facts) + 1}",
                        **fact,
                        "period": period,
                        "source_id": source_id,
                        "source_url": article.get("url", ""),
                        "source_title": article.get("title", "Untitled source"),
                        "source_tier": article.get("source_tier", "general_web"),
                        "confidence": self._fact_confidence(article),
                    }
                )

            fact_texts = {
                self._normalize_evidence_text(fact.get("raw_text", ""))
                for fact in facts
                if fact.get("source_id") == source_id
            }
            observation_texts = []
            for source_text in [article.get("title", ""), article.get("snippet", "")]:
                observation_texts.extend(self._extract_numeric_observations(source_text))
            for observation_text in observation_texts:
                normalized = self._normalize_evidence_text(observation_text)
                if not normalized or normalized in seen_observations:
                    continue
                if any(fact_text and fact_text in normalized for fact_text in fact_texts):
                    continue
                seen_observations.add(normalized)
                source_observations.append(
                    {
                        "observation_id": f"O{len(source_observations) + 1}",
                        "source_id": source_id,
                        "text": observation_text,
                        "classification": "unclassified_numeric_evidence",
                        "source_url": article.get("url", ""),
                        "source_title": article.get("title", "Untitled source"),
                        "period": period,
                        "confidence": self._fact_confidence(article),
                    }
                )

        metric_status = {
            metric: "verified" if any(fact["metric"] == metric for fact in facts) else "unavailable"
            for metric in REQUIRED_FINANCIAL_METRICS
        }
        verified_count = sum(status == "verified" for status in metric_status.values())
        official_count = sum(
            source["tier"] in {"exchange_filing", "company_official"}
            for source in sources
        )
        confidence_score = min(
            1.0,
            (verified_count / len(REQUIRED_FINANCIAL_METRICS)) * 0.7
            + min(official_count, 2) * 0.15,
        )

        return {
            "company": company,
            "ticker": ticker,
            "facts": facts,
            "source_observations": source_observations,
            "sources": sources,
            "metric_status": metric_status,
            "confidence": {
                "score": round(confidence_score, 2),
                "level": self._confidence_level(confidence_score),
                "verified_metrics": verified_count,
                "required_metrics": len(REQUIRED_FINANCIAL_METRICS),
                "official_sources": official_count,
            },
            "freshness": {
                "market_data_as_of": self._format_market_time(market_data.get("market_time")),
                "latest_source_date": self._latest_source_date(sources),
                "warning": self._freshness_warning(sources),
            },
        }

    def _source_quality(self, article: dict, *, company: str) -> tuple[str, int]:
        url = article.get("url", "").lower()
        source = article.get("source", "").lower()
        host = urlparse(url).netloc.removeprefix("www.")
        host_token = re.sub(r"[^a-z0-9]", "", host)
        company_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", company.lower())
            if len(token) >= 4
            and token
            not in {
                "company",
                "corporation",
                "incorporated",
                "limited",
                "holdings",
                "industries",
            }
        ]

        if any(domain in host for domain in ["nseindia.com", "bseindia.com", "sec.gov"]):
            return "exchange_filing", 100
        if any(token in host_token for token in company_tokens):
            return "company_official", 90
        if any(
            domain in host
            for domain in [
                "reuters.com",
                "bloomberg.com",
                "ft.com",
                "wsj.com",
                "moneycontrol.com",
                "economictimes.indiatimes.com",
            ]
        ):
            return "reputable_financial_news", 70
        if any(
            domain in host
            for domain in [
                "finance.yahoo.com",
                "google.com",
                "screener.in",
                "marketscreener.com",
                "trendlyne.com",
                "tijorifinance.com",
                "investing.com",
                "stockanalysis.com",
            ]
        ) or source in {"yahoo finance", "google finance"}:
            return "financial_aggregator", 40
        return "general_web", 20

    def _extract_facts(self, text: str) -> list[dict]:
        facts = []
        for metric, aliases in METRIC_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                pattern = re.compile(
                    rf"\b{re.escape(alias)}\b"
                    r"(?:\s+(?:was|were|stood at|is|of|at|reached|rose to|fell to|reported at))?"
                    r"\s*[:\-]?\s*"
                    r"(?P<currency>INR|USD|EUR|GBP|₹|Rs\.?|US\$|\$)?\s*"
                    r"(?P<value>-?\d[\d,]*(?:\.\d+)?)\s*"
                    r"(?P<unit>%|crore|cr|lakh|million|billion|trillion|mn|bn)?",
                    re.IGNORECASE,
                )
                match = pattern.search(text)
                if not match:
                    continue

                unit = self._normalize_unit(match.group("unit"))
                currency = self._normalize_currency(match.group("currency"))
                if unit == "%" and not metric.endswith("margin"):
                    continue
                facts.append(
                    {
                        "metric": metric,
                        "value": match.group("value"),
                        "currency": currency,
                        "unit": unit,
                        "raw_text": match.group(0).strip(),
                    }
                )
                break
        return facts

    def _extract_numeric_observations(self, text: str) -> list[str]:
        numeric_pattern = re.compile(
            r"(?:INR|USD|EUR|GBP|₹|Rs\.?|US\$|\$)\s*-?\d[\d,]*(?:\.\d+)?"
            r"(?:\s*(?:%|crore|cr|lakh|million|billion|trillion|mn|bn))?"
            r"|-?\d[\d,]*(?:\.\d+)?\s*(?:%|crore|cr|lakh|million|billion|trillion|mn|bn)",
            re.IGNORECASE,
        )
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [
            sentence.strip()
            for sentence in sentences
            if sentence.strip() and numeric_pattern.search(sentence)
        ]

    def _normalize_evidence_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    def _extract_period(self, text: str) -> str:
        patterns = [
            r"\bQ[1-4]\s*(?:FY)?\s*\d{2,4}\b",
            r"\bFY\s*\d{2,4}\b",
            r"\b(?:quarter|year)\s+ended\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", " ", match.group(0)).upper()
        return "Unspecified"

    def _normalize_currency(self, currency: str | None) -> str | None:
        if not currency:
            return None
        value = currency.upper().replace(".", "")
        if value in {"₹", "RS", "INR"}:
            return "INR"
        if value in {"$", "US$", "USD"}:
            return "USD"
        return value

    def _normalize_unit(self, unit: str | None) -> str | None:
        if not unit:
            return None
        value = unit.lower()
        return {
            "cr": "crore",
            "mn": "million",
            "bn": "billion",
        }.get(value, value)

    def _fact_confidence(self, article: dict) -> str:
        score = article.get("source_score", 20)
        if score >= 90:
            return "high"
        if score >= 70:
            return "medium"
        return "low"

    def _confidence_level(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    def _format_market_time(self, value) -> str:
        if not isinstance(value, (int, float)):
            return "Unavailable"
        return datetime.fromtimestamp(value, tz=UTC).isoformat()

    def _latest_source_date(self, sources: list[dict]) -> str:
        dates = [
            source["published_at"]
            for source in sources
            if source.get("published_at") not in {None, "", "Latest", "Unknown"}
        ]
        return max(dates) if dates else "Unavailable"

    def _freshness_warning(self, sources: list[dict]) -> str | None:
        if not sources:
            return "No research sources were retrieved."
        if all(source["published_at"] in {"Latest", "Unknown", None, ""} for source in sources):
            return "Source publication dates are unavailable."
        return None


financial_evidence_service = FinancialEvidenceService()
