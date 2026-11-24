from __future__ import annotations

import httpx

from ui.client import ApiError, IncidentLensClient


def _client(handler) -> IncidentLensClient:
    return IncidentLensClient(
        "http://test", transport=httpx.MockTransport(handler)
    )


def test_list_cases() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/cases"
        return httpx.Response(200, json=[{"case_id": "case_001"}])

    assert _client(handler).list_cases() == [{"case_id": "case_001"}]


def test_analyze_posts_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/analyze"
        body = request.read().decode()
        assert "case_001" in body
        return httpx.Response(200, json={"hypotheses": [{"service": "payment"}]})

    result = _client(handler).analyze("case_001", "multi")
    assert result["hypotheses"][0]["service"] == "payment"


def test_api_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "case not found"})

    try:
        _client(handler).get_case("missing")
    except ApiError as exc:
        assert "404" in str(exc)
    else:
        raise AssertionError("ApiError expected")
