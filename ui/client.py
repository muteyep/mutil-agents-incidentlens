from __future__ import annotations

import os

import httpx


class ApiError(RuntimeError):
    """Raised when the API is unreachable or returns an error status."""


class IncidentLensClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("INCIDENTLENS_API_URL", "http://localhost:8000")
        ).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url, timeout=timeout, transport=transport
        )

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(f"cannot reach API at {self.base_url}: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"{response.status_code}: {detail}")
        return response.json()

    def health(self) -> dict:
        return self._request("GET", "/health")

    def list_cases(self) -> list[dict]:
        return self._request("GET", "/api/cases")

    def get_case(self, case_id: str) -> dict:
        return self._request("GET", f"/api/cases/{case_id}")

    def analyze(self, case_id: str, mode: str = "multi", use_llm: bool = False) -> dict:
        return self._request(
            "POST",
            "/api/analyze",
            json={"case_id": case_id, "mode": mode, "use_llm": use_llm},
        )

    def start_approval(self, action: str, risk: str = "high") -> dict:
        return self._request(
            "POST", "/api/approval/start", json={"action": action, "risk": risk}
        )

    def resume_approval(self, thread_id: str, approved: bool) -> dict:
        return self._request(
            "POST",
            f"/api/approval/{thread_id}/resume",
            json={"approved": approved},
        )

    def list_runs(self, limit: int = 20) -> list[dict]:
        return self._request("GET", f"/api/runs?limit={limit}")
