import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.keyword_discovery import BrightDataKeywordDiscovery, KeywordDiscoveryError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "brightdata_keyword_sample.json"


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        brightdata_api_token=SecretStr("unit-test-secret"),
        brightdata_keyword_dataset_id="gd_lu702nij2f790tmv9h",
    )


def test_settings_read_process_environment_without_loading_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "process-env-test-token")
    settings = Settings()
    assert settings.brightdata_api_token is not None
    assert settings.brightdata_api_token.get_secret_value() == "process-env-test-token"
    assert Settings.model_config.get("env_file") is None


def test_keyword_request_matches_documented_configuration() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        parsed = urlparse(str(request.url))
        assert request.method == "POST"
        assert parsed.path == "/datasets/v3/scrape"
        assert parse_qs(parsed.query) == {
            "dataset_id": ["gd_lu702nij2f790tmv9h"],
            "notify": ["false"],
            "include_errors": ["true"],
            "type": ["discover_new"],
            "discover_by": ["keyword"],
        }
        assert request.headers["Authorization"] == "Bearer unit-test-secret"
        assert json.loads(request.content) == {
            "input": [{"search_keyword": "football", "country": ""}],
            "limit_per_input": None,
        }
        return httpx.Response(200, json=json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = BrightDataKeywordDiscovery(make_settings(), client).search(" football ")
    assert len(result.records) == 1
    assert result.snapshot_id is None
    assert result.records[0]["play_count"] == 268000
    client.close()


def test_keyword_response_with_snapshot_is_not_mistaken_for_records() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(202, json={"snapshot_id": "snap-123"}))
    )
    result = BrightDataKeywordDiscovery(make_settings(), client).search("football")
    assert result.records == []
    assert result.snapshot_id == "snap-123"
    client.close()


def test_provider_error_keeps_safe_detail_and_redacts_secrets() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                400,
                json={"error": "invalid input", "request_token": "unit-test-secret", "hint": "check keyword"},
            )
        )
    )
    with pytest.raises(KeywordDiscoveryError) as error:
        BrightDataKeywordDiscovery(make_settings(), client).search("football")
    assert error.value.status_code == 400
    assert "invalid input" in (error.value.provider_detail or "")
    assert "check keyword" in (error.value.provider_detail or "")
    assert "unit-test-secret" not in (error.value.provider_detail or "")
    client.close()


def test_malformed_json_is_reported_safely() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"{not json"))
    )
    with pytest.raises(KeywordDiscoveryError, match="malformed JSON"):
        BrightDataKeywordDiscovery(make_settings(), client).search("football")
    client.close()


def test_empty_keyword_is_rejected_before_provider_call() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="must not be empty"):
        BrightDataKeywordDiscovery(make_settings(), client).search("  ")
    client.close()


def test_progress_and_snapshot_retrieval_use_provider_endpoints() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/progress/snap-123"):
            return httpx.Response(200, json={"snapshot_id": "snap-123", "status": "ready"})
        return httpx.Response(200, json=fixture)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = BrightDataKeywordDiscovery(make_settings(), client)
    progress = service.get_progress("snap-123")
    snapshot = service.get_snapshot("snap-123")
    assert progress["status"] == "ready"
    assert snapshot.records == fixture
    assert calls[0].url.path == "/datasets/v3/progress/snap-123"
    assert calls[1].url.path == "/datasets/v3/snapshot/snap-123"
    assert calls[1].url.params["format"] == "json"
    client.close()


def test_snapshot_id_is_validated_before_provider_request() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[])))
    with pytest.raises(ValueError, match="invalid snapshot ID"):
        BrightDataKeywordDiscovery(make_settings(), client).get_progress("../secret")
    client.close()
