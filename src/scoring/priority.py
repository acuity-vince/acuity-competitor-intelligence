from datetime import datetime,timezone

BASE={"BROKER_TC_REFERENCE_REMOVED":85,"POSSIBLE_REMOVAL":70,"BROKER_TC_NEWLY_DETECTED":75,"BROKER_TC_PRODUCT_ADDED":70,"BROKER_TC_PRODUCT_REMOVED":70,"BROKER_TC_CONFIRMED":55,"TC_NEW_CLIENT":65,"TC_NEW_PARTNERSHIP":65,"TC_NEW_PLATFORM_INTEGRATION":70,"TC_NEW_PRODUCT":55,"TC_PRODUCT_UPDATE":40,"GENERIC_MENTION":10}

def score(signal_type: str, confidence: int, priority_account=False, recent_signal_count=0, age_days=0) -> int:
    value=BASE.get(signal_type,10)
    if priority_account: value+=10
    if recent_signal_count>=3: value+=10
    elif recent_signal_count==2: value+=5
    if age_days<7: value+=10
    elif age_days<30: value+=5
    if confidence<50: value-=20
    return max(0,min(100,value))

