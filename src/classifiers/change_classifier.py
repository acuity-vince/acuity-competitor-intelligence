def classify(previous_detected: bool, current_detected: bool, added_products: set, removed_products: set) -> str:
    if not previous_detected and current_detected: return "TRADING_CENTRAL_ADDED"
    if previous_detected and not current_detected: return "TRADING_CENTRAL_REMOVED"
    if added_products: return "PRODUCT_ADDED"
    if removed_products: return "PRODUCT_REMOVED"
    return "COPY_ONLY_CHANGE"

