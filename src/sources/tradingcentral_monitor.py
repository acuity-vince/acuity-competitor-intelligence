import json
from pathlib import Path
from ..detectors.announcement_detector import parse_listing
from ..scoring.priority import score as priority_score
from ..utils.dates import utc_now
from ..utils.hashing import sha256

TYPE_TO_SIGNAL={'NEW_BROKER_PARTNERSHIP':'TC_NEW_PARTNERSHIP','NEW_PLATFORM_INTEGRATION':'TC_NEW_PLATFORM_INTEGRATION','NEW_PRODUCT':'TC_NEW_PRODUCT','PRODUCT_UPDATE':'TC_PRODUCT_UPDATE'}

def monitor(db, html: str):
    created=0
    for item in parse_listing(html):
        if db.connection.execute("SELECT 1 FROM announcements WHERE url=? AND content_hash=?",(item['url'],sha256(item['content']))).fetchone(): continue
        kind=TYPE_TO_SIGNAL.get(item['type'],'TC_COMPETITIVE_PAGE_CHANGE'); priority=priority_score(kind,95)
        db.connection.execute("""INSERT INTO announcements(competitor_id,title,url,published_date,detected_date,announcement_type,
          companies_mentioned,products_mentioned,summary,confidence_score,commercial_priority,content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(url) DO UPDATE SET title=excluded.title,summary=excluded.summary,content_hash=excluded.content_hash,
          announcement_type=excluded.announcement_type,commercial_priority=excluded.commercial_priority""",
          ('trading_central',item['title'],item['url'],item['published_date'],utc_now(),item['type'],json.dumps([]),json.dumps([]),item['content'],95,priority,sha256(item['content'])))
        created+=1
    db.connection.commit(); return created

