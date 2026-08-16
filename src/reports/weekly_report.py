from datetime import datetime,timezone,timedelta
from html import escape
from pathlib import Path
from .csv_export import export

def generate(db,output_dir='reports/output'):
    since=(datetime.now(timezone.utc)-timedelta(days=7)).isoformat()
    rows=db.connection.execute("""SELECT s.*,c.company_name FROM signals s LEFT JOIN companies c ON c.id=s.company_id
      WHERE s.detected_at>=? ORDER BY s.commercial_priority DESC,s.detected_at DESC""",(since,)).fetchall()
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); date=datetime.now(timezone.utc).date().isoformat()
    csv_path=export(rows,out/f"weekly-{date}.csv")
    cards=''.join(f"<article><h2>{escape(r['company_name'] or 'Trading Central')}</h2><p>{escape(r['title'])}</p><dl><dt>COMMERCIAL PRIORITY</dt><dd>{r['commercial_priority']}</dd><dt>EVIDENCE CONFIDENCE</dt><dd>{r['confidence_score']}</dd></dl><p>{escape(r['description'])}</p><a href=\"{escape(r['source_url'])}\">Evidence</a></article>" for r in rows[:20]) or '<p>No new signals this week.</p>'
    html=f"<!doctype html><html><head><meta charset='utf-8'><title>Acuity competitor intelligence</title><style>body{{background:#0b0d10;color:#f2f4f5;font:16px Roboto,Arial;max-width:960px;margin:48px auto}}article{{border:1px solid #343a40;padding:24px;margin:16px 0}}dt{{font:12px monospace;color:#aeb4ba}}dd{{margin:4px 0 16px}}a{{color:#fff}}</style></head><body><h1>Acuity competitor intelligence</h1><p>Weekly report · {date}</p>{cards}</body></html>"
    html_path=out/f"weekly-{date}.html"; html_path.write_text(html,encoding='utf-8'); return html_path,csv_path

