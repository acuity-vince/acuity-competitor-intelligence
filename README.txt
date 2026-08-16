ACUITY COMPETITOR INTELLIGENCE V1

Evidence-first monitoring of public broker pages and Trading Central announcements.
V1 covers Trading Central only. LinkedIn, authenticated collection, HubSpot, outreach,
other competitors and all later-phase capabilities are excluded.

QUICK START

  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  python -m src.main init-db
  python -m src.main scan-brokers --fixture-dir tests/fixtures/brokers
  python -m src.main scan-announcements --fixture tests/fixtures/tradingcentral/news.html
  python -m src.main weekly-report
  pytest -q

On macOS/Linux, activate with: source .venv/bin/activate

LIVE COLLECTION

Replace the disabled sample record in config/brokers.yaml with approved public broker
domains, then run scan-brokers without --fixture-dir. The collector checks robots.txt,
sitemaps and configured research URLs, caps each broker at 25 pages, identifies itself,
waits two seconds between requests per domain, retries temporary HTTP failures only,
and records access failures. It does not bypass restrictions.

COMMANDS

  python -m src.main init-db [--db PATH]
  python -m src.main scan-brokers [--db PATH] [--fixture-dir PATH]
  python -m src.main scan-announcements [--db PATH] [--fixture PATH]
  python -m src.main weekly-report [--db PATH] [--output-dir PATH]
  python -m src.main company-report COMPANY_ID [--db PATH]

OUTPUTS

SQLite keeps companies, pages, snapshots, evidence, signals, announcements and runs.
Weekly reporting writes HTML and CSV to reports/output. Evidence confidence and
commercial priority remain separate. A missing reference is first recorded as a
possible removal; confirmation requires a later successful scan.

ENVIRONMENT

All settings have safe defaults. Copy .env.example only when overrides are needed.
OPENAI_API_KEY and OPENAI_MODEL are reserved for optional prompt-based review; core
detection, change handling and scoring are deterministic and need no API key.

