from src.scoring.confidence import score as confidence
from src.scoring.priority import score as priority

def test_scores_are_separate_and_capped():
    assert confidence('broker_explicit_access','CONFIRMED')==95
    assert priority('BROKER_TC_NEWLY_DETECTED',95,True)==95
    assert priority('BROKER_TC_REFERENCE_REMOVED',95,True,recent_signal_count=3)==100

def test_low_confidence_penalty(): assert priority('GENERIC_MENTION',30)==0

