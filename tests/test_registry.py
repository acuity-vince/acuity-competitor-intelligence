from src.regulators.cysec import attach_domains, parse_domains, parse_firms
from src.regulators.models import RegulatoryRecord
from src.regulators.registry import Registry
from src.reports.registry_export import export_registry


CURRENT = """
<main>
  <div class="entity-card"><a href="/firm/1">Alpha Markets Ltd</a>
    <p>Licence Number: 111/11</p><p>Licence Date: 01/02/2011</p>
    <p>Company Registration Number: HE 123456</p><p>Country: Cyprus</p>
  </div>
  <div class="entity-card"><a href="/firm/2">Beta EU Ltd</a>
    <p>Licence Number: 222/22 (Under examination for voluntary renunciation of the authorisation)</p>
    <p>Licence Date: 02/03/2022</p><p>Company Registration Number: 654321</p>
  </div>
</main>
"""

FORMER = """
<main><div class="entity-card"><a href="/firm/3">Former Broker Ltd</a>
  <p>Licence Number: 333/13 (Voluntary Renunciation)</p><p>Licence Date: 03/04/2013</p>
  <p>Date of Termination: 05/06/2020</p><p>Company Registration Number: 987654</p>
</div></main>
"""

DOMAINS = """
<table><tr><th>#</th><th>Regulated Entity</th><th>Domains</th></tr>
<tr><td>1.</td><td>Alpha Markets Ltd</td><td>www.alpha.example; trade.alpha.example</td></tr>
<tr><td>2.</td><td>Beta EU Ltd</td><td>https://beta.example/eu/</td></tr></table>
"""


def test_cysec_parses_current_former_and_domains():
    current = attach_domains(parse_firms(CURRENT), parse_domains(DOMAINS))
    former = parse_firms(FORMER, former=True)
    assert [record.license_number for record in current] == ["111/11", "222/22"]
    assert current[0].domains == ("alpha.example", "trade.alpha.example")
    assert current[1].normalized_status == "SURRENDER_PENDING"
    assert former[0].normalized_status == "VOLUNTARILY_CANCELLED"
    assert former[0].termination_date == "05/06/2020"


def test_registry_ingest_is_idempotent_and_exports(db, tmp_path):
    current = attach_domains(parse_firms(CURRENT), parse_domains(DOMAINS))
    former = parse_firms(FORMER, former=True)
    snapshots = [
        ("CURRENT", "https://example/current", CURRENT, len(current)),
        ("FORMER", "https://example/former", FORMER, len(former)),
        ("DOMAINS", "https://example/domains", DOMAINS, 2),
    ]
    first = Registry(db).ingest("cysec", [*current, *former], snapshots)
    second = Registry(db).ingest("cysec", [*current, *former], snapshots)
    assert first["new_licenses"] == 3
    assert second["new_licenses"] == 0
    assert db.connection.execute("SELECT count(*) FROM regulatory_licenses").fetchone()[0] == 3
    assert db.connection.execute("SELECT count(*) FROM regulatory_events").fetchone()[0] == 3
    output = export_registry(db, tmp_path / "registry.csv")
    assert "Alpha Markets Ltd" in output.read_text(encoding="utf-8-sig")


def test_missing_record_is_review_event_not_status_change(db):
    record = RegulatoryRecord(
        regulator_id="cysec", legal_name="Alpha Markets Ltd", license_number="111/11",
        normalized_status="ACTIVE", source_status="Current investment firm",
        source_url="https://example/current", company_number="123456", country="Cyprus",
    )
    snapshots = [("CURRENT", "https://example/current", "one", 1)]
    Registry(db).ingest("cysec", [record], snapshots)
    result = Registry(db).ingest("cysec", [], [("CURRENT", "https://example/current", "empty", 0)])
    row = db.connection.execute("SELECT normalized_status,missing_count FROM regulatory_licenses").fetchone()
    assert result["missing"] == 1
    assert tuple(row) == ("ACTIVE", 1)
    assert db.connection.execute("SELECT event_type FROM regulatory_events ORDER BY id DESC LIMIT 1").fetchone()[0] == "MISSING_FROM_SOURCE"
