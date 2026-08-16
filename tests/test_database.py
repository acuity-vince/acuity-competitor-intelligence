from src.utils.dates import utc_now
from src.utils.hashing import sha256

BROKER={'id':'b1','company_name':'Broker One','domain':'b1.test','priority_account':False,'active':True}

def test_schema_and_history(db):
    db.upsert_company(BROKER)
    db.save_page('b1','https://b1.test/research',200,'h1','t1','old')
    db.save_page('b1','https://b1.test/research',200,'h2','t2','new',True)
    assert db.connection.execute('SELECT count(*) FROM page_snapshots').fetchone()[0]==2
    assert db.connection.execute('SELECT current_text FROM pages').fetchone()[0]=='new'

def test_evidence_is_idempotent(db):
    db.upsert_company(BROKER); now=utc_now()
    record={'company_id':'b1','competitor_id':'trading_central','product_id':None,'source_url':'https://b1.test','source_type':'broker_website','evidence_text':'offers Trading Central','detected_at':now,'last_verified':now,'status':'CONFIRMED','confidence_score':95,'evidence_hash':sha256('one')}
    db.add_evidence(record); db.add_evidence(record)
    assert db.connection.execute('SELECT count(*) FROM competitor_evidence').fetchone()[0]==1

