"""Combine regulator-specific active candidate lists into one normalized registry."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re


FIELDS = [
    "legal_name", "regulator_code", "regulator", "jurisdiction", "license_number",
    "license_type", "status", "license_date", "approved_domains", "forex_broker",
    "classification_confidence", "classification_reason", "evidence_url",
    "evidence_status", "needs_review", "source_url", "last_checked",
]

ASIC_SOURCE = "https://data.gov.au/data/dataset/asic-afs-licensee"
MAURITIUS_SOURCE = "https://opr.fscmauritius.org/ords/opr/r/fsc-opr/fsc-online-public-register-opr"
NON_TARGET_NAME = re.compile(
    r"\b(bank|insurance|superannuation|trustee|asset management|funds? management|"
    r"investment management|wealth management|responsible entity|pension)\b",
    re.IGNORECASE,
)
TARGET_NAME = re.compile(r"\b(forex|fx|markets?|trading|broker|derivatives|exchange)\b", re.IGNORECASE)


def normalize_cysec(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for row in rows:
        result.append({
            "legal_name": row["legal_name"],
            "regulator_code": "CySEC",
            "regulator": row["regulator"],
            "jurisdiction": row["jurisdiction"],
            "license_number": row["license_number"],
            "license_type": row["license_type"],
            "status": row["status"],
            "license_date": row["license_date"],
            "approved_domains": row["approved_domains"],
            "forex_broker": row["forex_broker"],
            "classification_confidence": row["classification_confidence"],
            "classification_reason": row["classification_reason"],
            "evidence_url": row["evidence_url"],
            "evidence_status": row["evidence_status"],
            "needs_review": row["needs_review"],
            "source_url": row["source_url"],
            "last_checked": row["last_seen"],
        })
    return result


def normalize_asic(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = []
    for row in rows:
        condition = row["AFS_LIC_CONDITION"]
        # Target the subset authorised to issue or make markets in FX for retail clients.
        if not (
            "foreign exchange contracts" in condition.lower()
            and re.search(r"issuing|make a market", condition, re.IGNORECASE)
            and "retail" in condition.lower()
        ):
            continue
        name = row["AFS_LIC_NAME"].strip()
        if NON_TARGET_NAME.search(name):
            broker, confidence, review = "NO", "HIGH", "NO"
            reason = "Legal name indicates a non-target bank, fund, asset/wealth manager, insurer, or trustee"
        elif TARGET_NAME.search(name):
            broker, confidence, review = "YES", "MEDIUM", "NO"
            reason = "AFS licence authorises retail FX issuance/market-making and the legal name indicates trading activity"
        else:
            broker, confidence, review = "YES", "LOW", "YES"
            reason = "AFS licence authorises retail FX issuance/market-making; website/product validation still required"
        result.append({
            "legal_name": name,
            "regulator_code": "ASIC",
            "regulator": "Australian Securities and Investments Commission",
            "jurisdiction": "Australia",
            "license_number": row["AFS_LIC_NUM"],
            "license_type": "Australian Financial Services Licence",
            "status": "ACTIVE",
            "license_date": row["AFS_LIC_START_DT"],
            "approved_domains": "",
            "forex_broker": broker,
            "classification_confidence": confidence,
            "classification_reason": reason,
            "evidence_url": ASIC_SOURCE,
            "evidence_status": "OFFICIAL_DATASET",
            "needs_review": review,
            "source_url": ASIC_SOURCE,
            "last_checked": now,
        })
    return result


def normalize_mauritius(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = []
    for record in payload["active"]:
        _, name, license_date, license_type, annotations = record
        if TARGET_NAME.search(name):
            broker, confidence = "YES", "LOW"
            reason = "Active FSC Mauritius investment-dealer licence and trading-oriented legal name; product validation required"
        else:
            broker, confidence = "NO", "LOW"
            reason = "Active investment-dealer licence, but no affirmative FX/CFD evidence found; manual product validation required"
        result.append({
            "legal_name": name.strip(),
            "regulator_code": "FSC Mauritius",
            "regulator": "Financial Services Commission Mauritius",
            "jurisdiction": "Mauritius",
            "license_number": "",
            "license_type": license_type,
            "status": "ACTIVE",
            "license_date": license_date,
            "approved_domains": "",
            "forex_broker": broker,
            "classification_confidence": confidence,
            "classification_reason": reason,
            "evidence_url": MAURITIUS_SOURCE,
            "evidence_status": "OFFICIAL_PUBLIC_REGISTER",
            "needs_review": "YES",
            "source_url": MAURITIUS_SOURCE,
            "last_checked": now,
        })
    return result


def normalize_fca(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        {field: str(record.get(field, "")) for field in FIELDS}
        for record in payload.get("records", [])
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cysec_csv", type=Path)
    parser.add_argument("asic_csv", type=Path)
    parser.add_argument("mauritius_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--fca-json", type=Path)
    args = parser.parse_args()
    rows = normalize_cysec(args.cysec_csv) + normalize_asic(args.asic_csv) + normalize_mauritius(args.mauritius_json)
    if args.fca_json:
        rows += normalize_fca(args.fca_json)
    rows.sort(key=lambda row: (row["regulator_code"], row["forex_broker"] != "YES", row["legal_name"]))
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} active records")


if __name__ == "__main__":
    main()
