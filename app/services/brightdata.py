"""Small asynchronous Bright Data API client."""

import logging
import re
from typing import Any

import httpx

from app.config import Settings, settings

logger = logging.getLogger(__name__)
_SNAPSHOT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class BrightDataError(RuntimeError):
    """Safe provider error suitable for returning to API callers."""


class BrightDataClient:
    def __init__(self, config: Settings = settings, http_client: httpx.AsyncClient | None = None):
        self.config = config
        self._http_client = http_client

    def _headers(self) -> dict[str, str]:
        if self.config.brightdata_api_token is None or not self.config.brightdata_api_token.get_secret_value():
            raise BrightDataError("Bright Data credentials are not configured")
        return {
            "Authorization": f"Bearer {self.config.brightdata_api_token.get_secret_value()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.config.brightdata_base_url.rstrip('/')}{path}"
        try:
            if self._http_client is None:
                async with httpx.AsyncClient(timeout=self.config.request_timeout_seconds) as client:
                    response = await client.request(method, url, params=params, json=json, headers=self._headers())
            else:
                response = await self._http_client.request(
                    method, url, params=params, json=json, headers=self._headers()
                )
        except httpx.TimeoutException as exc:
            raise BrightDataError("Bright Data request timed out") from exc
        except httpx.RequestError as exc:
            raise BrightDataError("Bright Data could not be reached") from exc

        if response.is_error:
            # Provider bodies can echo request data or credentials; do not return them.
            logger.warning("Bright Data request failed method=%s path=%s status=%s", method, path, response.status_code)
            raise BrightDataError(f"Bright Data returned HTTP {response.status_code}")
        logger.info("Bright Data request completed method=%s path=%s status=%s", method, path, response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def trigger(self, dataset_id: str, payload: dict[str, Any]) -> Any:
        return await self._request(
            "POST",
            "/datasets/v3/trigger",
            params={"dataset_id": dataset_id, "include_errors": "true"},
            json=payload,
        )

    async def progress(self, snapshot_id: str) -> Any:
        self._validate_snapshot_id(snapshot_id)
        return await self._request("GET", f"/datasets/v3/progress/{snapshot_id}")

    async def snapshot(self, snapshot_id: str, output_format: str = "json") -> Any:
        self._validate_snapshot_id(snapshot_id)
        return await self._request(
            "GET", f"/datasets/v3/snapshot/{snapshot_id}", params={"format": output_format}
        )

    @staticmethod
    def _validate_snapshot_id(snapshot_id: str) -> None:
        if not _SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
            raise BrightDataError("Invalid Bright Data snapshot ID")


client = BrightDataClient()
