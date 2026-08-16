SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS companies (
 id TEXT PRIMARY KEY, company_name TEXT NOT NULL, domain TEXT NOT NULL UNIQUE, country TEXT,
 region TEXT, broker_type TEXT, priority_account INTEGER NOT NULL DEFAULT 0,
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL REFERENCES companies(id),
 url TEXT NOT NULL UNIQUE, page_type TEXT, first_seen TEXT NOT NULL, last_checked TEXT NOT NULL,
 last_success TEXT, http_status INTEGER, content_hash TEXT, text_hash TEXT, current_text TEXT,
 active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS page_snapshots (
 id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER NOT NULL REFERENCES pages(id),
 captured_at TEXT NOT NULL, content_hash TEXT NOT NULL, text_content TEXT NOT NULL,
 word_count INTEGER NOT NULL, meaningful_change INTEGER NOT NULL DEFAULT 0,
 monthly_reference INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS competitor_evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL REFERENCES companies(id),
 competitor_id TEXT NOT NULL, product_id TEXT, source_url TEXT NOT NULL, source_type TEXT NOT NULL,
 evidence_text TEXT NOT NULL, detected_at TEXT NOT NULL, last_verified TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('CONFIRMED','LIKELY','HISTORICAL','REMOVED','UNCLEAR','NOT_DETECTED')),
 confidence_score INTEGER NOT NULL CHECK(confidence_score BETWEEN 0 AND 98), evidence_hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS signals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT REFERENCES companies(id), signal_type TEXT NOT NULL,
 competitor_id TEXT, product_id TEXT, title TEXT NOT NULL, description TEXT NOT NULL,
 source_url TEXT NOT NULL, evidence_text TEXT NOT NULL, detected_at TEXT NOT NULL,
 confidence_score INTEGER NOT NULL, commercial_priority INTEGER NOT NULL,
 review_status TEXT NOT NULL DEFAULT 'NEW' CHECK(review_status IN ('NEW','REVIEWED','ACTIONED','DISMISSED')),
 previous_value TEXT, current_value TEXT, ai_reasoning_summary TEXT, created_at TEXT NOT NULL,
 confirmation_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS announcements (
 id INTEGER PRIMARY KEY AUTOINCREMENT, competitor_id TEXT NOT NULL, title TEXT NOT NULL,
 url TEXT NOT NULL UNIQUE, published_date TEXT, detected_date TEXT NOT NULL, announcement_type TEXT NOT NULL,
 companies_mentioned TEXT, products_mentioned TEXT, summary TEXT NOT NULL,
 confidence_score INTEGER NOT NULL, commercial_priority INTEGER NOT NULL, content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_type TEXT NOT NULL, started_at TEXT NOT NULL,
 completed_at TEXT, companies_scanned INTEGER NOT NULL DEFAULT 0, pages_scanned INTEGER NOT NULL DEFAULT 0,
 errors INTEGER NOT NULL DEFAULT 0, signals_created INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_company ON competitor_evidence(company_id);
CREATE INDEX IF NOT EXISTS idx_signals_detected ON signals(detected_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_page ON page_snapshots(page_id, captured_at DESC);
"""

