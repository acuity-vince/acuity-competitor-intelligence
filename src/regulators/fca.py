"""Client for candidate-by-candidate FCA Financial Services Register enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


BASE_URL = "https://register.fca.org.uk/services/V0.1"


class FCAConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class FCASearchResult:
    frn: str
    name: str
    status: str
    result_type: str
    raw: dict[str, Any]


class FCAClient:
    """Small authenticated client; the FCA API is for individual lookups, not bulk scans."""

    def __init__(
        self,
        email: str,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        base_url: str = BASE_URL,
    ):
        if not email or not api_key:
            raise FCAConfigurationError("FCA_API_EMAIL and FCA_API_KEY are required")
        self.client = httpx.Client(
            base_url=base_url,
            headers={
                "X-Auth-Email": email,
                "X-Auth-Key": api_key,
                "Accept": "application/json",
                "User-Agent": "AcuityCompetitorResearch/1.0",
            },
            follow_redirects=True,
            timeout=20,
            transport=transport,
        )

    def search_firms(self, query: str) -> list[FCASearchResult]:
        response = self.client.get("/Search", params={"q": query, "type": "firm"})
        response.raise_for_status()
        payload = response.json()
        records = payload.get("Data") or payload.get("data") or []
        if isinstance(records, dict):
            records = records.get("Results") or records.get("results") or []
        return [self._search_result(record) for record in records]

    def get_firm(self, frn: str) -> dict[str, Any]:
        response = self.client.get(f"/Firm/{frn}")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _search_result(record: dict[str, Any]) -> FCASearchResult:
        def pick(*keys: str) -> str:
            for key in keys:
                value = record.get(key)
                if value is not None:
                    return str(value).strip()
            return ""

        return FCASearchResult(
            frn=pick("FRN", "frn", "Reference Number", "ReferenceNumber"),
            name=pick("Name", "name", "Firm Name", "FirmName"),
            status=pick("Status", "status"),
            result_type=pick("Type", "type", "Type of business or Individual"),
            raw=record,
        )
