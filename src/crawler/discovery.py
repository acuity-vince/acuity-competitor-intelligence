from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ..utils.urls import absolute, canonicalize, same_domain

def rank_urls(urls: list[str], domain: str, terms: list[str], limit=25) -> list[str]:
    unique={canonicalize(u) for u in urls if same_domain(u,domain)}
    def score(url):
        path=urlparse(url).path.lower()
        return sum(4 if f"/{term}" in path else 1 for term in terms if term in path)
    return sorted(unique,key=lambda u:(-score(u),len(u),u))[:limit]

def links_from_html(html: str, base_url: str, domain: str) -> list[str]:
    soup=BeautifulSoup(html,"html.parser")
    return [absolute(base_url,a['href']) for a in soup.select('a[href]') if same_domain(absolute(base_url,a['href']),domain)]

