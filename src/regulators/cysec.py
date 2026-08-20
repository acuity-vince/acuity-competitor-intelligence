import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .models import RegulatoryRecord


CURRENT_URL = "https://www.cysec.gov.cy/en-GB/entities/investment-firms/cypriot/"
FORMER_URL = "https://www.cysec.gov.cy/en-GB/entities/investment-firms/former-investment-firms-cypriot/"
DOMAINS_URL = "https://www.cysec.gov.cy/en-GB/entities/investment-firms/approved-domains/"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split()).strip(" ;") or None


def _field(text: str, label: str) -> str | None:
    next_label = "|".join(re.escape(item) for item in (
        "Licence Number", "CySEC Registration Number", "Licence Date",
        "Company Registration Number", "Date of Termination", "Telephone",
        "Country", "E-Mail", "Approved Trade Names",
    ))
    pattern = rf"{re.escape(label)}\s*:\s*(.+?)(?=\s+(?:{next_label})\s*:|$)"
    match = re.search(pattern, text, re.I)
    return _clean(match.group(1)) if match else None


def _status(text: str, former: bool) -> tuple[str, str]:
    lower = text.lower()
    if "under examination for voluntary renunciation" in lower:
        return "SURRENDER_PENDING", "Under examination for voluntary renunciation"
    if "voluntary renunciation" in lower:
        return "VOLUNTARILY_CANCELLED", "Voluntary Renunciation"
    if "revoked" in lower:
        return "REVOKED", "Revoked"
    if "withdrawn" in lower:
        return "FORMERLY_AUTHORISED", "Withdrawn"
    return ("FORMERLY_AUTHORISED", "Former investment firm") if former else ("ACTIVE", "Current investment firm")


def _entity_blocks(html: str):
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    for marker in soup.find_all(string=re.compile(r"^(?:Licence Number|CySEC Registration Number)\s*:?(?:\s|$)", re.I)):
        node = marker.parent
        parents = list(node.parents)
        candidate = next((parent for parent in parents if "card-entities" in parent.get("class", [])), None)
        if candidate is None:
            candidate = next((parent for parent in parents if parent.name in {"article", "li", "tr"}), None)
        if candidate is None:
            candidate = next((parent for parent in parents if parent.name == "div" and
                              parent.find("a", class_="card-title") and
                              len(parent.get_text(" ", strip=True)) <= 1600), None)
        candidate = candidate or node.parent
        text = _clean(candidate.get_text(" ", strip=True)) or ""
        key = re.sub(r"\s+", " ", text)
        if key in seen:
            continue
        seen.add(key)
        link = candidate.find("a", class_="card-title") or candidate.find("a")
        name = _clean(link.get_text(" ", strip=True)) if link else None
        if name and re.search(r"Licence Number|CySEC Registration Number", text, re.I):
            yield name, text


def parse_firms(html: str, *, former: bool = False, source_url: str | None = None) -> list[RegulatoryRecord]:
    source_url = source_url or (FORMER_URL if former else CURRENT_URL)
    records = []
    for name, text in _entity_blocks(html):
        number = _field(text, "Licence Number") or _field(text, "CySEC Registration Number")
        if not number:
            continue
        number = re.split(r"\s*\(", number, maxsplit=1)[0].strip()
        normalized, source_status = _status(text, former)
        records.append(RegulatoryRecord(
            regulator_id="cysec",
            legal_name=name,
            license_number=number,
            normalized_status=normalized,
            source_status=source_status,
            source_url=source_url,
            company_number=_field(text, "Company Registration Number"),
            country="Cyprus",
            license_type="Cyprus Investment Firm",
            license_date=_field(text, "Licence Date"),
            termination_date=_field(text, "Date of Termination"),
        ))
    return records


def _normalize_domain(value: str) -> str | None:
    value = value.strip().strip(";,.")
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    return host or None


def parse_domains(html: str) -> dict[str, tuple[str, ...]]:
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3 or not cells[0].get_text(" ", strip=True).rstrip(".").isdigit():
            continue
        name = _clean(cells[1].get_text(" ", strip=True))
        raw = cells[2].get_text(" ", strip=True)
        domains = []
        for token in re.split(r"[;,\s]+", raw):
            domain = _normalize_domain(token)
            if domain and "." in domain:
                domains.append(domain)
        if name:
            result[name] = tuple(dict.fromkeys(domains))
    return result


def attach_domains(records: list[RegulatoryRecord], domains: dict[str, tuple[str, ...]]) -> list[RegulatoryRecord]:
    attached = []
    by_normalized = {re.sub(r"\W+", "", key).lower(): value for key, value in domains.items()}
    for record in records:
        key = re.sub(r"\W+", "", record.legal_name).lower()
        attached.append(RegulatoryRecord(**{**record.__dict__, "domains": by_normalized.get(key, ())}))
    return attached
