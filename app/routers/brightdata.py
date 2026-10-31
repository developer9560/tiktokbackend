"""Bright Data collection endpoints."""

from fastapi import APIRouter, HTTPException, Path, Query

from app.config import settings
from app.schemas import TriggerRequest, TriggerResponse
from app.services.brightdata import BrightDataError, client

router = APIRouter()


def _dataset_id(request_dataset_id: str | None) -> str:
    dataset_id = request_dataset_id or settings.brightdata_dataset_id
    if not dataset_id:
        raise HTTPException(status_code=503, detail="Bright Data dataset is not configured")
    return dataset_id


def _raise_provider_error(exc: BrightDataError) -> None:
    raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/config")
async def provider_config() -> dict[str, bool | str | None]:
    return {
        "token_configured": bool(
            settings.brightdata_api_token and "6d7e9eb7-b797-45db-9877-9dd89e48c85b"
        ),
        "dataset_configured": bool(settings.brightdata_keyword_dataset_id),
        "dataset_id": settings.brightdata_keyword_dataset_id,
        "keyword_dataset_id": settings.brightdata_keyword_dataset_id,
    }


@router.post("/jobs", response_model=TriggerResponse)
async def trigger_job(
    body: TriggerRequest,
    dataset_id: str | None = Query(default=None, min_length=1, max_length=128),
) -> TriggerResponse:
    selected_dataset = _dataset_id(dataset_id)
    try:
        result = await client.trigger(selected_dataset, body.payload)
    except BrightDataError as exc:
        _raise_provider_error(exc)
    snapshot_id = result.get("snapshot_id") if isinstance(result, dict) else None
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise HTTPException(status_code=502, detail="Bright Data trigger response did not include a snapshot ID")
    return TriggerResponse(dataset_id=selected_dataset, snapshot_id=snapshot_id, provider_response=result)


@router.get("/jobs/{snapshot_id}/progress")
async def job_progress(snapshot_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,128}$")) -> object:
    try:
        return await client.progress(snapshot_id)
    except BrightDataError as exc:
        _raise_provider_error(exc)


@router.get("/jobs/{snapshot_id}/results")
async def job_results(
    snapshot_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,128}$"),
    output_format: str = Query(default="json", pattern="^(json|ndjson|jsonl|csv)$"),
) -> object:
    try:
        return await client.snapshot(snapshot_id, output_format)
    except BrightDataError as exc:
        _raise_provider_error(exc)
