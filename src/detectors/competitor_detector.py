import re
from ..storage.models import Detection
from ..utils.text import context_window

CURRENT_RELATIONSHIP_TERMS=("access to","offers","provides","integrated","integration","partnered","available to","powered by","clients can")

def detect(text: str, url: str, links: list[str], aliases: list[str], products: list[dict]) -> Detection:
    haystacks=[text,url,*links]
    found=[]; evidence=[]
    for alias in aliases:
        pattern=re.compile(re.escape(alias),re.IGNORECASE)
        if any(pattern.search(h) for h in haystacks):
            found.append(alias)
        for match in pattern.finditer(text): evidence.append(context_window(text,match.start(),match.end()))
    if any("tradingcentral.com" in h.lower() for h in [url,*links]): found.append("tradingcentral.com")
    product_ids=[]
    for product in products:
        if not product.get('active',True): continue
        terms=[product['product_name'],*product.get('aliases',[])]
        if any(re.search(r"(?<!\w)"+re.escape(term)+r"(?!\w)",text,re.I) for term in terms): product_ids.append(product['product_id'])
    relationship=tuple(term for term in CURRENT_RELATIONSHIP_TERMS if term in text.lower())
    return Detection(tuple(dict.fromkeys(found)),tuple(dict.fromkeys(product_ids)),tuple(dict.fromkeys(evidence)),relationship)

def deterministic_status(result: Detection) -> str:
    if not result.matched_terms: return "NOT_DETECTED"
    return "CONFIRMED" if result.relationship_terms else "UNCLEAR"

