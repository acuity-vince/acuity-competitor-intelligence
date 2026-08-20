import csv
from pathlib import Path


HEADERS = (
    "legal_name", "company_number", "country", "regulator", "jurisdiction",
    "license_number", "license_type", "status", "source_status", "license_date",
    "termination_date", "approved_domains", "source_url", "first_seen", "last_seen",
)


def export_registry(db, output_path):
    rows = db.connection.execute("""
        SELECT e.legal_name,e.company_number,e.country,r.name regulator,r.jurisdiction,
        l.license_number,l.license_type,l.normalized_status status,l.source_status,
        l.license_date,l.termination_date,
        group_concat(d.domain, '; ') approved_domains,l.source_url,l.first_seen,l.last_seen
        FROM regulatory_licenses l
        JOIN legal_entities e ON e.id=l.legal_entity_id
        JOIN regulators r ON r.id=l.regulator_id
        LEFT JOIN regulated_domains d ON d.legal_entity_id=e.id AND d.regulator_id=l.regulator_id AND d.active=1
        GROUP BY l.id ORDER BY e.legal_name,r.name
    """).fetchall()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return path
