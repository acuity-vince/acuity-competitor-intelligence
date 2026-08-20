# Broker registry data

This directory contains the reproducible inputs and generated exports used by the broker intelligence site.

- `sources/` contains regulator source snapshots used by the collectors.
- `exports/` contains the current CSV and Excel registry outputs.
- `../site/public/site/data/registry.csv` is the snapshot embedded in the hosted site.

Credentials are intentionally excluded from Git. Copy `.env.example` to `.env` and add local credentials before running authenticated collectors such as FCA.
