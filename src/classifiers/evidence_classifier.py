from ..detectors.competitor_detector import deterministic_status

def classify(detection) -> dict:
    status=deterministic_status(detection)
    reasons={"CONFIRMED":"Competitor reference appears with current-access wording.","UNCLEAR":"Competitor is mentioned without enough relationship evidence.","NOT_DETECTED":"No matching evidence."}
    return {"classification":status,"short_reason":reasons[status],"evidence_strength":95 if status=="CONFIRMED" else 50 if status=="UNCLEAR" else 0}

