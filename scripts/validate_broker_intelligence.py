#!/usr/bin/env python3
"""Validate the published broker-intelligence contract and audited sales copy."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


BANNED_COPY = re.compile(
    r"\b(delve|tapestry|seamless(?:ly)?|robust|unlock|supercharge|elevate|game-changing|"
    r"revolutionise|myriad|plethora|beacon|ever-evolving|cutting-edge|transformative|"
    r"synergy|holistic|embark|foster|facilitate|multifaceted|intricate|paramount)\b|"
    r"not just .+ but|more than just|whether you(?:'re| are)|that's where|say goodbye|"
    r"imagine a world|what if i told you|here's the thing|let me be clear|at the end of the day",
    re.IGNORECASE,
)
ALLOWED_TECH = {"CONFIRMED_ACTIVE", "LIKELY_ACTIVE", "DIRECTORY_REPORTED", "HISTORICAL", "UNKNOWN"}
VENDORS = {"Trading Central", "Autochartist", "Acuity Trading"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profiles", type=Path)
    options = parser.parse_args()
    payload = json.loads(options.profiles.read_text(encoding="utf-8"))
    profiles = payload["profiles"]
    priority25 = [p for p in profiles if p.get("verification", {}).get("scope") == "PRIORITY_25"]
    priority100 = [p for p in profiles if p.get("priority_tier") == "PRIORITY_100"]
    errors = []

    if len(profiles) != 1627:
        errors.append(f"expected 1627 profiles, found {len(profiles)}")
    if len(priority25) != 25:
        errors.append(f"expected 25 gold profiles, found {len(priority25)}")
    if len(priority100) != 100:
        errors.append(f"expected 100 priority profiles, found {len(priority100)}")

    copy_lines = []
    for profile in priority100:
        assessments = profile.get("technology_assessment", [])
        if {item.get("vendor") for item in assessments} != VENDORS or len(assessments) != 3:
            errors.append(f"{profile['slug']}: technology assessment must cover exactly three vendors")
        if any(item.get("status") not in ALLOWED_TECH for item in assessments):
            errors.append(f"{profile['slug']}: invalid technology status")
        if not profile.get("intelligence_scope"):
            errors.append(f"{profile['slug']}: missing intelligence scope")

    for profile in priority25:
        footprint = profile.get("canonical_regulatory_footprint", {})
        if footprint.get("readiness") not in {"READY", "READY_WITH_UNRESOLVED"}:
            errors.append(f"{profile['slug']}: canonical footprint is not ready")
        intel = profile.get("sales_intelligence", {})
        if not intel.get("why_now") or not intel.get("discovery_angle"):
            errors.append(f"{profile['slug']}: incomplete sales brief")
        copy_lines.extend([intel.get("why_now", ""), intel.get("discovery_angle", "")])
        for person in profile.get("people", []):
            if person.get("status") == "CONFIRMED_CURRENT" and (not person.get("name") or not person.get("evidence_url")):
                errors.append(f"{profile['slug']}: confirmed person lacks a name or source")
        codes = [item.get("code") for item in profile.get("regulators", [])]
        if len(codes) != len(set(codes)):
            errors.append(f"{profile['slug']}: duplicate canonical regulator code")

    for line in copy_lines:
        if BANNED_COPY.search(line):
            errors.append(f"content-audit vocabulary or construction hit: {line}")
        if "—" in line or line.count(";"):
            errors.append(f"content-audit punctuation hit: {line}")
    repeats = [line for line, count in Counter(copy_lines).items() if line and count > 1]
    if repeats:
        errors.append(f"repeated sales-copy lines: {repeats}")

    result = {
        "profile_count": len(profiles),
        "priority_25_count": len(priority25),
        "priority_100_count": len(priority100),
        "priority_25_with_confirmed_leader": sum(any(p.get("status") == "CONFIRMED_CURRENT" for p in row.get("people", [])) for row in priority25),
        "priority_25_with_material_history": sum(bool(row.get("change_history")) for row in priority25),
        "content_audit_score": "5/5" if not errors else "FAIL",
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
