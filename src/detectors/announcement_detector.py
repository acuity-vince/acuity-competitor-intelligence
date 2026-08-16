import re
from bs4 import BeautifulSoup
from ..utils.text import normalize_text

TYPES=(("NEW_PRODUCT",("launches","introduces","new product")),("NEW_PLATFORM_INTEGRATION",("integration","integrates")),("NEW_BROKER_PARTNERSHIP",("partnership","partners with","broker")),("PRODUCT_UPDATE",("update","enhancement")),("REGIONAL_EXPANSION",("expansion","expands")),("EVENT",("event","expo","conference")))

def classify(title: str, content: str) -> str:
    value=(title+' '+content).lower()
    for kind,terms in TYPES:
        if any(t in value for t in terms): return kind
    return "COMPANY_NEWS"

def parse_listing(html: str, base_url="https://www.tradingcentral.com") -> list[dict]:
    from urllib.parse import urljoin
    soup=BeautifulSoup(html,"html.parser"); results=[]
    for article in soup.select("article"):
        link=article.select_one("a[href]"); title_node=article.select_one("h1,h2,h3")
        if not link or not title_node: continue
        content=normalize_text(article.get_text(" ",strip=True)); title=normalize_text(title_node.get_text(" ",strip=True))
        date=article.select_one("time")
        results.append({"title":title,"url":urljoin(base_url,link['href']),"published_date":date.get('datetime') if date else None,"content":content,"type":classify(title,content)})
    return results
