"""Find active FCA counterparts for strong candidates in the master registry."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.regulators.fca import FCAClient, FCASearchResult  # noqa: E402


FCA_REGISTER = "https://register.fca.org.uk/"
FCA_API_SOURCE = "https://register.fca.org.uk/Developer/s/"
ACTIVE_STATUS = {"authorised"}


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def clean_display_name(value: str) -> str:
    return re.sub(r"\s*\(Postcode:.*?\)\s*$", "", value, flags=re.IGNORECASE).strip()


def normalize_name(value: str) -> str:
    value = clean_display_name(value).casefold().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = ["ltd" if token == "limited" else token for token in value.split()]
    return " ".join(tokens)


def match_score(candidate_name: str, result_name: str) -> float:
    candidate = normalize_name(candidate_name)
    result = normalize_name(result_name)
    if not candidate or not result:
        return 0.0
    if candidate == result:
        return 1.0
    return SequenceMatcher(None, candidate, result).ratio()


def is_active_firm(result: FCASearchResult) -> bool:
    return (
        result.status.strip().casefold() in ACTIVE_STATUS
        and bool(result.frn)
        and "firm" in result.result_type.casefold()
    )


def evidence_url(result: FCASearchResult) -> str:
    value = str(result.raw.get("URL") or "").strip()
    return urljoin(FCA_REGISTER, value) if value else FCA_REGISTER


def search_with_retry(client: FCAClient, query: str) -> list[FCASearchResult]:
    for attempt in range(4):
        try:
            return client.search_firms(query)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("master_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--minimum-score", type=float, default=0.96)
    args = parser.parse_args()

    load_local_env(REPO_ROOT / ".env")
    email = os.getenv("FCA_API_EMAIL", "")
    api_key = os.getenv("FCA_API_KEY", "")
    if not email or not api_key:
        print("FCA_API_EMAIL and FCA_API_KEY are required in .env", file=sys.stderr)
        return 2

    with args.master_csv.open(encoding="utf-8-sig", newline="") as handle:
        master_rows = list(csv.DictReader(handle))
    candidates = [
        row for row in master_rows
        if row["forex_broker"] == "YES"
        and row["classification_confidence"] in {"HIGH", "MEDIUM"}
        and row["regulator_code"] != "FCA"
    ]
    # A legal entity can appear under multiple regulators; search it only once.
    unique_candidates: dict[str, dict[str, str]] = {}
    for row in candidates:
        unique_candidates.setdefault(normalize_name(row["legal_name"]), row)

    client = FCAClient(email, api_key)
    accepted_by_frn: dict[str, dict[str, object]] = {}
    reviewed: list[dict[str, object]] = []
    total = len(unique_candidates)
    for index, row in enumerate(unique_candidates.values(), start=1):
        query = row["legal_name"].strip()
        results = search_with_retry(client, query)
        scored = sorted(
            ((match_score(query, result.name), result) for result in results if is_active_firm(result)),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best = scored[0] if scored else (0.0, None)
        accepted = best is not None and best_score >= args.minimum_score
        reviewed.append({
            "candidate_name": query,
            "candidate_regulator": row["regulator_code"],
            "best_fca_name": clean_display_name(best.name) if best else "",
            "best_fca_frn": best.frn if best else "",
            "best_fca_status": best.status if best else "",
            "match_score": round(best_score, 4),
            "accepted": accepted,
        })
        if accepted and best is not None:
            normalized_row = {
                "legal_name": clean_display_name(best.name),
                "regulator_code": "FCA",
                "regulator": "Financial Conduct Authority",
                "jurisdiction": "United Kingdom",
                "license_number": best.frn,
                "license_type": "Financial Services Register firm",
                "status": "ACTIVE",
                "license_date": "",
                "approved_domains": "",
                "forex_broker": "YES",
                "classification_confidence": row["classification_confidence"],
                "classification_reason": (
                    f"Active FCA firm matched to {row['regulator_code']} candidate "
                    f"{row['legal_name']} (legal-name score {best_score:.3f})"
                ),
                "evidence_url": evidence_url(best),
                "evidence_status": "OFFICIAL_API",
                "needs_review": "NO" if best_score == 1.0 else "YES",
                "source_url": FCA_API_SOURCE,
                "last_checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "matched_from_regulator": row["regulator_code"],
                "matched_from_name": row["legal_name"],
                "match_score": round(best_score, 4),
            }
            existing = accepted_by_frn.get(best.frn)
            if existing is None or float(normalized_row["match_score"]) > float(existing["match_score"]):
                accepted_by_frn[best.frn] = normalized_row

        if index % 25 == 0 or index == total:
            print(f"Checked {index}/{total}; accepted {len(accepted_by_frn)} FCA matches", flush=True)
        # Stay comfortably under the official 50 requests per 10 seconds limit.
        time.sleep(0.24)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "minimum_score": args.minimum_score,
        "candidate_count": total,
        "accepted_count": len(accepted_by_frn),
        "records": sorted(accepted_by_frn.values(), key=lambda row: str(row["legal_name"])),
        "review_log": reviewed,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(accepted_by_frn)} FCA records to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
