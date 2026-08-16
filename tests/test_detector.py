import yaml
from src.crawler.extract import extract_page
from src.detectors.competitor_detector import detect,deterministic_status

def test_detects_competitor_products_and_context(root):
    html=(root/'tests/fixtures/brokers/sample_broker.html').read_text()
    products=yaml.safe_load((root/'config/products.yaml').read_text())['products']
    text,links,_=extract_page(html); result=detect(text,'https://sample-broker.test/research',links,['Trading Central','TradingCentral'],products)
    assert deterministic_status(result)=='CONFIRMED'
    assert {'analyst_views','market_buzz'} <= set(result.products)
    assert result.evidence and 'access to Trading Central' in result.evidence[0]

def test_generic_mention_is_not_confirmed(root):
    result=detect('A review compares Trading Central with other firms.','https://x.test',[],['Trading Central'],[])
    assert deterministic_status(result)=='UNCLEAR'

