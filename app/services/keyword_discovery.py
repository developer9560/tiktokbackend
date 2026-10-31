"""Bright Data TikTok keyword-discovery integration from the supplied cURL."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, settings

logger = logging.getLogger(__name__)
_SECRET_KEYS = re.compile(r"(token|authorization|api.?key|secret|password)", re.IGNORECASE)


class KeywordDiscoveryError(RuntimeError):
    """Provider error containing only a redacted, safe detail."""

    def __init__(self, message: str, *, status_code: int | None = None, provider_detail: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.provider_detail = provider_detail


@dataclass(frozen=True)
class KeywordDiscoveryResponse:
    records: list[dict[str, Any]]
    snapshot_id: str | None
    provider_response: Any
    status_code: int


def _redact(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SECRET_KEYS.search(str(key)) else _redact(item, token)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, token) for item in value]
    if isinstance(value, str):
        redacted = value.replace(token, "[REDACTED]") if token else value
        return redacted[:2000]
    return value


class BrightDataKeywordDiscovery:
    """Calls only the documented TikTok keyword discovery operation."""

    endpoint = "/datasets/v3/scrape"

    def __init__(self, config: Settings = settings, client: httpx.Client | None = None):
        self.config = config
        self._client = client

    def search(self, keyword: str, country: str = "") -> KeywordDiscoveryResponse:
        token = "6d7e9eb7-b797-45db-9877-9dd89e48c85b"
        if not token:
            raise KeywordDiscoveryError("Bright Data credentials are not configured")
        cleaned_keyword = keyword.strip()
        if not cleaned_keyword:
            raise ValueError("keyword must not be empty")

        params = {
            "dataset_id": self.config.brightdata_keyword_dataset_id,
            "notify": "false",
            "include_errors": "true",
            "type": "discover_new",
            "discover_by": "keyword",
        }
        payload = {
            "input": [{"search_keyword": cleaned_keyword, "country": country}],
            "limit_per_input": None,
        }
        url = f"{self.config.brightdata_base_url.rstrip('/')}{self.endpoint}"

        response = self._send("POST", url, token, params=params, json=payload)
        provider_body = self._decode(response, token)
        if response.is_error:
            self._raise_provider_error(response, provider_body, token)

        records, snapshot_id = self._extract_records(provider_body, token)
        logger.info(
            "Bright Data keyword request completed status=%s dataset_id=%s records=%s snapshot=%s",
            response.status_code,
            self.config.brightdata_keyword_dataset_id,
            len(records),
            bool(snapshot_id),
        )
        return KeywordDiscoveryResponse(
            records=records,
            snapshot_id=snapshot_id,
            provider_response=_redact(provider_body, token),
            status_code=response.status_code,
        )

    def get_progress(self, snapshot_id: str) -> dict[str, Any]:
        self._validate_snapshot_id(snapshot_id)
        token = self._token()
        url = f"{self.config.brightdata_base_url.rstrip('/')}/datasets/v3/progress/{snapshot_id}"
        response = self._send("GET", url, token)
        body = self._decode(response, token)
        if response.is_error:
            self._raise_provider_error(response, body, token)
        if not isinstance(body, dict) or not isinstance(body.get("status"), str):
            raise KeywordDiscoveryError("Bright Data returned malformed progress data")
        return body

    def get_snapshot(self, snapshot_id: str, output_format: str = "json") -> KeywordDiscoveryResponse:
        self._validate_snapshot_id(snapshot_id)
        token = self._token()
        url = f"{self.config.brightdata_base_url.rstrip('/')}/datasets/v3/snapshot/{snapshot_id}"
        response = self._send("GET", url, token, params={"format": output_format})
        body = self._decode(response, token)
        if response.is_error:
            self._raise_provider_error(response, body, token)
        records, returned_snapshot_id = self._extract_records(body, token)
        return KeywordDiscoveryResponse(
            records=records,
            snapshot_id=returned_snapshot_id,
            provider_response=_redact(body, token),
            status_code=response.status_code,
        )

    def _token(self) -> str:
        token = "6d7e9eb7-b797-45db-9877-9dd89e48c85b"
        if not token:
            raise KeywordDiscoveryError("Bright Data credentials are not configured")
        return token

    def _send(
        self,
        method: str,
        url: str,
        token: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = self._client.request(
                    method,
                    url,
                    params=params,
                    headers=self._headers(token),
                    json=json,
                    timeout=self.config.request_timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.config.request_timeout_seconds) as client:
                    response = client.request(
                        method,
                        url,
                        params=params,
                        headers=self._headers(token),
                        json=json,
                    )
        except httpx.TimeoutException as exc:
            raise KeywordDiscoveryError("Bright Data request timed out") from exc
        except httpx.RequestError as exc:
            raise KeywordDiscoveryError("Bright Data could not be reached") from exc
        return response

    def _raise_provider_error(self, response: httpx.Response, body: Any, token: str) -> None:
        safe_detail = self._provider_detail(body, token)
        logger.warning(
            "Bright Data keyword request failed status=%s dataset_id=%s",
            response.status_code,
            self.config.brightdata_keyword_dataset_id,
        )
        raise KeywordDiscoveryError(
            f"Bright Data returned HTTP {response.status_code}",
            status_code=response.status_code,
            provider_detail=safe_detail,
        )

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @staticmethod
    def _decode(response: httpx.Response, token: str) -> Any:
        if not response.content:
            raise KeywordDiscoveryError(
                "Bright Data returned an empty response",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            safe_text = str(_redact(response.text, token))
            raise KeywordDiscoveryError(
                "Bright Data returned malformed JSON",
                status_code=response.status_code,
                provider_detail=safe_text,
            ) from exc

    @staticmethod
    def _extract_records(body: Any, token: str = "") -> tuple[list[dict[str, Any]], str | None]:
        if isinstance(body, list):
            if not all(isinstance(record, dict) for record in body):
                raise KeywordDiscoveryError("Bright Data response contained an invalid record")
            errors = [record for record in body if BrightDataKeywordDiscovery._is_error_record(record)]
            records = [record for record in body if not BrightDataKeywordDiscovery._is_error_record(record)]
            if errors and not records:
                raise BrightDataKeywordDiscovery._input_error(errors, token)
            if errors:
                logger.warning("Bright Data returned %s input error row(s) alongside records", len(errors))
            return records, None
        if isinstance(body, dict):
            snapshot_id = body.get("snapshot_id")
            if isinstance(snapshot_id, str) and snapshot_id:
                return [], snapshot_id
            records = body.get("data")
            if isinstance(records, list) and all(isinstance(record, dict) for record in records):
                return BrightDataKeywordDiscovery._extract_records(records, token)
            if BrightDataKeywordDiscovery._is_error_record(body):
                raise BrightDataKeywordDiscovery._input_error([body], token)
            if any(key in body for key in ("url", "post_id", "description")):
                return [body], None
        raise KeywordDiscoveryError(
            "Bright Data returned an unsupported response shape",
            provider_detail=json.dumps(BrightDataKeywordDiscovery._shape_summary(body), separators=(",", ":")),
        )

    @staticmethod
    def _is_error_record(record: dict[str, Any]) -> bool:
        return "error" in record or "error_code" in record

    @staticmethod
    def _input_error(errors: list[dict[str, Any]], token: str) -> KeywordDiscoveryError:
        details = [
            {
                key: error[key]
                for key in ("error_code", "error")
                if key in error
            }
            for error in errors[:5]
        ]
        safe_details = _redact(details, token)
        return KeywordDiscoveryError(
            "Bright Data could not collect the supplied input",
            provider_detail=json.dumps(safe_details, ensure_ascii=False, separators=(",", ":"))[:2000],
        )

    @staticmethod
    def _shape_summary(body: Any) -> dict[str, Any]:
        if isinstance(body, dict):
            summary: dict[str, Any] = {"type": "object", "keys": sorted(str(key) for key in body)}
            for key, value in body.items():
                if isinstance(value, list):
                    entry: dict[str, Any] = {"type": "array", "length": len(value)}
                    if value and isinstance(value[0], dict):
                        entry["first_item_keys"] = sorted(str(item_key) for item_key in value[0])
                    summary[str(key)] = entry
                elif isinstance(value, dict):
                    summary[str(key)] = {"type": "object", "keys": sorted(str(item_key) for item_key in value)}
                else:
                    summary[str(key)] = {"type": type(value).__name__}
            return summary
        if isinstance(body, list):
            return {
                "type": "array",
                "length": len(body),
                "first_item_keys": sorted(str(key) for key in body[0]) if body and isinstance(body[0], dict) else [],
            }
        return {"type": type(body).__name__}

    @staticmethod
    def _validate_snapshot_id(snapshot_id: str) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", snapshot_id):
            raise ValueError("invalid snapshot ID")

    @staticmethod
    def _provider_detail(body: Any, token: str) -> str:
        safe_body = json.dumps(_redact(body, token), ensure_ascii=False, separators=(",", ":"))
        return safe_body[:2000]


keyword_discovery = BrightDataKeywordDiscovery()
