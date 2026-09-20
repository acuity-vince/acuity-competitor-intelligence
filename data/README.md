# Broker registry data

This directory contains the reproducible inputs and generated exports used by the broker intelligence site.

- `sources/` contains regulator source snapshots used by the collectors.
- `exports/` contains the current CSV and Excel registry outputs.
- `../site/public/site/data/registry.csv` is the snapshot embedded in the hosted site.

Credentials are intentionally excluded from Git. Copy `.env.example` to `.env` and add local credentials before running authenticated collectors such as FCA.

## Priority intelligence layers

- `sources/priority-25-entity-resolution-overrides.json` records reviewed brand-to-entity decisions and explicit regulator no-result outcomes.
- `sources/priority-25-sales-intelligence.json` contains evidence-backed Priority 100 sales briefs. Priority 25 records add the gold-tier people, offices, technology assessments, and material history; the remaining 75 stay explicitly hypothesis-led until first-party evidence is confirmed.
- `sources/priority-25-monitor-results.json` is the reviewed connector export used by `scripts/sync_firecrawl_monitor_history.py`; only material events are merged into profile history.
- `sources/priority-25-monitoring.json` records the active weekly monitors and the material-change policy.
- `exports/priority-25-canonical-footprints.json` is the trusted canonical footprint used by the Site.
- `exports/regulator-normalization-audit.csv` records label normalization and duplicate merges.

Run `scripts/validate_broker_intelligence.py site/public/site/data/brokers.json` after rebuilding. It checks the 1,627-profile contract, Priority 25 and Priority 100 coverage, technology status vocabulary, entity readiness, and the sales-copy audit gate.
