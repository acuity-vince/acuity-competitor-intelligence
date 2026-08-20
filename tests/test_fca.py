import json

import httpx
import pytest

from src.regulators.fca import FCAClient, FCAConfigurationError


def test_fca_client_requires_credentials():
    with pytest.raises(FCAConfigurationError):
        FCAClient("", "")


def test_fca_search_sends_auth_headers_and_parses_results():
    def handler(request: httpx.Request):
        assert request.headers["X-Auth-Email"] == "owner@example.com"
        assert request.headers["X-Auth-Key"] == "test-key"
        assert request.url.params["q"] == "Example Markets"
        assert request.url.params["type"] == "firm"
        payload = {"Data": [{"Reference Number": "123456", "Name": "Example Markets Ltd", "Status": "Authorised", "Type of business or Individual": "Firm"}]}
        return httpx.Response(200, content=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})

    client = FCAClient("owner@example.com", "test-key", transport=httpx.MockTransport(handler))
    results = client.search_firms("Example Markets")
    assert len(results) == 1
    assert results[0].frn == "123456"
    assert results[0].status == "Authorised"
    assert results[0].result_type == "Firm"
