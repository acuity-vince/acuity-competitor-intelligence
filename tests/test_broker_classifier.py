from src.classifiers.broker_classifier import classify_broker


def test_positive_fx_product_evidence():
    result = classify_broker("Example Markets Ltd", "Trade forex and CFDs with MetaTrader 5")
    assert result.forex_broker == "YES"
    assert result.needs_review == "NO"


def test_bank_is_not_target():
    result = classify_broker("Hellenic Bank Public Company Ltd", "Retail bank and corporate banking")
    assert result.forex_broker == "NO"
    assert result.confidence == "HIGH"


def test_unknown_requires_review():
    result = classify_broker("Example Investments Ltd", "Welcome to our company")
    assert result.forex_broker == "NO"
    assert result.needs_review == "YES"
