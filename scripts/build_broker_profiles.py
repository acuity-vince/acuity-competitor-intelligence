#!/usr/bin/env python3
"""Build broker-centric intelligence profiles from regulator and directory sources."""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


def clean(value: str | None) -> str:
    return (value or "").strip()


def norm_name(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"\([^)]*\)", "", value.lower())
    return re.sub(r"[^a-z0-9]", "", value)


def hostname(value: str | None) -> str:
    value = clean(value).lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").removeprefix("www.").rstrip(".")


def split_values(value: str | None) -> list[str]:
    return [part.strip() for part in re.split(r"\s*[;|]\s*", clean(value)) if part.strip()]


def split_domains(value: str | None) -> list[str]:
    values = re.split(r"[;,|\s]+", clean(value))
    return sorted({domain for part in values if (domain := hostname(part))})


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()).strip("-")
    return slug or "broker"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def relationship(row: dict[str, str]) -> dict:
    score = int(clean(row.get("confidence_score")) or 0)
    return {
        "vendor": "Trading Central",
        "status": clean(row.get("relationship_status")) or "UNCLEAR",
        "confidence_score": score,
        "confidence": "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW",
        "products": split_values(row.get("trading_central_products")),
        "integration_types": split_values(row.get("integration_type")),
        "summary": clean(row.get("evidence_summary")),
        "description": clean(row.get("relationship_description")),
        "relationship_type": clean(row.get("relationship_type")),
        "source_type": clean(row.get("source_type")),
        "evidence_url": clean(row.get("primary_evidence_url")),
        "evidence_title": clean(row.get("primary_evidence_title")),
        "additional_evidence_urls": split_values(row.get("additional_evidence_urls")),
        "first_evidence_date": clean(row.get("first_evidence_date")),
        "most_recent_evidence_date": clean(row.get("most_recent_evidence_date")),
        "evidence_excerpt": clean(row.get("evidence_excerpt")),
        "research_notes": clean(row.get("research_notes")),
        "date_checked": clean(row.get("date_checked")),
    }


def directory_relationship(vendor: str, row: dict[str, str]) -> dict:
    pages = split_values(row.get("research_tool_pages_checked"))
    notes = clean(row.get("research_tool_notes"))
    return {
        "vendor": vendor,
        "status": "DIRECTORY_REPORTED",
        "confidence_score": 70,
        "confidence": "MEDIUM",
        "products": [],
        "integration_types": [],
        "summary": notes or f"{vendor} relationship reported in the supplied broker directory export.",
        "description": "Directory-reported research-tool relationship; retain for verification against broker-owned evidence.",
        "relationship_type": "DIRECTORY_REPORTED",
        "source_type": "Claude broker directory export",
        "evidence_url": pages[0] if pages else clean(row.get("website")),
        "evidence_title": "Broker directory research-tool scan",
        "additional_evidence_urls": pages[1:],
        "first_evidence_date": "",
        "most_recent_evidence_date": "",
        "evidence_excerpt": "",
        "research_notes": notes,
        "date_checked": "",
    }


def new_profile(profile_id: str, slug: str, brand_name: str, source: str) -> dict:
    return {
        "id": profile_id,
        "slug": slug,
        "brand_name": brand_name,
        "broker_group": "",
        "aliases": [],
        "primary_domain": "",
        "website_url": "",
        "primary_market": "",
        "headquarters": "",
        "founded_year": "",
        "directory_license_status": "",
        "directory_notes": "",
        "research_scan": {},
        "forex_broker": "UNKNOWN",
        "classification_confidence": "LOW",
        "needs_review": "YES",
        "profile_sources": [source],
        "domains": [],
        "legal_entities": [],
        "licenses": [],
        "regulators": [],
        "offices": [],
        "people": [],
        "vendor_relationships": [],
        "last_checked": "",
    }


def add_domain(profile: dict, domain: str, url: str = "", source: str = "") -> None:
    if not domain:
        return
    if not any(item["domain"] == domain for item in profile["domains"]):
        profile["domains"].append({"domain": domain, "url": url or f"https://{domain}", "source": source})


def add_registry_row(profile: dict, row: dict[str, str]) -> None:
    legal_name = clean(row.get("legal_name"))
    entity_key = (norm_name(legal_name), clean(row.get("jurisdiction")))
    if legal_name and not any((norm_name(item["legal_name"]), item["jurisdiction"]) == entity_key for item in profile["legal_entities"]):
        profile["legal_entities"].append({
            "legal_name": legal_name,
            "jurisdiction": clean(row.get("jurisdiction")),
            "status": clean(row.get("status")),
            "source_url": clean(row.get("source_url")),
        })

    license_key = (clean(row.get("regulator_code")), clean(row.get("license_number")), legal_name)
    if not any((item["regulator_code"], item["license_number"], item["legal_name"]) == license_key for item in profile["licenses"]):
        profile["licenses"].append({
            "regulator_code": clean(row.get("regulator_code")),
            "regulator_name": clean(row.get("regulator")),
            "jurisdiction": clean(row.get("jurisdiction")),
            "license_number": clean(row.get("license_number")),
            "license_type": clean(row.get("license_type")),
            "status": clean(row.get("status")),
            "license_date": clean(row.get("license_date")),
            "legal_name": legal_name,
            "evidence_url": clean(row.get("evidence_url")) or clean(row.get("source_url")),
            "evidence_status": clean(row.get("evidence_status")),
            "last_checked": clean(row.get("last_checked")),
            "source": "Official regulator registry",
        })

    for domain in split_domains(row.get("approved_domains")):
        add_domain(profile, domain, source="Official regulator registry")

    if clean(row.get("forex_broker")) == "YES":
        profile["forex_broker"] = "YES"
    elif profile["forex_broker"] == "UNKNOWN" and clean(row.get("forex_broker")) == "NO":
        profile["forex_broker"] = "NO"
    confidence = clean(row.get("classification_confidence"))
    rank = {"": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    if rank.get(confidence, 0) > rank.get(profile["classification_confidence"], 0):
        profile["classification_confidence"] = confidence
    if clean(row.get("needs_review")) == "NO":
        profile["needs_review"] = "NO"
    profile["last_checked"] = max(profile["last_checked"], clean(row.get("last_checked")))


def is_brand_profile(profile: dict) -> bool:
    return any(source != "Official regulator registry" for source in profile["profile_sources"]) or bool(profile["vendor_relationships"])


def append_unique(target: list, values: list, key) -> None:
    existing = {key(item) for item in target}
    for item in values:
        item_key = key(item)
        if item_key not in existing:
            target.append(item)
            existing.add(item_key)


def merge_profile_into(target: dict, source: dict) -> None:
    target["profile_sources"] = sorted(set(target["profile_sources"] + source["profile_sources"]))
    target["aliases"] = sorted(set(target.get("aliases", []) + source.get("aliases", []) + [source["brand_name"]]))
    append_unique(target["domains"], source["domains"], lambda item: item.get("domain", ""))
    append_unique(target["legal_entities"], source["legal_entities"], lambda item: (norm_name(item.get("legal_name")), item.get("jurisdiction", "")))
    append_unique(target["licenses"], source["licenses"], lambda item: (item.get("regulator_code", ""), item.get("license_number", ""), norm_name(item.get("legal_name"))))
    append_unique(target["offices"], source["offices"], lambda item: (item.get("country", ""), item.get("city", ""), item.get("type", "")))
    append_unique(target["people"], source["people"], lambda item: (norm_name(item.get("name")), item.get("role", "")))
    for relationship_item in source["vendor_relationships"]:
        existing = next((item for item in target["vendor_relationships"] if item["vendor"].lower() == relationship_item["vendor"].lower()), None)
        if not existing:
            target["vendor_relationships"].append(relationship_item)
        elif relationship_item.get("confidence_score", 0) > existing.get("confidence_score", 0):
            target["vendor_relationships"].remove(existing)
            target["vendor_relationships"].append(relationship_item)
    for field in ["primary_domain", "website_url", "primary_market", "headquarters", "founded_year", "directory_license_status", "directory_notes"]:
        if not target.get(field) and source.get(field):
            target[field] = source[field]
    if target["forex_broker"] == "UNKNOWN" or source["forex_broker"] == "YES":
        target["forex_broker"] = source["forex_broker"]
    confidence_rank = {"": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    if confidence_rank.get(source["classification_confidence"], 0) > confidence_rank.get(target["classification_confidence"], 0):
        target["classification_confidence"] = source["classification_confidence"]
    target["needs_review"] = "YES" if "YES" in {target["needs_review"], source["needs_review"]} else "NO"
    target["last_checked"] = max(target["last_checked"], source["last_checked"])


def classify_profile(profile: dict) -> None:
    identity_text = " ".join([profile["brand_name"], profile.get("directory_notes", ""), *[item.get("legal_name", "") for item in profile["legal_entities"]]]).lower()
    name_text = " ".join([profile["brand_name"], *[item.get("legal_name", "") for item in profile["legal_entities"]]]).lower()
    license_text = " ".join(item.get("license_type", "") for item in profile["licenses"]).lower()

    if re.search(r"\b(bank|banque|banca|credit union|building society)\b", name_text):
        company_type = "Bank / Financial Institution"
        reason = "The broker or legal-entity name identifies a bank or deposit-taking institution."
    elif re.search(r"\b(b2broker|brokeree|metaquotes|onezero|prime xm)\b|technology provider|software provider|liquidity provider|payment provider", identity_text):
        company_type = "Technology / Liquidity Provider"
        reason = "The available identity or directory description identifies a technology, payments, or liquidity provider."
    elif re.search(r"\bprop\b|funded trader|proprietary trading", identity_text):
        company_type = "Prop Firm"
        reason = "The available identity or directory description indicates proprietary or funded trading."
    elif profile["forex_broker"] == "YES" and "institutional" in identity_text and "retail" not in identity_text:
        company_type = "Institutional Broker"
        reason = "The source describes an institutional broker without a retail offering."
    elif profile["forex_broker"] == "YES":
        company_type = "Forex / CFD Broker"
        reason = "At least one imported source classifies this profile as a forex or CFD broker."
    elif "investment dealer" in license_text or "investment firm" in license_text:
        company_type = "Investment Firm / Dealer"
        reason = "The regulatory licence identifies an investment firm or investment dealer, but broker relevance is not confirmed."
    elif profile["forex_broker"] == "NO":
        company_type = "Non-broker Financial Company"
        reason = "The existing classification evidence does not identify this profile as a forex or CFD broker."
    else:
        company_type = "Needs Review"
        reason = "The available sources do not yet support a reliable company-type classification."

    profile["company_type"] = company_type
    profile["company_type_reason"] = reason
    if company_type == "Forex / CFD Broker" and any(item["vendor"] == "Trading Central" for item in profile["vendor_relationships"]):
        profile["sales_relevance"] = "HIGH"
    elif company_type in {"Forex / CFD Broker", "Institutional Broker", "Prop Firm", "Technology / Liquidity Provider"}:
        profile["sales_relevance"] = "MEDIUM"
    elif company_type == "Needs Review":
        profile["sales_relevance"] = "REVIEW"
    else:
        profile["sales_relevance"] = "LOW"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trading-central", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--brokerchooser", type=Path)
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--normalized-output", required=True, type=Path)
    parser.add_argument("--crosswalk-output", required=True, type=Path)
    parser.add_argument("--directory-normalized-output", type=Path)
    parser.add_argument("--directory-crosswalk-output", type=Path)
    parser.add_argument("--identity-audit-output", type=Path)
    parser.add_argument("--identity-merge-output", type=Path)
    parser.add_argument("--priority-verification", type=Path)
    args = parser.parse_args()

    tc_rows = read_csv(args.trading_central)
    registry_rows = read_csv(args.registry)
    brokerchooser_rows = read_csv(args.brokerchooser) if args.brokerchooser and args.brokerchooser.exists() else []
    directory_rows = read_csv(args.directory) if args.directory and args.directory.exists() else []
    verification_profiles = {}
    if args.priority_verification and args.priority_verification.exists():
        verification_payload = json.loads(args.priority_verification.read_text(encoding="utf-8"))
        verification_profiles = {item["slug"]: item for item in verification_payload.get("profiles", [])}

    profiles: list[dict] = []
    used_slugs: set[str] = set()
    tc_domain_map: dict[str, dict] = {}
    tc_name_map: dict[str, dict] = {}
    crosswalk: list[dict[str, str]] = []

    def unique_slug(name: str) -> str:
        base = slugify(name)
        candidate = base
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{base}-{suffix}"
            suffix += 1
        used_slugs.add(candidate)
        return candidate

    for row in tc_rows:
        brand = clean(row.get("broker_brand")) or clean(row.get("broker_name"))
        slug = unique_slug(brand)
        profile = new_profile(f"broker-{slug}", slug, brand, "Trading Central master")
        profile["broker_group"] = clean(row.get("broker_group"))
        profile["primary_domain"] = hostname(row.get("broker_domain"))
        profile["website_url"] = clean(row.get("broker_url")) or (f"https://{profile['primary_domain']}" if profile["primary_domain"] else "")
        profile["primary_market"] = clean(row.get("country_or_primary_market"))
        profile["vendor_relationships"].append(relationship(row))
        profile["last_checked"] = clean(row.get("date_checked"))
        add_domain(profile, profile["primary_domain"], profile["website_url"], "Trading Central master")
        profiles.append(profile)
        if profile["primary_domain"]:
            tc_domain_map[profile["primary_domain"]] = profile
        for alias in {brand, clean(row.get("broker_name")), clean(row.get("broker_group"))}:
            if norm_name(alias):
                tc_name_map[norm_name(alias)] = profile

    registry_unmatched: list[dict[str, str]] = []
    for row in registry_rows:
        matched_ids = {
            tc_domain_map[tc_domain]["id"]
            for source_domain in split_domains(row.get("approved_domains"))
            for tc_domain in tc_domain_map
            if source_domain == tc_domain or source_domain.endswith(f".{tc_domain}") or tc_domain.endswith(f".{source_domain}")
        }
        if len(matched_ids) == 1:
            matched_id = next(iter(matched_ids))
            profile = next(item for item in profiles if item["id"] == matched_id)
            add_registry_row(profile, row)
            crosswalk.append({
                "broker_name": profile["brand_name"],
                "broker_domain": profile["primary_domain"],
                "legal_name": clean(row.get("legal_name")),
                "regulator_code": clean(row.get("regulator_code")),
                "license_number": clean(row.get("license_number")),
                "match_method": "EXACT_DOMAIN",
                "match_confidence": "HIGH",
                "needs_review": "NO",
            })
        else:
            registry_unmatched.append(row)

    remaining_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in registry_unmatched:
        remaining_groups[norm_name(row.get("legal_name"))].append(row)
    for key, rows in sorted(remaining_groups.items(), key=lambda item: clean(item[1][0].get("legal_name")).lower()):
        brand = clean(rows[0].get("legal_name")) or "Unnamed regulated entity"
        slug = unique_slug(brand)
        profile = new_profile(f"broker-{slug}", slug, brand, "Official regulator registry")
        for row in rows:
            add_registry_row(profile, row)
        profile["primary_market"] = next((clean(row.get("jurisdiction")) for row in rows if clean(row.get("jurisdiction"))), "")
        profile["primary_domain"] = profile["domains"][0]["domain"] if profile["domains"] else ""
        profile["website_url"] = profile["domains"][0]["url"] if profile["domains"] else ""
        profiles.append(profile)

    by_name = {norm_name(profile["brand_name"]): profile for profile in profiles}
    for row in brokerchooser_rows:
        profile = tc_name_map.get(norm_name(row.get("broker_name"))) or by_name.get(norm_name(row.get("broker_name")))
        if not profile:
            continue
        if "BrokerChooser" not in profile["profile_sources"]:
            profile["profile_sources"].append("BrokerChooser")
        fx = clean(row.get("forex_broker"))
        if fx in {"YES", "NO"}:
            profile["forex_broker"] = fx
        if clean(row.get("needs_review")) == "NO":
            profile["needs_review"] = "NO"
        for regulator in split_values(row.get("regulators")):
            if regulator and not any(item["regulator_code"] == regulator or item["regulator_name"] == regulator for item in profile["licenses"]):
                profile["licenses"].append({
                    "regulator_code": regulator,
                    "regulator_name": regulator,
                    "jurisdiction": "",
                    "license_number": "",
                    "license_type": "Directory-reported regulator",
                    "status": "REPORTED",
                    "license_date": "",
                    "legal_name": "",
                    "evidence_url": clean(row.get("review_url")),
                    "evidence_status": "THIRD_PARTY",
                    "last_checked": clean(row.get("last_checked")),
                    "source": "BrokerChooser",
                })
        for entity in split_values(row.get("legal_entities")):
            if entity and not any(norm_name(item["legal_name"]) == norm_name(entity) for item in profile["legal_entities"]):
                profile["legal_entities"].append({"legal_name": entity, "jurisdiction": "", "status": "REPORTED", "source_url": clean(row.get("review_url"))})

    directory_crosswalk: list[dict[str, str]] = []
    for row in directory_rows:
        source_name = clean(row.get("broker_name"))
        source_domain = hostname(row.get("website"))
        source_name_key = norm_name(source_name)

        domain_candidates: dict[str, dict] = {}
        name_candidates: dict[str, dict] = {}
        for candidate in profiles:
            candidate_domains = {hostname(candidate.get("primary_domain"))}
            candidate_domains.update(hostname(item.get("domain")) for item in candidate.get("domains", []))
            candidate_domains.discard("")
            if source_domain and any(
                source_domain == candidate_domain
                or source_domain.endswith(f".{candidate_domain}")
                or candidate_domain.endswith(f".{source_domain}")
                for candidate_domain in candidate_domains
            ):
                domain_candidates[candidate["id"]] = candidate
            aliases = {norm_name(candidate.get("brand_name")), norm_name(candidate.get("broker_group"))}
            aliases.update(norm_name(item.get("legal_name")) for item in candidate.get("legal_entities", []))
            if source_name_key and source_name_key in aliases:
                name_candidates[candidate["id"]] = candidate

        profile = None
        method = ""
        if len(domain_candidates) == 1:
            profile = next(iter(domain_candidates.values()))
            method = "EXACT_OR_SUBDOMAIN"
        elif len(name_candidates) == 1:
            profile = next(iter(name_candidates.values()))
            method = "EXACT_NAME_OR_LEGAL_ENTITY"

        if profile is None:
            slug = unique_slug(source_name)
            profile = new_profile(f"broker-{slug}", slug, source_name, "Claude broker directory export")
            profile["forex_broker"] = "YES"
            profile["classification_confidence"] = "MEDIUM"
            profiles.append(profile)
            method = "NEW_PROFILE" if not domain_candidates and not name_candidates else "NEW_PROFILE_AMBIGUOUS_EXISTING"
        elif "Claude broker directory export" not in profile["profile_sources"]:
            profile["profile_sources"].append("Claude broker directory export")

        if source_domain:
            add_domain(profile, source_domain, clean(row.get("website")), "Claude broker directory export")
            if not profile["primary_domain"]:
                profile["primary_domain"] = source_domain
                profile["website_url"] = clean(row.get("website"))
        profile["headquarters"] = profile["headquarters"] or clean(row.get("hq_country"))
        profile["founded_year"] = profile["founded_year"] or clean(row.get("founded_year"))
        profile["directory_license_status"] = clean(row.get("license_status"))
        profile["directory_notes"] = clean(row.get("notes"))
        if not profile["primary_market"]:
            profile["primary_market"] = clean(row.get("hq_country"))
        if profile["forex_broker"] == "UNKNOWN":
            profile["forex_broker"] = "YES"
        if profile["classification_confidence"] == "LOW":
            profile["classification_confidence"] = "MEDIUM"

        hq_country = clean(row.get("hq_country"))
        if hq_country and not any(item.get("country") == hq_country and item.get("type") == "Headquarters" for item in profile["offices"]):
            profile["offices"].append({"country": hq_country, "city": "", "type": "Headquarters", "source": "Claude broker directory export"})

        for regulator in [item.strip() for item in clean(row.get("regulators")).split("|") if item.strip()]:
            if not any(item["regulator_code"] == regulator or item["regulator_name"] == regulator for item in profile["licenses"]):
                profile["licenses"].append({
                    "regulator_code": regulator,
                    "regulator_name": regulator,
                    "jurisdiction": "",
                    "license_number": "",
                    "license_type": "Directory-reported regulator",
                    "status": clean(row.get("license_status")) or "REPORTED",
                    "license_date": "",
                    "legal_name": "",
                    "evidence_url": clean(row.get("website")),
                    "evidence_status": "DIRECTORY_REPORTED",
                    "last_checked": "",
                    "source": "Claude broker directory export",
                })

        vendor_names = [item.strip() for item in clean(row.get("research_tool_vendors")).split("|") if item.strip()]
        for vendor in vendor_names:
            existing = next((item for item in profile["vendor_relationships"] if item["vendor"].lower() == vendor.lower()), None)
            if existing:
                existing["directory_support"] = {
                    "status": clean(row.get("research_tool_status")),
                    "notes": clean(row.get("research_tool_notes")),
                    "pages_checked": split_values(row.get("research_tool_pages_checked")),
                }
            else:
                profile["vendor_relationships"].append(directory_relationship(vendor, row))
        profile["research_scan"] = {
            "status": clean(row.get("research_tool_status")),
            "vendors": vendor_names,
            "notes": clean(row.get("research_tool_notes")),
            "pages_checked": split_values(row.get("research_tool_pages_checked")),
        }

        directory_crosswalk.append({
            "broker_name": source_name,
            "website": clean(row.get("website")),
            "profile_slug": profile["slug"],
            "action": "ADDED" if method.startswith("NEW_PROFILE") else "MERGED",
            "match_method": method,
            "reported_regulator_count": clean(row.get("regulator_count")),
            "research_tool_vendors": clean(row.get("research_tool_vendors")),
            "needs_review": "YES" if method == "NEW_PROFILE_AMBIGUOUS_EXISTING" else profile["needs_review"],
        })

    identity_merge_log: list[dict[str, str]] = []
    domain_groups: dict[str, list[dict]] = defaultdict(list)
    for profile in profiles:
        for domain in {item.get("domain", "") for item in profile["domains"] if item.get("domain")}:
            domain_groups[domain].append(profile)

    official_links: dict[str, dict[str, dict]] = defaultdict(dict)
    shared_domains: dict[str, set[str]] = defaultdict(set)
    for domain, domain_profiles in domain_groups.items():
        if len(domain_profiles) < 2:
            continue
        branded = [profile for profile in domain_profiles if is_brand_profile(profile)]
        official_only = [profile for profile in domain_profiles if not is_brand_profile(profile)]
        for source in official_only:
            for target in branded:
                official_links[source["id"]][target["id"]] = target
                shared_domains[source["id"]].add(domain)

    profiles_by_id = {profile["id"]: profile for profile in profiles}
    remove_ids: set[str] = set()
    for source_id, targets_by_id in official_links.items():
        source = profiles_by_id[source_id]
        targets = list(targets_by_id.values())
        if len(targets) == 1:
            target = targets[0]
            merge_profile_into(target, source)
            action = "MERGED_LEGAL_ENTITY_INTO_BRAND"
        else:
            for target in targets:
                append_unique(target["legal_entities"], source["legal_entities"], lambda item: (norm_name(item.get("legal_name")), item.get("jurisdiction", "")))
                append_unique(target["licenses"], source["licenses"], lambda item: (item.get("regulator_code", ""), item.get("license_number", ""), norm_name(item.get("legal_name"))))
                target["profile_sources"] = sorted(set(target["profile_sources"] + source["profile_sources"]))
            action = "LINKED_SHARED_LEGAL_ENTITY"
        remove_ids.add(source_id)
        identity_merge_log.append({
            "action": action,
            "source_profile": source["brand_name"],
            "source_slug": source["slug"],
            "target_profiles": " | ".join(target["brand_name"] for target in targets),
            "target_slugs": " | ".join(target["slug"] for target in targets),
            "shared_domains": " | ".join(sorted(shared_domains[source_id])),
        })
    profiles = [profile for profile in profiles if profile["id"] not in remove_ids]

    ambiguous_slugs = {item["profile_slug"] for item in directory_crosswalk if item["match_method"] == "NEW_PROFILE_AMBIGUOUS_EXISTING"}

    for profile in profiles:
        verification = verification_profiles.get(profile["slug"])
        if verification:
            profile["verification"] = {
                "scope": "PRIORITY_25",
                "status": verification["status"],
                "reported_regulators": verification["reported_regulators"],
                "verified_regulators": verification["verified_regulators"],
                "unresolved_regulators": verification["unresolved_regulators"],
                "notes": verification.get("notes", []),
                "last_verified": verification["last_verified"],
            }
            append_unique(
                profile["licenses"],
                verification.get("official_licenses", []),
                lambda item: (item.get("regulator_code", ""), item.get("license_number", ""), norm_name(item.get("legal_name"))),
            )
            for item in verification.get("official_licenses", []):
                legal_name = clean(item.get("legal_name"))
                entity_key = (norm_name(legal_name), clean(item.get("jurisdiction")))
                if legal_name and not any((norm_name(entity.get("legal_name")), entity.get("jurisdiction", "")) == entity_key for entity in profile["legal_entities"]):
                    profile["legal_entities"].append({
                        "legal_name": legal_name,
                        "jurisdiction": clean(item.get("jurisdiction")),
                        "status": clean(item.get("status")),
                        "source_url": clean(item.get("evidence_url")),
                    })
        else:
            profile["verification"] = {
                "scope": "NOT_YET_REVIEWED",
                "status": "NOT_REVIEWED",
                "reported_regulators": [],
                "verified_regulators": [],
                "unresolved_regulators": [],
                "notes": ["This profile is outside the current Priority 25 verification pilot."],
                "last_verified": "",
            }
        regulators: dict[str, dict] = {}
        for item in profile["licenses"]:
            code = item["regulator_code"] or item["regulator_name"]
            if not code:
                continue
            entry = regulators.setdefault(code, {"code": code, "name": item["regulator_name"], "jurisdictions": [], "license_count": 0, "official_license_count": 0})
            if item["jurisdiction"] and item["jurisdiction"] not in entry["jurisdictions"]:
                entry["jurisdictions"].append(item["jurisdiction"])
            entry["license_count"] += 1
            if item["source"] == "Official regulator registry":
                entry["official_license_count"] += 1
        profile["regulators"] = sorted(regulators.values(), key=lambda item: item["code"])
        profile["domains"] = sorted(profile["domains"], key=lambda item: item["domain"])
        profile["licenses"] = sorted(profile["licenses"], key=lambda item: (item["regulator_code"], item["license_number"], item["legal_name"]))
        if profile["vendor_relationships"] and profile["classification_confidence"] == "LOW":
            profile["classification_confidence"] = profile["vendor_relationships"][0]["confidence"]
        profile["identity_status"] = "NEEDS_REVIEW" if profile["slug"] in ambiguous_slugs else "CANONICAL"
        profile["identity_note"] = "Possible match to more than one existing profile; retained separately for review." if profile["slug"] in ambiguous_slugs else "Identity retained as a canonical broker or regulated-company profile."
        classify_profile(profile)

    eligible = [profile for profile in profiles if profile["sales_relevance"] in {"HIGH", "MEDIUM"}]
    for profile in eligible:
        tc = next((item for item in profile["vendor_relationships"] if item["vendor"] == "Trading Central"), None)
        official_count = sum(item["source"] == "Official regulator registry" for item in profile["licenses"])
        profile["priority_score"] = (
            (35 if tc and tc["status"] == "CONFIRMED_ACTIVE" else 28 if tc else 0)
            + (25 if profile["company_type"] == "Forex / CFD Broker" else 15)
            + min(20, len(profile["regulators"]) * 4)
            + (12 if official_count else 0)
            + (5 if profile["primary_domain"] else 0)
            + (3 if profile["headquarters"] else 0)
        )
    eligible.sort(key=lambda item: (-item["priority_score"], item["brand_name"].lower()))
    for rank, profile in enumerate(eligible, start=1):
        profile["priority_rank"] = rank
        profile["priority_tier"] = "PRIORITY_100" if rank <= 100 else "STANDARD"
    for profile in profiles:
        if "priority_rank" not in profile:
            profile["priority_score"] = 0
            profile["priority_rank"] = None
            profile["priority_tier"] = "NOT_SALES_TARGET"

    profiles.sort(key=lambda item: item["brand_name"].lower())
    payload = {
        "generated_at": date.today().isoformat(),
        "profile_count": len(profiles),
        "trading_central_count": sum(any(item["vendor"] == "Trading Central" for item in profile["vendor_relationships"]) for profile in profiles),
        "priority_verified_count": sum(profile.get("verification", {}).get("status") == "VERIFIED" for profile in profiles),
        "priority_partial_count": sum(profile.get("verification", {}).get("status") == "PARTIAL" for profile in profiles),
        "profiles": profiles,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    args.normalized_output.parent.mkdir(parents=True, exist_ok=True)
    with args.normalized_output.open("w", encoding="utf-8", newline="") as handle:
        fields = list(tc_rows[0].keys()) if tc_rows else []
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(tc_rows)

    args.crosswalk_output.parent.mkdir(parents=True, exist_ok=True)
    with args.crosswalk_output.open("w", encoding="utf-8", newline="") as handle:
        fields = ["broker_name", "broker_domain", "legal_name", "regulator_code", "license_number", "match_method", "match_confidence", "needs_review"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(crosswalk)

    if args.directory_normalized_output and directory_rows:
        args.directory_normalized_output.parent.mkdir(parents=True, exist_ok=True)
        with args.directory_normalized_output.open("w", encoding="utf-8", newline="") as handle:
            fields = list(directory_rows[0].keys())
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(directory_rows)

    if args.directory_crosswalk_output:
        args.directory_crosswalk_output.parent.mkdir(parents=True, exist_ok=True)
        with args.directory_crosswalk_output.open("w", encoding="utf-8", newline="") as handle:
            fields = ["broker_name", "website", "profile_slug", "action", "match_method", "reported_regulator_count", "research_tool_vendors", "needs_review"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(directory_crosswalk)

    if args.identity_merge_output:
        args.identity_merge_output.parent.mkdir(parents=True, exist_ok=True)
        with args.identity_merge_output.open("w", encoding="utf-8", newline="") as handle:
            fields = ["action", "source_profile", "source_slug", "target_profiles", "target_slugs", "shared_domains"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(identity_merge_log)

    if args.identity_audit_output:
        args.identity_audit_output.parent.mkdir(parents=True, exist_ok=True)
        with args.identity_audit_output.open("w", encoding="utf-8", newline="") as handle:
            fields = ["priority_rank", "brand_name", "slug", "company_type", "sales_relevance", "forex_broker", "primary_domain", "regulators", "legal_entity_count", "license_count", "research_tools", "identity_status", "needs_review", "classification_reason"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for profile in profiles:
                writer.writerow({
                    "priority_rank": profile["priority_rank"] or "",
                    "brand_name": profile["brand_name"],
                    "slug": profile["slug"],
                    "company_type": profile["company_type"],
                    "sales_relevance": profile["sales_relevance"],
                    "forex_broker": profile["forex_broker"],
                    "primary_domain": profile["primary_domain"],
                    "regulators": " | ".join(item["code"] for item in profile["regulators"]),
                    "legal_entity_count": len(profile["legal_entities"]),
                    "license_count": len(profile["licenses"]),
                    "research_tools": " | ".join(item["vendor"] for item in profile["vendor_relationships"]),
                    "identity_status": profile["identity_status"],
                    "needs_review": profile["needs_review"],
                    "classification_reason": profile["company_type_reason"],
                })

    tc_profiles = [profile for profile in profiles if any(item["vendor"] == "Trading Central" for item in profile["vendor_relationships"])]
    matched = sum(bool(profile["licenses"]) for profile in tc_profiles)
    print(json.dumps({
        "profiles": len(profiles),
        "trading_central_profiles": len(tc_profiles),
        "trading_central_with_regulatory_data": matched,
        "crosswalk_rows": len(crosswalk),
        "multi_regulated_profiles": sum(len(profile["regulators"]) > 1 for profile in profiles),
        "directory_rows": len(directory_rows),
        "directory_merged": sum(item["action"] == "MERGED" for item in directory_crosswalk),
        "directory_added": sum(item["action"] == "ADDED" for item in directory_crosswalk),
        "profiles_with_acuity": sum(any(item["vendor"] == "Acuity Trading" for item in profile["vendor_relationships"]) for profile in profiles),
        "profiles_with_autochartist": sum(any(item["vendor"] == "Autochartist" for item in profile["vendor_relationships"]) for profile in profiles),
        "identity_profiles_removed": len(remove_ids),
        "priority_100": sum(profile["priority_tier"] == "PRIORITY_100" for profile in profiles),
        "company_types": {company_type: sum(profile["company_type"] == company_type for profile in profiles) for company_type in sorted({profile["company_type"] for profile in profiles})},
    }))


if __name__ == "__main__":
    main()
