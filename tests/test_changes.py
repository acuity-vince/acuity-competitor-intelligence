from src.detectors.page_change_detector import relevant_change
from src.classifiers.change_classifier import classify
from src.sources.broker_monitor import BrokerMonitor
import yaml

def test_competitor_addition_is_meaningful():
    result=relevant_change('Research tools','Research tools Trading Central',['Trading Central'])
    assert result['relevant']
    assert classify(False,True,set(),set())=='TRADING_CENTRAL_ADDED'

def test_cosmetic_change_creates_no_competitor_change():
    assert not relevant_change('Updated 1','Updated 2',['Trading Central'])['relevant']

def test_removal_needs_two_successful_scans(db,root):
    monitor=BrokerMonitor(db,root/'config')
    broker=yaml.safe_load((root/'config/brokers.yaml').read_text())['brokers'][0]
    db.upsert_company(broker)
    url=broker['known_research_urls'][0]
    original=(root/'tests/fixtures/brokers/sample_broker.html').read_text()
    monitor.process_page(broker,url,original)
    monitor.process_page(broker,url,'<html><main><p>Research tools are available.</p></main></html>')
    assert db.connection.execute("SELECT signal_type FROM signals ORDER BY id DESC LIMIT 1").fetchone()[0]=='POSSIBLE_REMOVAL'
    monitor.process_page(broker,url,'<html><main><p>Research tools remain available.</p></main></html>')
    assert db.connection.execute("SELECT signal_type FROM signals ORDER BY id DESC LIMIT 1").fetchone()[0]=='BROKER_TC_REFERENCE_REMOVED'
