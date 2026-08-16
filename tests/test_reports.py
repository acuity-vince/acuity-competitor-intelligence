from src.reports.weekly_report import generate
from src.sources.broker_monitor import BrokerMonitor

def test_fixture_pipeline_and_report(db,root,tmp_path):
    monitor=BrokerMonitor(db,root/'config')
    counts=monitor.run(root/'tests/fixtures/brokers')
    assert counts=={'companies':1,'pages':1,'errors':0,'signals':1}
    html,csv=generate(db,tmp_path/'reports')
    assert html.exists() and csv.exists()
    assert 'Sample Broker' in html.read_text(encoding='utf-8')

