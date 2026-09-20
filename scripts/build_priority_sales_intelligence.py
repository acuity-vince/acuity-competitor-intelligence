#!/usr/bin/env python3
"""Build the reviewed Priority 100 sales-intelligence source layer.

The output deliberately separates first-party facts from sales hypotheses. Missing
leaders stay unresolved; technology relationships never become active without a
current first-party source.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


HQ = {
    "activtrades": ("London", "United Kingdom"),
    "admiral-markets-admirals": ("Tallinn", "Estonia"),
    "atfx": ("London", "United Kingdom"),
    "avatrade": ("Dublin", "Ireland"),
    "cfi-financial-group": ("Beirut", "Lebanon"),
    "easymarkets": ("Limassol", "Cyprus"),
    "etoro": ("London", "United Kingdom"),
    "exness": ("Limassol", "Cyprus"),
    "fortrade": ("London", "United Kingdom"),
    "fp-markets": ("Sydney", "Australia"),
    "fusion-markets": ("Melbourne", "Australia"),
    "fxcm": ("London", "United Kingdom"),
    "fxpro": ("Limassol", "Cyprus"),
    "hantec-financial-hantec-markets-asia": ("London", "United Kingdom"),
    "hycm": ("London", "United Kingdom"),
    "ironfx": ("Limassol", "Cyprus"),
    "markets-com": ("London", "United Kingdom"),
    "moneta-markets": ("Sydney", "Australia"),
    "naga": ("Hamburg", "Germany"),
    "vantage-vantage-markets": ("Sydney", "Australia"),
    "vt-markets": ("Sydney", "Australia"),
    "doto": ("Ebene", "Mauritius"),
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": ("Ebene", "Mauritius"),
    "plus500": ("Haifa", "Israel"),
    "just2trade": ("Limassol", "Cyprus"),
    "windsor-brokers": ("Limassol", "Cyprus"),
}

HQ_EVIDENCE = {
    "vt-markets": "https://www.vtmarkets.com/ms-asia/press-release/vt-markets-opens-a-new-office-in-malaysia/",
    "doto": "https://doto.com/en/about/",
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": "https://doto.com/en/about/",
    "plus500": "https://financialservices.plus500.com/about-us/",
    "just2trade": "https://j2t.com/fr/about/",
    "windsor-brokers": "https://windsorbrokers.com/company/legal/terms-conditions/",
}

HQ_STATUS = {
    "doto": "REGISTERED_OFFICE_CONFIRMED",
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": "REGISTERED_OFFICE_CONFIRMED",
    "windsor-brokers": "OPERATIONS_ADDRESS_CONFIRMED",
}

HQ_NOTE = {
    "vt-markets": "Broker-owned release describes VT Markets as based in Sydney.",
    "doto": "Current broker-owned legal disclosure identifies the registered office in Ebene.",
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": "Current broker-owned legal disclosure identifies the Doto Global registered office in Ebene; the profile retains the regulated-entity name for identity traceability.",
    "plus500": "The current Plus500 group locations page labels Haifa as headquarters.",
    "just2trade": "The current broker-owned company page identifies Limassol as the head office.",
    "windsor-brokers": "Current site terms identify the Limassol address for the website operator and payment entity; this is an operations address, not a confirmed group headquarters.",
}

OFFICES = {
    "activtrades": [("London", "United Kingdom"), ("Nassau", "The Bahamas"), ("Lisbon", "Portugal"), ("Port Louis", "Mauritius")],
    "atfx": [("London", "United Kingdom"), ("Limassol", "Cyprus"), ("Dubai", "United Arab Emirates"), ("Johannesburg", "South Africa")],
    "cfi-financial-group": [("Beirut", "Lebanon"), ("Dubai", "United Arab Emirates"), ("London", "United Kingdom"), ("Larnaca", "Cyprus")],
    "etoro": [("London", "United Kingdom"), ("Tel Aviv", "Israel"), ("Limassol", "Cyprus")],
    "fxcm": [("London", "United Kingdom"), ("Limassol", "Cyprus"), ("Johannesburg", "South Africa")],
    "fxpro": [("Limassol", "Cyprus"), ("London", "United Kingdom"), ("Monaco", "Monaco")],
    "hantec-financial-hantec-markets-asia": [("London", "United Kingdom"), ("Dubai", "United Arab Emirates"), ("Hong Kong", "Hong Kong"), ("Sydney", "Australia"), ("Sao Paulo", "Brazil"), ("Hanoi", "Vietnam"), ("Santiago", "Chile"), ("Kigali", "Rwanda"), ("Bangkok", "Thailand")],
    "hycm": [("London", "United Kingdom"), ("Limassol", "Cyprus"), ("Dubai", "United Arab Emirates")],
    "doto": [("Ebene", "Mauritius"), ("Limassol", "Cyprus")],
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": [("Ebene", "Mauritius"), ("Limassol", "Cyprus")],
    "fp-markets": [("Sydney", "Australia"), ("Rodney Bay", "Saint Lucia")],
    "fusion-markets": [("Melbourne", "Australia"), ("Port Vila", "Vanuatu"), ("Mahe", "Seychelles")],
    "just2trade": [("Limassol", "Cyprus")],
    "markets-com": [("London", "United Kingdom"), ("Nicosia", "Cyprus")],
    "moneta-markets": [("Cape Town", "South Africa"), ("Ebene", "Mauritius"), ("Limassol", "Cyprus"), ("Hong Kong", "Hong Kong"), ("London", "United Kingdom")],
    "plus500": [("Haifa", "Israel"), ("Tel Aviv", "Israel"), ("London", "United Kingdom"), ("Limassol", "Cyprus"), ("Tallinn", "Estonia"), ("Sofia", "Bulgaria"), ("Chicago", "United States"), ("Nassau", "The Bahamas"), ("Dubai", "United Arab Emirates"), ("Tokyo", "Japan"), ("Singapore", "Singapore"), ("Sydney", "Australia"), ("Melbourne", "Australia")],
    "vt-markets": [("Sydney", "Australia"), ("Kuala Lumpur", "Malaysia"), ("Johannesburg", "South Africa"), ("Port Louis", "Mauritius"), ("Limassol", "Cyprus")],
    "windsor-brokers": [("Limassol", "Cyprus"), ("Amman", "Jordan"), ("Mahe", "Seychelles"), ("Nairobi", "Kenya")],
}

OFFICE_EVIDENCE = {
    "doto": "https://doto.com/en/about/",
    "doto-europe-ltd-ex-vasby-capital-markets-ltd": "https://doto.com/en/about/",
    "fp-markets": "https://www.fpmarkets.com/about-us/",
    "fusion-markets": "https://fusionmarkets.com/About-us/Who-we-are",
    "hantec-financial-hantec-markets-asia": "https://www.hantecgroup.com/en/about-us",
    "just2trade": "https://j2t.com/fr/about/",
    "markets-com": "https://www.markets.com/about/",
    "moneta-markets": "https://help.monetamarkets.com/hc/en-us/articles/55892178454937-Who-is-Moneta-Markets",
    "plus500": "https://financialservices.plus500.com/about-us/",
    "vt-markets": "https://www.vtmarkets.com/ms-asia/press-release/vt-markets-opens-a-new-office-in-malaysia/",
    "windsor-brokers": "https://windsorbrokers.com/company/contact/",
}

PEOPLE = {
    "activtrades": [("Alex Pusco", "Chief Executive Officer", "https://partners.activtrades.com/en/about-us")],
    "admiral-markets-admirals": [("Alexander Tsikhilov", "Chairman of the Management Board", "https://view.news.eu.nasdaq.com/view?id=bdc346902821d9af74af2774e4b3bed38&lang=en&src=listed")],
    "atfx": [
        ("Joe Li", "Chairman", "https://www.atfx.com/en/about-us/company-news/atfx-chairman-joe-li-message-2025-stronger-2026"),
        ("Dany Mawas", "Chief Executive Officer, Africa", "https://www.atfx.com/en/about-us/company-news/atfx-deepens-regional-expansion-with-appointment-of-dany-mawas-as-ceo-africa"),
        ("Siju Daniel", "Chief Commercial Officer", "https://www.atfx.com/en/about-us/company-news/atfx-deepens-regional-expansion-with-appointment-of-dany-mawas-as-ceo-africa"),
    ],
    "avatrade": [("Dáire Ferguson", "Chief Executive Officer", "https://www.avatrade.com/about-avatrade/management")],
    "cfi-financial-group": [
        ("Ziad Melhem", "Chief Executive Officer", "https://cfi.trade/en/bh/company/leadership"),
        ("Omar Khaled", "Chief Marketing Officer", "https://cfi.trade/en/bh/company/leadership"),
        ("Ahmad Khatib", "Chief Business Development Officer", "https://cfi.trade/en/bh/company/leadership"),
    ],
    "easymarkets": [("Nikos Antoniades", "Chief Executive Officer", "https://www.easymarkets.com/eu/why-us/")],
    "etoro": [
        ("Yoni Assia", "Co-founder and Chief Executive Officer", "https://www.etoro.com/en-us/about/team/"),
        ("Nir Szmulewicz", "Chief Marketing Officer", "https://www.etoro.com/en-us/about/team/"),
        ("Tuval Chomut", "Chief Solutions Officer", "https://www.etoro.com/en-us/about/team/"),
    ],
    "exness": [("Petr Valov", "Founder and Chief Executive Officer", "https://www.exness.com/about-us/")],
    "fp-markets": [("Craig Allison", "Chief Executive Officer", "https://www.fpmarkets.com/blog/fp-markets-recognised-for-best-trading-conditions-and-transparency-at-uf-awards-2025/")],
    "fusion-markets": [("Phil Horner", "Founder and Chief Executive Officer", "https://fusionmarkets.com/About-us/Who-we-are")],
    "fxcm": [("Brendan Callan", "Chief Executive Officer", "https://www.fxcm.com/uk/about-fxcm/executive-team/")],
    "fxpro": [("Charalambos Psimolophitis", "Chief Executive Officer", "https://www.fxpro.com/about")],
    "hantec-financial-hantec-markets-asia": [("Freddy Lau", "Global Chief Executive Officer", "https://www.hantecgroup.com/en/happenings/20250101")],
    "markets-com": [("Stavros Anastasiou", "Chief Executive Officer", "https://www.markets.com/za/awards-and-media/articles/media-highlights/")],
    "moneta-markets": [("David Bily", "Founder and Chief Executive Officer", "https://www.monetamarkets.com/about-us/moneta-media/")],
    "naga": [("Octavian Patrascu", "Chief Executive Officer", "https://group.naga.com/newsroom/naga-group-reports-first-profitable-q1-with-improved-ebitda-margin-2026-guidance-reiterated")],
    "plus500": [("David Zruia", "Chief Executive Officer", "https://www.plus500.com/investors/corporate-governance/board-of-directors")],
    "vantage-vantage-markets": [("Marc Despallieres", "Chief Executive Officer", "https://www.vantagemarkets.com/press-releases/vantage-delivers-a-stellar-showcase-at-ifx-expo-dubai-2025/")],
    "vt-markets": [("Ross Maxwell", "Chief Strategy Officer", "https://www.vtmarkets.com/fr-ca/press-release/vt-markets-appoints-ross-maxwell-as-chief-strategy-officer-to-accelerate-global-growth/")],
    "windsor-brokers": [("Johny Abuaitah", "Chief Executive Officer", "https://windsorbrokers.com/company/")],
}

PEOPLE_STATUS = {
    "fxcm": "LAST_CONFIRMED",
}

PEOPLE_NOTE = {
    "fxcm": "The latest broker-owned leadership evidence located in this pass is historical; confirm the current role before outreach.",
}

TECH_OVERRIDES = {
    "vantage-vantage-markets": ("Autochartist", "CONFIRMED_ACTIVE", "HIGH", "https://plus.vantagemarkets.com/traders-tool-city/premium-tools/trading-edge-plus/"),
    "moneta-markets": ("Autochartist", "CONFIRMED_ACTIVE", "HIGH", "https://www.monetamarkets.com/trading-tools/autochartist/"),
    "markets-com": ("Trading Central", "UNKNOWN", "LOW", "https://www.markets.com/trading-tools/trading-central/"),
    "fxcm": ("Trading Central", "DIRECTORY_REPORTED", "MEDIUM", "https://www.financemagnates.com/forex/brokers/fxcm-integrates-trading-central-analytics/"),
    "just2trade": ("Trading Central", "DIRECTORY_REPORTED", "MEDIUM", "https://tradingcentral.com/broker/just2trade/"),
}

SIGNALS = {
    "admiral-markets-admirals": ("2026-04-30", "CORPORATE", "Admirals published its audited 2025 annual report after a year of operational realignment.", "Ask which parts of the research stack remain strategic after the operational realignment and who owns the next review.", "https://view.news.eu.nasdaq.com/view?id=bdc346902821d9af74af2774e4b3bed38&lang=en&src=listed"),
    "atfx": ("2026-05-25", "LEADERSHIP", "ATFX appointed Dany Mawas as CEO for Africa while expanding regional leadership.", "Ask how the Africa leadership team will measure trader use of research tools, and who owns the next vendor review.", "https://www.atfx.com/en/about-us/company-news/atfx-deepens-regional-expansion-with-appointment-of-dany-mawas-as-ceo-africa"),
    "cfi-financial-group": ("2026-09-02", "LEADERSHIP", "CFI appointed Federico Cirulli as chairman as the group entered a new growth phase.", "Ask whether the growth plan includes a research-stack review, then route the conversation through the named commercial or marketing owner.", "https://cfi.trade/en/vu/company/media-center/cfi-appoints-federico-cirulli-as-chairman-as-group-enters-next-phase-of-growth"),
    "etoro": ("2026-04-14", "PRODUCT", "eToro announced an AI app ecosystem, creating a timely opening around differentiated intelligence delivery.", "Ask how the AI app ecosystem will source external market intelligence and how eToro will measure its use.", "https://www.etoro.com/about/media-center/"),
    "windsor-brokers": ("2026-09-14", "REGULATORY", "CySEC licence 030/04 is active under WB Trade EU Ltd, formerly Windsor Brokers Ltd. The record is a historical Windsor relationship rather than a current Windsor licence.", "Confirm the current commercial owner at WB Trade before discussing research technology. The Windsor brand mapping is historical.", "https://www.cysec.gov.cy/en-GB/entities/investment-firms/cypriot/37569/"),
    "fp-markets": ("2026-09-09", "REGULATORY", "FP Markets reports Mauritius licence GB21026264, but exact-name searches of the FSC Mauritius register returned no result on 9 September 2026.", "Start with the entity mismatch. Ask the compliance or partnership owner to confirm the Mauritius entity before treating the account as fully resolved.", "https://www.fscmauritius.org/en/supervision/register-of-licensees"),
    "hantec-financial-hantec-markets-asia": ("2025", "OFFICE_OR_MARKET_EXPANSION", "Hantec's current group timeline records the opening of a Southeast Asia regional office in Bangkok in 2025.", "Ask how the Bangkok expansion changes regional content coverage and who owns research-tool adoption across Southeast Asia.", "https://www.hantecgroup.com/en/about-us"),
    "naga": ("2026-04-23", "CORPORATE", "NAGA reported its first profitable first quarter and reiterated plans to expand AI tools and white-label services.", "Ask where external market intelligence fits alongside NAGA's AI and white-label roadmap, and who owns the commercial evaluation.", "https://group.naga.com/newsroom/naga-group-reports-first-profitable-q1-with-improved-ebitda-margin-2026-guidance-reiterated"),
    "plus500": ("2026-08-10", "CORPORATE", "Plus500 published its H1 2026 results, creating a current planning window for product and research priorities.", "Use the H1 planning cycle to identify the owner of customer research tools and the next technology review date.", "https://cdn-investors.plus500.com/Reports/Presentation"),
    "vt-markets": ("2026-09-03", "LEADERSHIP", "VT Markets appointed Ross Maxwell as Chief Strategy Officer to accelerate global growth.", "Ask how the global-growth plan will change regional research coverage and which executive owns the next vendor review.", "https://www.vtmarkets.com/fr-ca/press-release/vt-markets-appoints-ross-maxwell-as-chief-strategy-officer-to-accelerate-global-growth/"),
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    options = args()
    payload = json.loads(options.profiles.read_text(encoding="utf-8"))
    rows = sorted(
        (row for row in payload["profiles"] if row.get("priority_tier") == "PRIORITY_100"),
        key=lambda row: row.get("priority_rank") or 9999,
    )
    today = date.today().isoformat()
    output = []
    for row in rows:
        slug = row["slug"]
        source = row.get("website_url") or row.get("primary_domain") or ""
        directory_hq = row.get("headquarters", "")
        if "," in directory_hq:
            directory_city, directory_country = (part.strip() for part in directory_hq.split(",", 1))
        else:
            directory_city, directory_country = "", directory_hq
        hq_city, hq_country = HQ.get(slug, (directory_city, directory_country))
        office_rows = OFFICES.get(slug, [(hq_city, hq_country)] if hq_country else [])
        hq_source = HQ_EVIDENCE.get(slug, source)
        office_source = OFFICE_EVIDENCE.get(slug, hq_source)
        people = [
            {"name": name, "title": title, "role_type": "LEADERSHIP", "status": PEOPLE_STATUS.get(slug, "CONFIRMED_CURRENT"), "confidence": "HIGH" if slug not in PEOPLE_STATUS else "MEDIUM", "evidence_url": url, "checked_date": today, "note": PEOPLE_NOTE.get(slug, "")}
            for name, title, url in PEOPLE.get(slug, [])
        ]
        if not people:
            people = [{"name": "", "title": "CEO / senior commercial leader", "role_type": "LEADERSHIP", "status": "UNRESOLVED", "confidence": "LOW", "evidence_url": "", "checked_date": today, "note": "No current first-party leadership disclosure was located in this pass."}]

        assessments = []
        for relationship in row.get("vendor_relationships", []):
            if relationship.get("vendor") not in {"Trading Central", "Autochartist", "Acuity Trading"}:
                continue
            status = relationship.get("status", "UNKNOWN")
            if status == "UNCLEAR":
                status = "UNKNOWN"
            assessments.append({
                "vendor": relationship["vendor"], "status": status,
                "confidence": relationship.get("confidence", "LOW"),
                "evidence_url": relationship.get("evidence_url", ""),
                "checked_date": relationship.get("last_checked", today),
                "note": relationship.get("summary", relationship.get("description", "")),
            })
        override = TECH_OVERRIDES.get(slug)
        if override:
            vendor, status, confidence, url = override
            assessments = [item for item in assessments if item["vendor"] != vendor]
            note = "The previously reported broker-owned product URL returned HTTP 404 in the monitoring baseline; current use remains unconfirmed." if status == "UNKNOWN" else "Current broker-owned product page located in this pass."
            assessments.append({"vendor": vendor, "status": status, "confidence": confidence, "evidence_url": url, "checked_date": today, "note": note})

        is_gold = row.get("verification", {}).get("scope") == "PRIORITY_25"
        verified_claims = row.get("canonical_regulatory_footprint", {}).get("regulator_claims", [])
        verified_codes = [item.get("regulator_code") for item in verified_claims if item.get("status") == "VERIFIED_ACTIVE"]
        reported_codes = [item.get("code") for item in row.get("regulators", []) if item.get("code")]
        active_tools = [item["vendor"] for item in assessments if item["status"] in {"CONFIRMED_ACTIVE", "LIKELY_ACTIVE"}]
        cited_sources = [item.get("evidence_url") for item in assessments if item.get("evidence_url")]
        cited_sources += [person.get("evidence_url") for person in people if person.get("evidence_url")]
        signal = SIGNALS.get(slug)
        if signal:
            cited_sources.append(signal[4])
            why_now = signal[2]
            discovery = signal[3]
        elif active_tools:
            tool_text = " and ".join(active_tools)
            brand = row["brand_name"]
            variants = [
                f"Broker-owned evidence confirms {tool_text} in {brand}'s current research stack. Ask about renewal timing and gaps in trader engagement.",
                f"{brand} currently documents {tool_text}. The account is competitive today, so check the next review date and weak coverage areas.",
                f"{brand}'s current stack includes {tool_text}. Verify who owns its performance and whether the team has an active review window.",
                f"Current evidence shows {tool_text} at {brand}. A focused first call should test renewal timing and the case for a complementary feed.",
            ]
            why_now = variants[(row.get("priority_rank") or 0) % len(variants)]
            discovery_variants = [
                f"Start with {', '.join(verified_codes[:3]) or 'the broker group'}. Who owns research-tool adoption at {brand}, and what would trigger a vendor review?",
                f"Ask how {brand} measures use of its current research tools. Then confirm the date and owner of the next vendor review.",
                f"Find the commercial owner for research across {', '.join(verified_codes[:3]) or 'the broker group'}. Ask where {brand}'s current feed loses trader attention.",
                f"Use {brand}'s current vendor evidence in the first call. Confirm whether the immediate need is better coverage or a replacement.",
            ]
            discovery = discovery_variants[(row.get("priority_rank") or 0) % len(discovery_variants)]
        elif is_gold:
            why_now = f"{row['brand_name']} has {len(verified_codes)} verified regulator relationship{'s' if len(verified_codes) != 1 else ''}. Current use of Trading Central, Autochartist and Acuity is unconfirmed, so the first job is to establish the stack."
            discovery = f"Ask which research feeds are live at {row['brand_name']} today and who owns their performance."
        else:
            footprint = ", ".join(reported_codes[:3]) or "a reported broker footprint"
            why_now = f"{row['brand_name']} is a Priority 100 account with {footprint} in the normalized registry. No current first-party vendor evidence has been confirmed yet."
            discovery = f"Confirm the active legal entity and research stack at {row['brand_name']}, then identify the owner and timing of the next vendor review."

        output.append({
            "priority_rank": row.get("priority_rank"), "slug": slug, "brand_name": row["brand_name"],
            "status": "EVIDENCE_BACKED" if is_gold else "EVIDENCE_BACKED_HYPOTHESIS", "last_checked": today, "hypothesis": True,
            "headquarters": {"city": hq_city, "country": hq_country, "status": HQ_STATUS.get(slug, "CONFIRMED" if slug in HQ else "DIRECTORY_REPORTED"), "confidence": "HIGH" if slug in HQ else "LOW", "evidence_url": hq_source, "checked_date": today, "note": HQ_NOTE.get(slug, "")},
            "offices": [{"city": city, "country": country, "status": "CONFIRMED", "confidence": "MEDIUM", "evidence_url": office_source, "checked_date": today} for city, country in office_rows],
            "people": people, "technology_assessment": assessments,
            "why_now": why_now, "discovery_angle": discovery,
            "sources": sorted(set(filter(None, cited_sources + ([source, hq_source, office_source] if source else [hq_source, office_source])))),
            "change_history": [] if not signal else [{"date": signal[0], "category": signal[1], "summary": signal[2], "evidence_url": signal[4]}],
        })
    result = {"generated_at": today, "methodology": "First-party and official sources are kept separate from normalized registry evidence; unresolved fields remain explicit; sales angles are hypotheses.", "profiles": output}
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output)} Priority 100 intelligence records to {options.output}")


if __name__ == "__main__":
    main()
