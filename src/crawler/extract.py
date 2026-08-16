from bs4 import BeautifulSoup
from ..utils.text import normalize_text

def extract_page(html: str) -> tuple[str, list[str], list[str]]:
    soup=BeautifulSoup(html,"html.parser")
    for tag in soup.select("script,style,noscript,nav,footer,form"): tag.decompose()
    title=normalize_text(soup.title.get_text(" ",strip=True)) if soup.title else ""
    pieces=[title]
    pieces.extend(normalize_text(node.get_text(" ",strip=True)) for node in soup.select("h1,h2,h3,p,li") if node.get_text(strip=True))
    alt=[normalize_text(img.get('alt','')) for img in soup.select('img[alt]') if img.get('alt','').strip()]
    links=[a.get('href','') for a in soup.select('a[href]')]
    return normalize_text(" ".join(pieces+alt)),links,alt

