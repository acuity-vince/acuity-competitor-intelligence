import time
import httpx

RETRY_STATUSES = {429, 500, 502, 503, 504}

class Fetcher:
    def __init__(self, user_agent="AcuityCompetitorResearch/1.0", interval=2.0, max_retries=3, transport=None):
        self.interval=interval; self.max_retries=max_retries; self.last_request={}
        self.client=httpx.Client(headers={"User-Agent":user_agent},follow_redirects=True,timeout=20,transport=transport)

    def get(self, url: str) -> httpx.Response:
        domain=httpx.URL(url).host or ""
        elapsed=time.monotonic()-self.last_request.get(domain,0)
        if elapsed < self.interval: time.sleep(self.interval-elapsed)
        response=None
        for attempt in range(self.max_retries+1):
            self.last_request[domain]=time.monotonic(); response=self.client.get(url)
            if response.status_code not in RETRY_STATUSES: return response
            if attempt < self.max_retries: time.sleep(min(2**attempt,8))
        return response

