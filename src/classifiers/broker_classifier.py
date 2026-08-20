"""Evidence-led classifier for Acuity's FX/CFD/prop-firm target market."""

from __future__ import annotations

from dataclasses import dataclass
import re


POSITIVE_PATTERNS = {
    "forex": 6,
    "foreign exchange trading": 6,
    "currency pairs": 5,
    "fx trading": 5,
    "cfd trading": 6,
    "contracts for difference": 6,
    "trade cfds": 6,
    "metatrader": 5,
    "mt4": 4,
    "mt5": 4,
    "retail trading": 4,
    "trading account": 3,
    "spreads from": 3,
    "leverage": 2,
    "copy trading": 4,
    "funded trader": 6,
    "prop firm": 6,
    "proprietary trading": 4,
}

NEGATIVE_PATTERNS = {
    "wealth management": 5,
    "asset management": 5,
    "investment management": 4,
    "private banking": 6,
    "commercial bank": 7,
    "retail bank": 7,
    "corporate banking": 6,
    "fund administration": 6,
    "family office": 5,
    "insurance": 5,
    "corporate finance": 4,
}


@dataclass(frozen=True)
class BrokerClassification:
    forex_broker: str
    confidence: str
    reason: str
    needs_review: str


def _hits(text: str, patterns: dict[str, int]) -> list[tuple[str, int]]:
    lowered = re.sub(r"\s+", " ", text.lower())
    return [(term, weight) for term, weight in patterns.items() if term in lowered]


def classify_broker(legal_name: str, website_text: str = "") -> BrokerClassification:
    combined = f"{legal_name} {website_text}"
    positive = _hits(combined, POSITIVE_PATTERNS)
    negative = _hits(combined, NEGATIVE_PATTERNS)
    positive_score = sum(weight for _, weight in positive)
    negative_score = sum(weight for _, weight in negative)

    # Explicit product evidence outweighs a generic corporate descriptor.
    explicit_product = any(weight >= 5 for _, weight in _hits(website_text, POSITIVE_PATTERNS))
    strong_non_target = negative_score >= 5 and not explicit_product

    if re.search(r"\bbank\b", legal_name, flags=re.IGNORECASE) and not explicit_product:
        return BrokerClassification("NO", "HIGH", "Legal entity is identified as a bank", "NO")

    if explicit_product or positive_score >= 8:
        terms = ", ".join(term for term, _ in positive[:3])
        confidence = "HIGH" if positive_score >= 10 else "MEDIUM"
        return BrokerClassification("YES", confidence, f"FX/CFD/prop evidence: {terms}", "NO")
    if strong_non_target:
        terms = ", ".join(term for term, _ in negative[:3])
        return BrokerClassification("NO", "HIGH", f"Non-target business evidence: {terms}", "NO")
    if positive_score >= 4:
        terms = ", ".join(term for term, _ in positive[:3])
        return BrokerClassification("YES", "LOW", f"Possible trading evidence: {terms}", "YES")

    return BrokerClassification(
        "NO",
        "LOW",
        "No affirmative FX, CFD, or prop-trading product evidence found",
        "YES",
    )
