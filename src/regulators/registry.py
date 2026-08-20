import json
import re

from ..utils.dates import utc_now
from ..utils.hashing import sha256


REGULATORS = {
    "cysec": ("Cyprus Securities and Exchange Commission", "Cyprus", "https://www.cysec.gov.cy/en-GB/entities/investment-firms/"),
    "fca": ("Financial Conduct Authority", "United Kingdom", "https://register.fca.org.uk/"),
    "asic": ("Australian Securities and Investments Commission", "Australia", "https://register.asic.gov.au/"),
    "fsca": ("Financial Sector Conduct Authority", "South Africa", "https://www.fsca.co.za/FSB-Search/"),
    "fsc_mauritius": ("Financial Services Commission Mauritius", "Mauritius", "https://www.fscmauritius.org/"),
}


def _entity_key(name: str) -> str:
    return re.sub(r"\W+", " ", name).strip().casefold()


class Registry:
    def __init__(self, db):
        self.db = db

    def ingest(self, regulator_id, records, snapshots):
        now = utc_now()
        name, jurisdiction, register_url = REGULATORS[regulator_id]
        self.db.connection.execute(
            """INSERT INTO regulators(id,name,jurisdiction,register_url,created_at,updated_at)
            VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,
            jurisdiction=excluded.jurisdiction,register_url=excluded.register_url,updated_at=excluded.updated_at""",
            (regulator_id, name, jurisdiction, register_url, now, now),
        )
        for kind, url, content, count in snapshots:
            self.db.connection.execute(
                "INSERT INTO regulatory_snapshots(regulator_id,source_kind,source_url,captured_at,content_hash,record_count) VALUES (?,?,?,?,?,?)",
                (regulator_id, kind, url, now, sha256(content), count),
            )

        seen = set()
        counts = {"records": 0, "new_licenses": 0, "status_changes": 0, "domains": 0, "missing": 0}
        for record in records:
            entity_id = self._upsert_entity(record, now)
            existing = self.db.connection.execute(
                "SELECT * FROM regulatory_licenses WHERE regulator_id=? AND license_number=?",
                (regulator_id, record.license_number),
            ).fetchone()
            license_id = self._upsert_license(record, entity_id, now)
            seen.add(record.license_number)
            counts["records"] += 1
            if existing is None:
                counts["new_licenses"] += 1
                self._event(regulator_id, entity_id, license_id, "LICENSE_DISCOVERED", None, record.normalized_status, record.source_url, now)
            elif existing["normalized_status"] != record.normalized_status:
                counts["status_changes"] += 1
                self._event(regulator_id, entity_id, license_id, "LICENSE_STATUS_CHANGED", existing["normalized_status"], record.normalized_status, record.source_url, now)
            counts["domains"] += self._upsert_domains(record, entity_id, now)

        current = self.db.connection.execute(
            "SELECT * FROM regulatory_licenses WHERE regulator_id=?", (regulator_id,)
        ).fetchall()
        for license_row in current:
            if license_row["license_number"] in seen:
                continue
            missing_count = license_row["missing_count"] + 1
            self.db.connection.execute(
                "UPDATE regulatory_licenses SET missing_count=? WHERE id=?", (missing_count, license_row["id"])
            )
            counts["missing"] += 1
            self._event(regulator_id, license_row["legal_entity_id"], license_row["id"], "MISSING_FROM_SOURCE", str(license_row["missing_count"]), str(missing_count), license_row["source_url"], now)

        self.db.connection.commit()
        return counts

    def _upsert_entity(self, record, now):
        if record.company_number:
            row = self.db.connection.execute(
                "SELECT id FROM legal_entities WHERE country=? AND company_number=?",
                (record.country, record.company_number),
            ).fetchone()
        else:
            row = self.db.connection.execute(
                "SELECT id FROM legal_entities WHERE country=? AND lower(legal_name)=lower(?)",
                (record.country, record.legal_name),
            ).fetchone()
        if row:
            self.db.connection.execute(
                "UPDATE legal_entities SET legal_name=?,updated_at=? WHERE id=?",
                (record.legal_name, now, row["id"]),
            )
            return row["id"]
        cursor = self.db.connection.execute(
            "INSERT INTO legal_entities(legal_name,company_number,country,created_at,updated_at) VALUES (?,?,?,?,?)",
            (record.legal_name, record.company_number, record.country, now, now),
        )
        return cursor.lastrowid

    def _upsert_license(self, record, entity_id, now):
        self.db.connection.execute(
            """INSERT INTO regulatory_licenses(regulator_id,legal_entity_id,license_number,license_type,
            normalized_status,source_status,license_date,termination_date,source_url,first_seen,last_seen,missing_count)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(regulator_id,license_number) DO UPDATE SET
            legal_entity_id=excluded.legal_entity_id,license_type=excluded.license_type,
            normalized_status=excluded.normalized_status,source_status=excluded.source_status,
            license_date=excluded.license_date,termination_date=excluded.termination_date,
            source_url=excluded.source_url,last_seen=excluded.last_seen,missing_count=0""",
            (record.regulator_id, entity_id, record.license_number, record.license_type,
             record.normalized_status, record.source_status, record.license_date,
             record.termination_date, record.source_url, now, now),
        )
        return self.db.connection.execute(
            "SELECT id FROM regulatory_licenses WHERE regulator_id=? AND license_number=?",
            (record.regulator_id, record.license_number),
        ).fetchone()["id"]

    def _upsert_domains(self, record, entity_id, now):
        count = 0
        for domain in record.domains:
            existing = self.db.connection.execute(
                "SELECT id FROM regulated_domains WHERE regulator_id=? AND legal_entity_id=? AND domain=?",
                (record.regulator_id, entity_id, domain),
            ).fetchone()
            self.db.connection.execute(
                """INSERT INTO regulated_domains(legal_entity_id,regulator_id,domain,source_url,first_seen,last_seen,active)
                VALUES (?,?,?,?,?,?,1) ON CONFLICT(regulator_id,legal_entity_id,domain) DO UPDATE SET
                last_seen=excluded.last_seen,source_url=excluded.source_url,active=1""",
                (entity_id, record.regulator_id, domain, record.source_url, now, now),
            )
            count += int(existing is None)
        return count

    def _event(self, regulator_id, entity_id, license_id, event_type, previous, current, source_url, now):
        key = sha256(json.dumps([regulator_id, license_id, event_type, previous, current], sort_keys=True))
        self.db.connection.execute(
            """INSERT OR IGNORE INTO regulatory_events(regulator_id,legal_entity_id,license_id,event_type,
            previous_value,current_value,source_url,detected_at,event_key) VALUES (?,?,?,?,?,?,?,?,?)""",
            (regulator_id, entity_id, license_id, event_type, previous, current, source_url, now, key),
        )
