"""Build normalized BrokerChooser inventories from isolated Firecrawl output."""

from __future__ import annotations

import csv
import html
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / ".firecrawl"
OUTPUT_DIR = ROOT / "data" / "sources"
REVIEW_MAPS = (
    RAW_DIR / "brokerchooser-sitemap-map.json",
    RAW_DIR / "brokerchooser-broker-reviews-map.json",
    RAW_DIR / "brokerchooser-forex-map.json",
)
SAFETY_MAP = RAW_DIR / "brokerchooser-safety-map.json"
NOT_RECOMMENDED = RAW_DIR / "brokerchooser-not-recommended.md"

REVIEW_URL_RE = re.compile(
    r"https://brokerchooser\.com/(?:[a-z]{2}/)?broker-reviews/"
    r"([a-z0-9-]+-review)/?",
    re.IGNORECASE,
)
SAFETY_URL_RE = re.compile(
    r"https://brokerchooser\.com/(?:[a-z]{2}/)?safety/"
    r"([a-z0-9-]+)-broker-safe-or-scam/?",
    re.IGNORECASE,
)


def clean_markdown(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<br\s*/?>", " | ", value, flags=re.IGNORECASE)
    value = re.sub(r"!\[[^]]*]\([^)]*\)", "", value)
    value = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", value)
    value = value.replace("**", "").replace("__", "")
    return re.sub(r"\s+", " ", value).strip(" |")


def display_name(slug: str) -> str:
    stem = re.sub(r"-review$", "", slug, flags=re.IGNORECASE)
    return " ".join(word.upper() if word in {"fx", "cfd", "ig", "xm"} else word.title() for word in stem.split("-"))


def canonical_review_urls() -> dict[str, str]:
    urls: dict[str, str] = {}
    for path in REVIEW_MAPS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for slug in REVIEW_URL_RE.findall(text):
            slug = slug.lower()
            urls[slug] = f"https://brokerchooser.com/broker-reviews/{slug}"
    return urls


def product_flag(text: str, product: str) -> tuple[str, str, str]:
    row_pattern = rf"^\|\s*{product}(?:<br>.*?)?\|\s*(Yes|No)\s*\|"
    row = re.search(row_pattern, text, re.IGNORECASE | re.MULTILINE)
    if row:
        flag = row.group(1).upper()
        return flag, "HIGH", f"BrokerChooser product table says {product.lower()} availability is {flag}."

    if product.lower() == "forex":
        pairs = re.search(
            r"^\|\s*Currency pairs \(#\).*?\|\s*([0-9][0-9,]*)\s*\|",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        if pairs and int(pairs.group(1).replace(",", "")) > 0:
            return "YES", "HIGH", f"BrokerChooser lists {pairs.group(1)} currency pairs."
        if re.search(r"Recommended for:[^\n]{0,160}\bforex\b", text, re.IGNORECASE):
            return "YES", "MEDIUM", "BrokerChooser recommends the broker for forex traders."
        if re.search(r"\boffers?\b[^.\n]{0,100}\bforex\b", text, re.IGNORECASE):
            return "YES", "MEDIUM", "BrokerChooser text states that forex is offered."
    else:
        if re.search(r"Recommended for:[^\n]{0,160}\bCFD", text, re.IGNORECASE):
            return "YES", "MEDIUM", "BrokerChooser recommends the broker for CFD traders."

    return "UNKNOWN", "LOW", f"No conclusive {product.lower()} availability field was extracted."


def parse_regulatory_table(text: str) -> tuple[list[str], list[str], list[str]]:
    regulators: set[str] = set()
    legal_entities: set[str] = set()
    jurisdictions: set[str] = set()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        header = [clean_markdown(cell).lower() for cell in line.strip().strip("|").split("|")]
        regulator_indexes = [i for i, value in enumerate(header) if value == "regulator"]
        entity_indexes = [i for i, value in enumerate(header) if value == "legal entity"]
        if not regulator_indexes or not entity_indexes:
            continue
        regulator_index = regulator_indexes[0]
        entity_index = entity_indexes[0]
        jurisdiction_index = next(
            (i for i, value in enumerate(header) if "client" in value or value == "country"),
            None,
        )
        for row in lines[index + 2 :]:
            if not row.startswith("|"):
                break
            cells = [clean_markdown(cell) for cell in row.strip().strip("|").split("|")]
            if len(cells) <= max(regulator_index, entity_index):
                continue
            if jurisdiction_index is not None and len(cells) > jurisdiction_index and cells[jurisdiction_index]:
                jurisdictions.add(cells[jurisdiction_index])
            if cells[regulator_index]:
                regulators.update(part.strip() for part in cells[regulator_index].split(" | ") if part.strip())
            if cells[entity_index]:
                legal_entities.update(part.strip() for part in cells[entity_index].split(" | ") if part.strip())
    return sorted(regulators), sorted(legal_entities), sorted(jurisdictions)


def parse_review(slug: str, url: str, checked_at: str) -> dict[str, str]:
    path = RAW_DIR / f"brokerchooser.com-broker-reviews-{slug}.md"
    if not path.exists():
        return {
            "broker_name": display_name(slug),
            "review_slug": slug,
            "review_url": url,
            "scrape_status": "SCRAPE_FAILED",
            "forex_broker": "UNKNOWN",
            "offers_cfds": "UNKNOWN",
            "classification_confidence": "LOW",
            "classification_reason": "Review URL was discovered, but the page scrape failed.",
            "regulators": "",
            "legal_entities": "",
            "jurisdictions": "",
            "source_category": "FULL_REVIEW",
            "needs_review": "YES",
            "last_checked": checked_at,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    title = re.search(r"^#\s+(.+?)\s+Review(?:\s+\d{4})?\s*$", text, re.IGNORECASE | re.MULTILINE)
    name = clean_markdown(title.group(1)) if title else display_name(slug)
    forex, forex_confidence, forex_reason = product_flag(text, "Forex")
    cfds, cfd_confidence, _ = product_flag(text, "CFDs?")
    regulators, legal_entities, jurisdictions = parse_regulatory_table(text)
    confidence = "HIGH" if "HIGH" in {forex_confidence, cfd_confidence} else forex_confidence
    return {
        "broker_name": name,
        "review_slug": slug,
        "review_url": url,
        "scrape_status": "SCRAPED",
        "forex_broker": forex,
        "offers_cfds": cfds,
        "classification_confidence": confidence,
        "classification_reason": forex_reason,
        "regulators": " | ".join(regulators),
        "legal_entities": " | ".join(legal_entities),
        "jurisdictions": " | ".join(jurisdictions),
        "source_category": "FULL_REVIEW",
        "needs_review": "NO" if forex in {"YES", "NO"} and regulators else "YES",
        "last_checked": checked_at,
    }


def write_review_inventory(checked_at: str) -> list[dict[str, str]]:
    rows = [parse_review(slug, url, checked_at) for slug, url in sorted(canonical_review_urls().items())]
    path = OUTPUT_DIR / "brokerchooser-reviewed-brokers.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_safety_inventory(checked_at: str) -> list[dict[str, str]]:
    text = SAFETY_MAP.read_text(encoding="utf-8", errors="replace")
    slugs = sorted({slug.lower() for slug in SAFETY_URL_RE.findall(text)})
    rows = [
        {
            "broker_name_unverified": display_name(slug),
            "profile_slug": slug,
            "profile_url": f"https://brokerchooser.com/safety/{slug}-broker-safe-or-scam",
            "source_category": "SAFETY_PROFILE",
            "sales_target": "UNKNOWN",
            "needs_review": "YES",
            "last_checked": checked_at,
        }
        for slug in slugs
    ]
    path = OUTPUT_DIR / "brokerchooser-safety-inventory.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_not_recommended(checked_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in NOT_RECOMMENDED.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("|") or "Broker's name" in line or re.match(r"^\|\s*-+", line):
            continue
        cells = [clean_markdown(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[0] or cells[0].lower() in seen:
            continue
        seen.add(cells[0].lower())
        link = re.search(r"https?://[^)\s]+", line)
        rows.append(
            {
                "broker_name": cells[0],
                "reason": cells[1],
                "review_url": link.group(0) if link else "",
                "source_category": "NOT_RECOMMENDED",
                "sales_target": "NO",
                "needs_review": "YES",
                "last_checked": checked_at,
            }
        )
    path = OUTPUT_DIR / "brokerchooser-not-recommended.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    reviews = write_review_inventory(checked_at)
    safety = write_safety_inventory(checked_at)
    not_recommended = write_not_recommended(checked_at)
    forex_yes = sum(row["forex_broker"] == "YES" for row in reviews)
    failed = sum(row["scrape_status"] == "SCRAPE_FAILED" for row in reviews)
    print(f"reviewed={len(reviews)} forex_yes={forex_yes} scrape_failed={failed}")
    print(f"safety_profiles={len(safety)} not_recommended={len(not_recommended)}")


if __name__ == "__main__":
    main()
