"""Enrich the CySEC registry CSV with auditable Acuity target classifications."""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
import httpx

from src.classifiers.broker_classifier import classify_broker


async def fetch_homepage(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, domain: str) -> tuple[str, str, str]:
    domain = domain.strip().split(";")[0].strip().strip("/")
    if not domain:
        return "", "", "NO_APPROVED_DOMAIN"
    async with semaphore:
        for scheme in ("https://", "http://"):
            url = scheme + domain
            try:
                response = await client.get(url)
                if response.status_code < 400 and "html" in response.headers.get("content-type", ""):
                    soup = BeautifulSoup(response.text, "html.parser")
                    for node in soup(["script", "style", "noscript", "svg"]):
                        node.decompose()
                    return " ".join(soup.stripped_strings)[:100_000], str(response.url), "FETCHED"
            except Exception:
                continue
    return "", url, "FETCH_FAILED"


async def run(input_csv: Path, output_csv: Path) -> None:
    with input_csv.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
        fields = list(rows[0]) + [
            "forex_broker",
            "classification_confidence",
            "classification_reason",
            "evidence_url",
            "evidence_status",
            "needs_review",
        ]

    domains = sorted({row.get("approved_domains", "").split(";")[0].strip() for row in rows})
    limits = httpx.Limits(max_connections=12, max_keepalive_connections=6)
    async with httpx.AsyncClient(
        headers={"User-Agent": "AcuityCompetitorResearch/1.0"},
        follow_redirects=True,
        timeout=8,
        limits=limits,
    ) as client:
        semaphore = asyncio.Semaphore(12)
        results = await asyncio.gather(
            *(fetch_homepage(client, semaphore, domain) for domain in domains)
        )
    cache = dict(zip(domains, results))

    for index, row in enumerate(rows, 1):
        domain = row.get("approved_domains", "").split(";")[0].strip()
        text, evidence_url, evidence_status = cache[domain]
        result = classify_broker(row["legal_name"], text)
        row.update(
            forex_broker=result.forex_broker,
            classification_confidence=result.confidence,
            classification_reason=result.reason,
            evidence_url=evidence_url,
            evidence_status=evidence_status,
            needs_review=result.needs_review,
        )
        if index % 25 == 0:
            print(f"Classified {index}/{len(rows)}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.input_csv, args.output_csv))


if __name__ == "__main__":
    main()
