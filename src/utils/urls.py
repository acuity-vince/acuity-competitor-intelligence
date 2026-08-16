from urllib.parse import urljoin, urlparse, urlunparse

def canonicalize(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower() or "https", parsed.netloc.lower(), parsed.path or "/", "", parsed.query, ""))

def same_domain(url: str, domain: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    domain = domain.lower().removeprefix("www.")
    return host == domain or host.endswith("." + domain)

def absolute(base: str, href: str) -> str:
    return urljoin(base, href)

