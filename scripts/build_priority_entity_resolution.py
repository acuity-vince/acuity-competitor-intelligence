#!/usr/bin/env python3
"""Build a canonical legal-entity and licence footprint for the Priority 25."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unicodedata


def clean(value: object) -> str:
    return str(value or "").strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"\b(limited)\b", "ltd", text)
    return re.sub(r"[^a-z0-9]", "", text)


def licence_key(item: dict) -> tuple[str, str, str]:
    return clean(item.get("regulator_code")), clean(item.get("license_number")), norm(item.get("legal_name"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()

    verified = json.loads(args.verification.read_text(encoding="utf-8"))
    overrides = json.loads(args.overrides.read_text(encoding="utf-8"))
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added: dict[str, list[dict]] = {}
    for row in overrides.get("official_records", []):
        item = dict(row)
        slug = item.pop("slug")
        item.update({"source": "Official regulator registry", "evidence_status": "OFFICIAL_PUBLIC_REGISTER", "last_checked": generated_at})
        added.setdefault(slug, []).append(item)
    resolutions = {(row["slug"], row["regulator_code"]): row for row in overrides.get("claim_resolutions", [])}

    profiles = []
    audits = []
    for profile in verified.get("profiles", []):
        unique: dict[tuple[str, str, str], dict] = {}
        duplicate_count = 0
        for item in [*profile.get("official_licenses", []), *added.get(profile["slug"], [])]:
            key = licence_key(item)
            if key in unique:
                duplicate_count += 1
                unique[key].update({k: v for k, v in item.items() if v})
            else:
                unique[key] = dict(item)
        official = sorted(unique.values(), key=lambda x: (clean(x.get("regulator_code")), norm(x.get("legal_name")), clean(x.get("license_number"))))
        entities: dict[str, dict] = {}
        orphan_count = 0
        for item in official:
            if not clean(item.get("legal_name")) or not clean(item.get("regulator_code")):
                orphan_count += 1
                continue
            entity = entities.setdefault(norm(item["legal_name"]), {
                "canonical_name": clean(item["legal_name"]),
                "jurisdictions": [],
                "mapping_confidence": clean(item.get("mapping_confidence")) or "HIGH",
                "mapping_basis": clean(item.get("mapping_basis")) or "Exact legal entity match in an official regulator source.",
                "mapping_evidence_url": clean(item.get("mapping_evidence_url")) or clean(item.get("evidence_url")),
                "licenses": [],
            })
            if clean(item.get("jurisdiction")) not in entity["jurisdictions"]:
                entity["jurisdictions"].append(clean(item.get("jurisdiction")))
            entity["licenses"].append(item)

        claims = []
        active_codes = {clean(item.get("regulator_code")) for item in official if clean(item.get("status")).upper() == "ACTIVE"}
        for code in profile.get("reported_regulators", []):
            override = resolutions.get((profile["slug"], code))
            if code in active_codes:
                status = "VERIFIED_ACTIVE"
            elif override:
                status = override["classification"]
            else:
                status = "UNRESOLVED_REPORTED"
            claim = {"regulator_code": code, "status": status}
            if override:
                claim.update({k: v for k, v in override.items() if k not in {"slug", "regulator_code", "classification"}})
            claims.append(claim)
        blocking = [item for item in claims if item["status"] in {"UNRESOLVED_REPORTED", "RELATIONSHIP_UNRESOLVED", "CURRENT_REGISTER_NO_RESULT"}]
        readiness = "READY" if not blocking and not orphan_count and not duplicate_count else "REVIEW"
        canonical = {
            "scope": "PRIORITY_25",
            "readiness": readiness,
            "legal_entities": sorted(entities.values(), key=lambda x: norm(x["canonical_name"])),
            "regulator_claims": claims,
            "unresolved_claims": blocking,
            "official_license_count": len(official),
            "last_verified": generated_at,
        }
        profiles.append({"slug": profile["slug"], "brand_name": profile["brand_name"], "priority_rank": profile["priority_rank"], "canonical_regulatory_footprint": canonical})
        audits.append({
            "priority_rank": profile["priority_rank"], "brand_name": profile["brand_name"], "slug": profile["slug"],
            "readiness": readiness, "legal_entity_count": len(entities), "official_license_count": len(official),
            "orphan_official_licenses": orphan_count, "duplicate_official_licenses": duplicate_count,
            "blocking_claims": " | ".join(f'{item["regulator_code"]}:{item["status"]}' for item in blocking),
            "last_verified": generated_at,
        })

    hold = [row for row in audits if row["readiness"] != "READY"]
    payload = {
        "generated_at": generated_at,
        "scope": "PRIORITY_25",
        "expansion_gate": {
            "status": "READY" if not hold and len(profiles) == 25 else "HOLD",
            "ready_profiles": len(profiles) - len(hold),
            "review_profiles": len(hold),
            "profile_count": len(profiles),
            "criteria": ["25 canonical footprints built", "zero orphan official licences", "zero duplicate official licences", "zero unclassified or relationship-ambiguous core claims"],
            "blocking_profiles": [row["slug"] for row in hold],
        },
        "profiles": profiles,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    with args.audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audits[0]))
        writer.writeheader()
        writer.writerows(audits)
    print(json.dumps(payload["expansion_gate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
