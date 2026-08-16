import sqlite3
from pathlib import Path
from .migrations import SCHEMA
from ..utils.dates import utc_now

class Database:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    def migrate(self):
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def upsert_company(self, broker: dict):
        now = utc_now()
        self.connection.execute("""INSERT INTO companies
          (id,company_name,domain,country,region,broker_type,priority_account,active,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET company_name=excluded.company_name,
          domain=excluded.domain,country=excluded.country,region=excluded.region,broker_type=excluded.broker_type,
          priority_account=excluded.priority_account,active=excluded.active,updated_at=excluded.updated_at""",
          (broker['id'],broker['company_name'],broker['domain'],broker.get('country'),broker.get('region'),
           broker.get('broker_type'),int(broker.get('priority_account',False)),int(broker.get('active',True)),now,now))
        self.connection.commit()

    def start_run(self, kind: str) -> int:
        cur = self.connection.execute("INSERT INTO runs(run_type,started_at,status) VALUES (?,?,'RUNNING')", (kind, utc_now()))
        self.connection.commit(); return cur.lastrowid

    def finish_run(self, run_id: int, **counts):
        self.connection.execute("""UPDATE runs SET completed_at=?,companies_scanned=?,pages_scanned=?,errors=?,
          signals_created=?,status=? WHERE id=?""", (utc_now(), counts.get('companies',0), counts.get('pages',0),
          counts.get('errors',0), counts.get('signals',0), counts.get('status','COMPLETED'), run_id))
        self.connection.commit()

    def get_page(self, url: str):
        return self.connection.execute("SELECT * FROM pages WHERE url=?", (url,)).fetchone()

    def save_page(self, company_id: str, url: str, status: int, html_hash: str, text_hash: str, text: str, meaningful=False):
        now = utc_now(); existing = self.get_page(url)
        if existing:
            self.connection.execute("""UPDATE pages SET last_checked=?,last_success=?,http_status=?,content_hash=?,
              text_hash=?,current_text=?,active=1 WHERE id=?""", (now,now,status,html_hash,text_hash,text,existing['id']))
            page_id = existing['id']
        else:
            cur = self.connection.execute("""INSERT INTO pages(company_id,url,page_type,first_seen,last_checked,last_success,
              http_status,content_hash,text_hash,current_text) VALUES (?,?,'broker',?,?,?,?,?,?,?)""",
              (company_id,url,now,now,now,status,html_hash,text_hash,text)); page_id=cur.lastrowid
        self.connection.execute("""INSERT INTO page_snapshots(page_id,captured_at,content_hash,text_content,word_count,meaningful_change)
          VALUES (?,?,?,?,?,?)""", (page_id,now,html_hash,text,len(text.split()),int(meaningful)))
        self._prune_snapshots(page_id)
        self.connection.commit(); return existing

    def record_failure(self, company_id: str, url: str, status: int):
        now=utc_now(); existing=self.get_page(url)
        if existing:
            self.connection.execute("UPDATE pages SET last_checked=?,http_status=? WHERE id=?",(now,status,existing['id']))
        else:
            self.connection.execute("INSERT INTO pages(company_id,url,page_type,first_seen,last_checked,http_status,active) VALUES (?,?,'broker',?,?,?,0)",(company_id,url,now,now,status))
        self.connection.commit()

    def _prune_snapshots(self, page_id: int):
        rows=self.connection.execute("SELECT id FROM page_snapshots WHERE page_id=? AND meaningful_change=0 AND monthly_reference=0 ORDER BY captured_at DESC,id DESC",(page_id,)).fetchall()
        for row in rows[2:]: self.connection.execute("DELETE FROM page_snapshots WHERE id=?",(row['id'],))

    def add_evidence(self, record: dict):
        self.connection.execute("""INSERT INTO competitor_evidence(company_id,competitor_id,product_id,source_url,source_type,
          evidence_text,detected_at,last_verified,status,confidence_score,evidence_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(evidence_hash) DO UPDATE SET last_verified=excluded.last_verified,status=excluded.status,
          confidence_score=excluded.confidence_score""", tuple(record[k] for k in ('company_id','competitor_id','product_id','source_url','source_type','evidence_text','detected_at','last_verified','status','confidence_score','evidence_hash')))
        self.connection.commit()

    def add_signal(self, record: dict) -> int:
        keys=('company_id','signal_type','competitor_id','product_id','title','description','source_url','evidence_text','detected_at','confidence_score','commercial_priority','previous_value','current_value','ai_reasoning_summary','created_at')
        cur=self.connection.execute(f"INSERT INTO signals({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",tuple(record.get(k) for k in keys)); self.connection.commit(); return cur.lastrowid

