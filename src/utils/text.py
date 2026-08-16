import re
import unicodedata

def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip()

def context_window(text: str, start: int, end: int, radius: int = 300) -> str:
    return text[max(0, start - radius): min(len(text), end + radius)].strip()

