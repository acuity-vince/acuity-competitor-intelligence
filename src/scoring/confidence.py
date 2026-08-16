BASE={"broker_explicit_access":95,"competitor_official_announcement":95,"broker_platform_page":92,"broker_news":90,"generic_third_party":50}

def score(source: str, classification: str) -> int:
    value=BASE.get(source,50)
    if classification in {"UNCLEAR","HISTORICAL"}: value=min(value,60)
    if classification=="NOT_DETECTED": value=0
    return min(98,max(0,value))

