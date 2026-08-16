from bs4 import BeautifulSoup

COMMON_SITEMAPS=("/sitemap_index.xml","/sitemap.xml","/wp-sitemap.xml")

def parse_sitemap(xml: str) -> list[str]:
    soup=BeautifulSoup(xml,"xml")
    return [loc.get_text(strip=True) for loc in soup.find_all("loc")]

