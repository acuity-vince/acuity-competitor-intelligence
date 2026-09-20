#!/usr/bin/env python3
"""Merge reviewed Firecrawl monitor events into broker change history.

The connector export is deliberately review-gated: only entries with
``meaningful_change: true`` and an allowed material category are published.
Unchanged, errored, or merely cosmetic page diffs stay in the audit export but
never become sales intelligence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_CATEGORIES = {
    "REGULATORY",
    "ENTITY_MAPPING",
    "LEADERSHIP",
    "OFFICE_OR_MARKET_EXPANSION",
    "PRODUCT",
    "TECHNOLOGY_RELATIONSHIP",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitoring", required=True, type=Path)
    parser.add_argument("--checks", required=True, type=Path)
    parser.add_argument("--intelligence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    options = parse_args()
    monitoring = json.loads(options.monitoring.read_text(encoding="utf-8"))
    checks = json.loads(options.checks.read_text(encoding="utf-8"))
    intelligence = json.loads(options.intelligence.read_text(encoding="utf-8"))

    known_monitors = {item["id"] for item in monitoring.get("monitors", [])}
    profiles = {item["slug"]: item for item in intelligence.get("profiles", [])}
    added = 0
    ignored = 0

    for check in checks.get("checks", []):
        if check.get("monitor_id") not in known_monitors:
            raise ValueError(f"Unknown monitor id: {check.get('monitor_id')}")
        for event in check.get("events", []):
            if not event.get("meaningful_change"):
                ignored += 1
                continue
            category = event.get("category")
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"Invalid material category: {category}")
            slug = event.get("profile_slug")
            if slug not in profiles:
                raise ValueError(f"Unknown profile slug: {slug}")
            if not all(event.get(key) for key in ("date", "summary", "evidence_url")):
                raise ValueError(f"Incomplete material event for {slug}")

            profile = profiles[slug]
            history = profile.setdefault("change_history", [])
            key = (event["date"], category, event["summary"], event["evidence_url"])
            existing = {
                (item.get("date"), item.get("category"), item.get("summary"), item.get("evidence_url"))
                for item in history
            }
            if key in existing:
                ignored += 1
                continue
            history.append({
                "date": event["date"],
                "category": category,
                "summary": event["summary"],
                "evidence_url": event["evidence_url"],
                "monitor_id": check["monitor_id"],
                "check_id": check.get("check_id", ""),
            })
            history.sort(key=lambda item: item.get("date", ""), reverse=True)
            profile["sources"] = sorted(set(profile.get("sources", []) + [event["evidence_url"]]))
            added += 1

    options.output.write_text(json.dumps(intelligence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"material_events_added": added, "events_ignored": ignored, "output": str(options.output)}, indent=2))


if __name__ == "__main__":
    main()
