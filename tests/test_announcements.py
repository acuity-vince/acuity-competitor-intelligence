from src.sources.tradingcentral_monitor import monitor

def test_announcement_monitor_is_idempotent(db,root):
    html=(root/'tests/fixtures/tradingcentral/news.html').read_text()
    assert monitor(db,html)==2
    assert monitor(db,html)==0
    rows=db.connection.execute('SELECT announcement_type FROM announcements ORDER BY id').fetchall()
    assert [r[0] for r in rows]==['NEW_BROKER_PARTNERSHIP','NEW_PRODUCT']

