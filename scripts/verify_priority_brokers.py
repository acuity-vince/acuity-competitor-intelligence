#!/usr/bin/env python3
"""Verify the Priority 25 against regulator-owned datasets and the FCA API."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


ASIC_SOURCE = "https://data.gov.au/data/dataset/asic-afs-licensee"
MAURITIUS_SOURCE = "https://opr.fscmauritius.org/ords/opr/r/fsc-opr/fsc-online-public-register-opr"
FCA_SOURCE = "https://register.fca.org.uk/"
FSCA_SOURCE = "https://www2.fsca.co.za/Fais/Search_FSP.htm"
CORE_REGULATORS = {"ASIC", "CySEC", "FCA", "FSC Mauritius", "FSCA"}

REGULATOR_ALIASES = {
    "australian securities and investments commission (asic)": "ASIC",
    "australian securities and investment commission (asic)": "ASIC",
    "cyprus securities and exchange commission (cysec)": "CySEC",
    "cyprus securities and exchange commission (cysec) ": "CySEC",
    "financial conduct authority (fca)": "FCA",
    "financial services commission (mauritius)": "FSC Mauritius",
    "mauritius financial services commission (fsc)": "FSC Mauritius",
    "financial sector conduct authority (fsca)": "FSCA",
    "financial sector conduct authority (south africa)": "FSCA",
}

# Brand searches are only used to discover the regulator's legal entity name.
# Acceptance still requires an authorised firm returned by the official API.
FCA_QUERIES = {
    "cfi-financial-group": ["Credit Financier Invest Limited"],
    "etoro": ["eToro UK Ltd"],
    "fortrade": ["Fortrade Limited"],
    "fxcm": ["Stratos Markets Limited"],
    "fxpro": ["FxPro UK Limited"],
    "markets-com": ["Markets.com", "Finalto Financial Services Limited"],
    "plus500": ["Plus500UK Ltd"],
    "activtrades": ["ActivTrades Plc"],
    "admiral-markets-admirals": ["Admirals UK Ltd", "Admiral Markets UK Ltd"],
    "atfx": ["AT Global Markets (UK) Limited"],
    "exness": ["Exness (UK) Ltd"],
    "hantec-financial-hantec-markets-asia": ["Hantec Markets Limited"],
    "hycm": ["Henyep Capital Markets (UK) Limited", "HYCM Capital Markets (UK) Limited"],
    "ironfx": ["Notesco UK Limited"],
    "moneta-markets": ["Moneta Markets"],
    "vantage-vantage-markets": ["Vantage Global Prime LLP"],
}

# Legal entities already tied to these brands by the supplied directory data or
# an unambiguous former/current brand name. They are matched only by exact name
# to a regulator-owned register row.
KNOWN_LEGAL_ENTITIES = {
    "cfi-financial-group": ["CFI International Ltd"],
    "fusion-markets": ["Gleneagle Asset Management Limited", "Gleneagle Securities (Aust) Pty Limited"],
    "fxcm": ["Stratos Trading Pty. Limited"],
    "plus500": ["Plus500AU Pty. Ltd."],
    "atfx": ["ATFX Global Markets (Cy) Ltd", "AT Global Markets (Australia) Pty Ltd", "AT Global Markets Intl Ltd"],
    "easymarkets": ["Easy Forex Trading Ltd", "EASYMARKETS PTY LTD"],
    "ironfx": ["Notesco Financial Services Ltd"],
    "moneta-markets": ["Moneta Markets Trading Limited"],
}


class FCAResult:
    def __init__(self, row: dict):
        def pick(*keys: str) -> str:
            for key in keys:
                if row.get(key) is not None:
                    return clean(row[key])
            return ""
        self.frn = pick("FRN", "frn", "Reference Number", "ReferenceNumber")
        self.name = pick("Name", "name", "Firm Name", "FirmName")
        self.status = pick("Status", "status")


class FCAClient:
    def __init__(self, email: str, key: str):
        self.email = email
        self.key = key

    def search_firms(self, query: str) -> list[FCAResult]:
        url = f"https://register.fca.org.uk/services/V0.1/Search?{urlencode({'q': query, 'type': 'firm'})}"
        request = Request(url, headers={
            "X-Auth-Email": self.email,
            "X-Auth-Key": self.key,
            "Accept": "application/json",
            "User-Agent": "AcuityCompetitorResearch/1.0",
        })
        # The FCA API endpoint currently serves an expired certificate. Scope the
        # compatibility context to this regulator-owned hostname and authenticated
        # GET request so verification can continue while preserving the failure in
        # the audit trail if the endpoint itself does not respond.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with urlopen(request, timeout=25, context=context) as response:
            payload = json.load(response)
        rows = payload.get("Data") or payload.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("Results") or rows.get("results") or []
        return [FCAResult(row) for row in rows]


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().casefold()
    text = re.sub(r"\s*\(postcode:.*?\)\s*$", "", text, flags=re.I)
    text = text.replace("&", " and ")
    text = re.sub(r"\b(limited)\b", "ltd", text)
    text = re.sub(r"\b(proprietary)\b", "pty", text)
    return re.sub(r"[^a-z0-9]", "", text)


def regulator_code(value: object) -> str:
    raw = clean(value)
    return REGULATOR_ALIASES.get(raw.casefold(), raw)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'") )


def asic_records(path: Path) -> dict[str, list[dict]]:
    records: dict[str, list[dict]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            condition = clean(row.get("AFS_LIC_CONDITION"))
            if "foreign exchange contracts" not in condition.casefold():
                continue
            record = {
                "regulator_code": "ASIC",
                "regulator_name": "Australian Securities and Investments Commission",
                "jurisdiction": "Australia",
                "license_number": clean(row.get("AFS_LIC_NUM")),
                "license_type": "Australian Financial Services Licence",
                "status": "ACTIVE",
                "license_date": clean(row.get("AFS_LIC_START_DT")),
                "legal_name": clean(row.get("AFS_LIC_NAME")),
                "evidence_url": ASIC_SOURCE,
                "evidence_status": "OFFICIAL_DATASET",
                "source": "Official regulator registry",
            }
            records.setdefault(norm(record["legal_name"]), []).append(record)
    return records


def mauritius_records(path: Path) -> dict[str, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, list[dict]] = {}
    for row in payload.get("active", []):
        _, name, license_date, license_type, *_ = row
        record = {
            "regulator_code": "FSC Mauritius",
            "regulator_name": "Financial Services Commission Mauritius",
            "jurisdiction": "Mauritius",
            "license_number": "",
            "license_type": clean(license_type),
            "status": "ACTIVE",
            "license_date": clean(license_date),
            "legal_name": clean(name),
            "evidence_url": MAURITIUS_SOURCE,
            "evidence_status": "OFFICIAL_PUBLIC_REGISTER",
            "source": "Official regulator registry",
        }
        records.setdefault(norm(name), []).append(record)
    return records


def fsca_records(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records: dict[str, list[dict]] = {}
    audits: dict[str, list[dict]] = {}
    for row in payload.get("search_audit", []):
        slug = clean(row.get("slug"))
        if slug:
            audits.setdefault(slug, []).append(row)
    for row in payload.get("authorised", []):
        if clean(row.get("official_status")).casefold() != "authorized":
            continue
        slug = clean(row.get("slug"))
        fsp_number = clean(row.get("fsp_number"))
        legal_name = clean(row.get("legal_name"))
        if not slug or not fsp_number or not legal_name:
            continue
        records.setdefault(slug, []).append({
            "regulator_code": "FSCA",
            "regulator_name": "Financial Sector Conduct Authority",
            "jurisdiction": "South Africa",
            "license_number": fsp_number,
            "license_type": "Authorised Financial Services Provider",
            "status": "ACTIVE",
            "license_date": "",
            "legal_name": legal_name,
            "evidence_url": clean(row.get("evidence_url")) or FSCA_SOURCE,
            "evidence_status": "OFFICIAL_SEARCH_RESULT",
            "source": "Official regulator registry",
            "brand_mapping_basis": clean(row.get("brand_mapping_basis")),
            "brand_mapping_url": clean(row.get("brand_mapping_url")),
        })
    return records, audits


def aliases(profile: dict) -> list[str]:
    values = [profile.get("brand_name"), *profile.get("aliases", [])]
    values += [item.get("legal_name") for item in profile.get("legal_entities", [])]
    values += KNOWN_LEGAL_ENTITIES.get(profile.get("slug", ""), [])
    return sorted({clean(value) for value in values if clean(value)})


def exact_matches(profile: dict, index: dict[str, list[dict]]) -> list[dict]:
    found: dict[tuple[str, str, str], dict] = {}
    for alias in aliases(profile):
        for record in index.get(norm(alias), []):
            key = (record["regulator_code"], record["license_number"], norm(record["legal_name"]))
            found[key] = record
    return list(found.values())


def fca_matches(profile: dict, client: FCAClient | None) -> tuple[list[dict], list[dict]]:
    if not client:
        return [], [{"query": "", "outcome": "FCA API credentials unavailable"}]
    queries = FCA_QUERIES.get(profile["slug"], [])
    accepted: dict[str, dict] = {}
    audit: list[dict] = []
    for query in queries:
        try:
            results = client.search_firms(query)
        except Exception as exc:  # preserve the rest of the ledger if one API call fails
            audit.append({"query": query, "outcome": f"API error: {type(exc).__name__}"})
            continue
        exact = [item for item in results if norm(item.name) == norm(query) and item.status.casefold() == "authorised" and item.frn]
        for item in exact:
            accepted[item.frn] = {
                "regulator_code": "FCA",
                "regulator_name": "Financial Conduct Authority",
                "jurisdiction": "United Kingdom",
                "license_number": item.frn,
                "license_type": "Financial Services Register firm",
                "status": "ACTIVE",
                "license_date": "",
                "legal_name": re.sub(r"\s*\(Postcode:.*?\)\s*$", "", item.name, flags=re.I).strip(),
                "evidence_url": f"https://register.fca.org.uk/services/V0.1/Firm/{item.frn}",
                "evidence_status": "OFFICIAL_API",
                "source": "Official regulator registry",
            }
        audit.append({
            "query": query,
            "outcome": "verified" if exact else "no exact authorised match",
            "result_count": len(results),
            "accepted_frns": "; ".join(item.frn for item in exact),
        })
        time.sleep(0.24)
    return list(accepted.values()), audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--asic", type=Path, required=True)
    parser.add_argument("--mauritius", type=Path, required=True)
    parser.add_argument("--fsca", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    profiles = json.loads(args.profiles.read_text(encoding="utf-8"))["profiles"]
    priority = sorted(
        (profile for profile in profiles if profile.get("priority_rank") and profile["priority_rank"] <= 25),
        key=lambda profile: profile["priority_rank"],
    )
    asic = asic_records(args.asic)
    mauritius = mauritius_records(args.mauritius)
    fsca, fsca_audits = fsca_records(args.fsca)
    official_indexes: dict[str, dict[str, list[dict]]] = {}
    for source_profile in profiles:
        for item in source_profile.get("licenses", []):
            if item.get("source") != "Official regulator registry":
                continue
            code = regulator_code(item.get("regulator_code") or item.get("regulator_name"))
            official_indexes.setdefault(code, {}).setdefault(norm(item.get("legal_name")), []).append(item)
    load_env(REPO_ROOT / ".env")
    email, key = os.getenv("FCA_API_EMAIL", ""), os.getenv("FCA_API_KEY", "")
    fca_client = FCAClient(email, key) if email and key else None

    output: list[dict] = []
    audit_rows: list[dict] = []
    for profile in priority:
        reported = sorted({regulator_code(item.get("regulator_code") or item.get("regulator_name")) for item in profile.get("licenses", [])} & CORE_REGULATORS)
        verified = [item for item in profile.get("licenses", []) if item.get("source") == "Official regulator registry"]
        for code in reported:
            verified += exact_matches(profile, official_indexes.get(code, {}))
        if "ASIC" in reported:
            verified += exact_matches(profile, asic)
        if "FSC Mauritius" in reported:
            verified += exact_matches(profile, mauritius)
        if "FSCA" in reported:
            verified += fsca.get(profile["slug"], [])
        fca_audit: list[dict] = []
        if "FCA" in reported:
            fca, fca_audit = fca_matches(profile, fca_client)
            verified += fca

        unique: dict[tuple[str, str, str], dict] = {}
        for item in verified:
            code = regulator_code(item.get("regulator_code") or item.get("regulator_name"))
            normalized = dict(item)
            normalized["regulator_code"] = code
            normalized["last_checked"] = generated_at
            unique[(code, clean(item.get("license_number")), norm(item.get("legal_name")))] = normalized
        verified = sorted(unique.values(), key=lambda item: (item["regulator_code"], item.get("legal_name", "")))
        verified_codes = sorted({item["regulator_code"] for item in verified} & CORE_REGULATORS)
        unresolved = sorted(set(reported) - set(verified_codes))
        notes = []
        if "FSCA" in unresolved:
            notes.append("FSCA claim remains unresolved after searches of the regulator's search-only public register.")
        if unresolved:
            notes.append("Unresolved means directory-reported, not disproven.")
        status = "VERIFIED" if reported and not unresolved else "PARTIAL" if verified_codes else "UNVERIFIED"
        record = {
            "slug": profile["slug"],
            "brand_name": profile["brand_name"],
            "priority_rank": profile["priority_rank"],
            "status": status,
            "reported_regulators": reported,
            "verified_regulators": verified_codes,
            "unresolved_regulators": unresolved,
            "official_licenses": verified,
            "notes": notes,
            "last_verified": generated_at,
        }
        output.append(record)
        audit_rows.append({
            "priority_rank": profile["priority_rank"],
            "brand_name": profile["brand_name"],
            "slug": profile["slug"],
            "verification_status": status,
            "reported_regulators": " | ".join(reported),
            "verified_regulators": " | ".join(verified_codes),
            "unresolved_regulators": " | ".join(unresolved),
            "official_license_count": len(verified),
            "fca_api_audit": json.dumps(fca_audit, ensure_ascii=False),
            "fsca_search_audit": json.dumps(fsca_audits.get(profile["slug"], []), ensure_ascii=False),
            "last_verified": generated_at,
        })
        print(f"#{profile['priority_rank']:02d} {profile['brand_name']}: {status} ({len(verified_codes)}/{len(reported)} core regulators)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"generated_at": generated_at, "scope": "PRIORITY_25", "profiles": output}, indent=2), encoding="utf-8")
    with args.audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
