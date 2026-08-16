import csv
from pathlib import Path

def export(rows,path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f); writer.writerow(['COMPANY','SIGNAL','PRIORITY','CONFIDENCE','DETECTED','SOURCE','EVIDENCE'])
        for r in rows: writer.writerow([r['company_name'] or 'Trading Central',r['signal_type'],r['commercial_priority'],r['confidence_score'],r['detected_at'],r['source_url'],r['evidence_text']])
    return path

