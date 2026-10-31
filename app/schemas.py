"""Provider-neutral API schemas; dataset payloads remain caller-defined."""

from typing import Any

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any] = Field(description="Exact JSON body required by the configured dataset")


class TriggerResponse(BaseModel):
    dataset_id: str
    snapshot_id: str | None = None
    provider_response: Any


class HealthResponse(BaseModel):
    status: str


class SearchCriteriaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    keyword: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    min_views: int | None = Field(default=None, ge=0)
    max_views: int | None = Field(default=None, ge=0)
    min_age_days: int | None = Field(default=None, ge=0, le=36500)
    target_language: str | None = Field(default=None, min_length=2, max_length=3, pattern=r"^[a-zA-Z]{2,3}$")
    language_requirement: Literal["spoken", "text"] = "spoken"
    target_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_view_range(self) -> "SearchCriteriaRequest":
        if self.min_views is not None and self.max_views is not None and self.min_views > self.max_views:
            raise ValueError("min_views must be less than or equal to max_views")
        return self


class SearchCounts(BaseModel):
    discovered: int
    processed: int
    matched: int
    rejected: int
    duplicates: int
    unverified: int


class SearchJobResponse(BaseModel):
    id: str
    status: str
    criteria: SearchCriteriaRequest
    counts: SearchCounts
    cutoff_at: datetime
    shortfall: int | None = None
    snapshot_id: str | None = None
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class SearchJobListResponse(BaseModel):
    items: list[SearchJobResponse]
    page: int
    page_size: int
    total: int


class OverviewMetrics(BaseModel):
    total_jobs: int
    active_jobs: int
    unique_videos: int
    matching_videos: int
    unverified_videos: int
    recent_failures: list[SearchJobResponse]


class CollectionProvenance(BaseModel):
    search_job_id: str
    dataset_id: str
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None


class VideoResult(BaseModel):
    id: str
    provider_post_id: str | None
    url: str | None
    description: str | None
    creator_id: str | None
    creator_username: str | None
    creator_url: str | None
    creator_avatar_url: str | None
    upload_date: datetime | None
    views: int | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    duration_seconds: float | None
    hashtags: list[str]
    thumbnail_url: str | None
    original_sound: Any | None
    region: str | None
    category: str | None
    category_method: str | None
    category_confidence: float | None
    detected_language: str | None
    language_evidence_type: str | None
    language_confidence: float | None
    language_status: str | None
    decision: str
    rejection_reasons: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    collection_provenance: CollectionProvenance | None = None


class PaginatedVideosResponse(BaseModel):
    items: list[VideoResult]
    page: int
    page_size: int
    total: int
    total_pages: int
