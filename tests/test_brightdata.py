import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import app
from app.services.brightdata import BrightDataClient, BrightDataError


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        brightdata_api_token=SecretStr("test-secret-token"),
        brightdata_dataset_id="test-dataset",
        brightdata_base_url="https://api.brightdata.com",
    )


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self.is_error = status_code >= 400
        self.content = text.encode() if text else (b"" if payload is None else b"json")
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


class FakeHttpClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.response


def test_trigger_uses_dataset_id_and_exact_payload() -> None:
    http = FakeHttpClient(FakeResponse(payload={"snapshot_id": "snap-123"}))
    payload = {"input": [{"search_url": "https://www.tiktok.com/explore?lang=en"}]}
    result = asyncio.run(BrightDataClient(make_settings(), http).trigger("test-dataset", payload))  # type: ignore[arg-type]
    method, url, kwargs = http.calls[0]
    assert method == "POST"
    assert "/datasets/v3/trigger" in url
    assert kwargs["params"] == {"dataset_id": "test-dataset", "include_errors": "true"}
    assert kwargs["json"] == payload
    assert kwargs["headers"]["Authorization"] == "Bearer test-secret-token"
    assert result == {"snapshot_id": "snap-123"}


def test_progress_and_snapshot_requests() -> None:
    http = FakeHttpClient(FakeResponse(payload={"status": "ready"}))
    provider = BrightDataClient(make_settings(), http)  # type: ignore[arg-type]
    async def run() -> None:
        await provider.progress("snap-123")
        await provider.snapshot("snap-123", "json")

    asyncio.run(run())
    assert "/datasets/v3/progress/snap-123" in http.calls[0][1]
    assert "/datasets/v3/snapshot/snap-123" in http.calls[1][1]
    assert http.calls[1][2]["params"] == {"format": "json"}


def test_provider_error_does_not_leak_response_body() -> None:
    http = FakeHttpClient(FakeResponse(400, text="sensitive-provider-detail test-secret-token"))
    with pytest.raises(BrightDataError) as error:
        asyncio.run(BrightDataClient(make_settings(), http).progress("snap-123"))  # type: ignore[arg-type]
    assert "400" in str(error.value)
    assert "test-secret-token" not in str(error.value)
    assert "sensitive-provider-detail" not in str(error.value)


def test_health_and_trigger_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import brightdata

    async def trigger(dataset_id: str, payload: dict) -> dict:
        assert dataset_id == "test-dataset"
        return {"snapshot_id": "snap-123"}

    monkeypatch.setattr(brightdata.settings, "brightdata_dataset_id", "test-dataset")
    monkeypatch.setattr(brightdata.client, "trigger", trigger)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        response = client.post("/api/brightdata/jobs", json={"payload": {"input": [{"url": "x"}]}})
    assert response.status_code == 200
    assert response.json()["snapshot_id"] == "snap-123"


def test_provider_endpoints_require_configured_credentials() -> None:
    provider = BrightDataClient(Settings(_env_file=None, brightdata_api_token=None))
    with pytest.raises(BrightDataError, match="credentials are not configured"):
        provider._headers()
