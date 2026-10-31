"""Search-job, progress, results, detail, and export API."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Generator
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import asc, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_session_factory
from app.models import CollectionAttempt, SearchJob, SearchJobVideo, Video, utc_now
from app.schemas import (
    CollectionProvenance,
    OverviewMetrics,
    PaginatedVideosResponse,
    SearchCriteriaRequest,
    SearchJobListResponse,
    SearchJobResponse,
    VideoResult,
)
from app.services.search_workflow import job_response_data

router = APIRouter(prefix="/api/v1", tags=["Search jobs"])


def _session() -> Generator[Session, None, None]:
    try:
        session = get_session_factory()()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail="Search database is not configured") from error
    try:
        yield session
    finally:
        session.close()


def _get_job(session: Session, job_id: str) -> SearchJob:
    job = session.get(SearchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Search job not found")
    return job


def _video_result(
    link: SearchJobVideo,
    video: Video,
    provenance: CollectionProvenance | None = None,
) -> VideoResult:
    return VideoResult(
        id=video.id,
        provider_post_id=video.provider_post_id,
        url=video.canonical_url,
        description=video.description,
        creator_id=video.creator_id,
        creator_username=video.creator_username,
        creator_url=video.creator_url,
        creator_avatar_url=video.creator_avatar_url,
        upload_date=video.created_at_source,
        views=video.view_count,
        likes=video.like_count,
        comments=video.comment_count,
        shares=video.share_count,
        saves=video.collect_count,
        duration_seconds=video.duration_seconds,
        hashtags=video.hashtags_json or [],
        thumbnail_url=video.thumbnail_url,
        original_sound=video.original_sound_json,
        region=video.region,
        category=link.category_label,
        category_method=link.category_method,
        category_confidence=link.category_confidence,
        detected_language=link.detected_language,
        language_evidence_type=link.language_evidence_type,
        language_confidence=link.language_confidence,
        language_status=link.language_status,
        decision=link.decision,
        rejection_reasons=link.rejection_reasons_json or [],
        first_seen_at=video.first_seen_at,
        last_seen_at=video.last_seen_at,
        collection_provenance=provenance,
    )


def _query_results(
    session: Session,
    job_id: str,
    *,
    page: int,
    page_size: int,
    sort_by: str,
    order: str,
    decision: Literal["all", "matched", "unverified", "rejected"] | None = None,
    include_unverified: bool | None = None,
    search: str | None = None,
) -> tuple[list[VideoResult], int]:
    _get_job(session, job_id)
    if decision == "all" or (decision is None and include_unverified is None):
        decisions = ["matched", "unverified", "rejected"]
    elif decision is not None:
        decisions = [decision]
    elif include_unverified:
        decisions = ["matched", "unverified"]
    else:
        decisions = ["matched"]
    conditions = [SearchJobVideo.search_job_id == job_id, SearchJobVideo.decision.in_(decisions)]
    if search:
        escaped_search = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        conditions.append(
            or_(
                Video.description.ilike(f"%{escaped_search}%", escape="\\"),
                Video.creator_username.ilike(f"%{escaped_search}%", escape="\\"),
            )
        )
    total = session.scalar(
        select(func.count())
        .select_from(SearchJobVideo)
        .join(Video, Video.id == SearchJobVideo.video_id)
        .where(*conditions)
    ) or 0
    sort_columns = {
        "views": Video.view_count,
        "upload_date": Video.created_at_source,
        "creator": Video.creator_username,
    }
    sort_column = sort_columns[sort_by]
    ordering = asc(sort_column) if order == "asc" else desc(sort_column)
    rows = session.execute(
        select(SearchJobVideo, Video)
        .join(Video, Video.id == SearchJobVideo.video_id)
        .where(*conditions)
        .order_by(asc(case((sort_column.is_(None), 1), else_=0)), ordering, Video.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_video_result(link, video) for link, video in rows], int(total)


@router.post("/search-jobs", response_model=SearchJobResponse, status_code=202)
def create_search_job(
    criteria: SearchCriteriaRequest,
    session: Session = Depends(_session),
) -> SearchJobResponse:
    if criteria.target_count > settings.max_search_target_count:
        raise HTTPException(
            status_code=422,
            detail=f"target_count must be no greater than {settings.max_search_target_count}",
        )
    job = SearchJob(
        id=str(uuid4()),
        keyword=criteria.keyword,
        category=criteria.category,
        min_views=criteria.min_views,
        max_views=criteria.max_views,
        min_age_days=criteria.min_age_days,
        cutoff_at=utc_now(),
        target_language=criteria.target_language.lower() if criteria.target_language else None,
        language_requirement=criteria.language_requirement,
        target_count=criteria.target_count,
        status="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return SearchJobResponse.model_validate(job_response_data(job))


@router.get("/search-jobs", response_model=SearchJobListResponse)
def list_search_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, max_length=32),
    session: Session = Depends(_session),
) -> SearchJobListResponse:
    query = select(SearchJob)
    count_query = select(func.count()).select_from(SearchJob)
    if status:
        query = query.where(SearchJob.status == status)
        count_query = count_query.where(SearchJob.status == status)
    total = int(session.scalar(count_query) or 0)
    jobs = session.scalars(query.order_by(SearchJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return SearchJobListResponse(
        items=[SearchJobResponse.model_validate(job_response_data(job)) for job in jobs],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/search-jobs/{job_id}", response_model=SearchJobResponse)
def get_search_job(job_id: str, session: Session = Depends(_session)) -> SearchJobResponse:
    return SearchJobResponse.model_validate(job_response_data(_get_job(session, job_id)))


@router.get("/search-jobs/{job_id}/progress", response_model=SearchJobResponse)
def get_search_job_progress(job_id: str, session: Session = Depends(_session)) -> SearchJobResponse:
    return SearchJobResponse.model_validate(job_response_data(_get_job(session, job_id)))


@router.get("/overview", response_model=OverviewMetrics)
def get_overview_metrics(session: Session = Depends(_session)) -> OverviewMetrics:
    active_statuses = ("queued", "collecting", "retrieving", "processing")
    total_jobs = int(session.scalar(select(func.count()).select_from(SearchJob)) or 0)
    active_jobs = int(
        session.scalar(
            select(func.count()).select_from(SearchJob).where(SearchJob.status.in_(active_statuses))
        )
        or 0
    )
    unique_videos = int(session.scalar(select(func.count()).select_from(Video)) or 0)
    matching_videos = int(
        session.scalar(
            select(func.count()).select_from(SearchJobVideo).where(SearchJobVideo.decision == "matched")
        )
        or 0
    )
    unverified_videos = int(
        session.scalar(
            select(func.count(func.distinct(SearchJobVideo.video_id)))
            .select_from(SearchJobVideo)
            .where(SearchJobVideo.language_status.in_(("unverified", "likely_match")))
        )
        or 0
    )
    recent_failures = session.scalars(
        select(SearchJob)
        .where(SearchJob.status == "failed")
        .order_by(SearchJob.completed_at.desc(), SearchJob.created_at.desc())
        .limit(5)
    ).all()
    return OverviewMetrics(
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        unique_videos=unique_videos,
        matching_videos=matching_videos,
        unverified_videos=unverified_videos,
        recent_failures=[SearchJobResponse.model_validate(job_response_data(job)) for job in recent_failures],
    )


@router.get("/search-jobs/{job_id}/videos", response_model=PaginatedVideosResponse)
def get_search_job_videos(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    sort_by: Literal["views", "upload_date", "creator"] = "views",
    order: Literal["asc", "desc"] = "desc",
    decision: Literal["all", "matched", "unverified", "rejected"] | None = Query(default=None),
    include_unverified: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    session: Session = Depends(_session),
) -> PaginatedVideosResponse:
    items, total = _query_results(
        session,
        job_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
        decision=decision,
        include_unverified=include_unverified,
        search=search,
    )
    return PaginatedVideosResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/videos/{video_id}", response_model=VideoResult)
def get_video_detail(video_id: str, session: Session = Depends(_session)) -> VideoResult:
    row = session.execute(
        select(SearchJobVideo, Video)
        .join(Video, Video.id == SearchJobVideo.video_id)
        .where(Video.id == video_id)
        .order_by(SearchJobVideo.processed_at.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Video not found")
    link, video = row
    attempt = session.scalar(
        select(CollectionAttempt)
        .where(CollectionAttempt.search_job_id == link.search_job_id)
        .order_by(CollectionAttempt.started_at.desc())
        .limit(1)
    )
    provenance = (
        CollectionProvenance(
            search_job_id=link.search_job_id,
            dataset_id=attempt.dataset_id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
        )
        if attempt is not None
        else None
    )
    return _video_result(link, video, provenance)


@router.get("/search-jobs/{job_id}/videos/export")
def export_search_job_videos(
    job_id: str,
    output_format: Literal["json", "csv"] = "json",
    decision: Literal["all", "matched", "unverified", "rejected"] | None = None,
    include_unverified: bool | None = None,
    search: str | None = Query(default=None, min_length=1, max_length=200),
    session: Session = Depends(_session),
) -> Response:
    page = 1
    results: list[VideoResult] = []
    while True:
        items, total = _query_results(
            session,
            job_id,
            page=page,
            page_size=100,
            sort_by="views",
            order="desc",
            decision=decision,
            include_unverified=include_unverified,
            search=search,
        )
        results.extend(items)
        if len(results) >= total or not items:
            break
        page += 1
    if output_format == "json":
        from fastapi.encoders import jsonable_encoder

        return Response(
            content=json.dumps(jsonable_encoder(results), ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{job_id}-videos.json"'},
        )

    buffer = io.StringIO(newline="")
    fields = list(VideoResult.model_fields)
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in results:
        row = item.model_dump(mode="json")
        for key, value in row.items():
            if isinstance(value, (list, dict)):
                row[key] = json.dumps(value, ensure_ascii=False)
        writer.writerow(row)
    headers = {"Content-Disposition": f'attachment; filename="{job_id}-videos.csv"'}
    return Response(content=buffer.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
