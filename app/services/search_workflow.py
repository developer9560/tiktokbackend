"""Persistent keyword search processing and restart-aware snapshot worker."""

from __future__ import annotations

import logging
import threading
from datetime import timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import get_session_factory
from app.models import CollectionAttempt, SearchJob, SearchJobVideo, Video, utc_now
from app.services.filtering import evaluate_video
from app.services.keyword_discovery import KeywordDiscoveryError, keyword_discovery
from app.services.video_normalization import normalize_video

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = ("collecting", "retrieving", "processing")


def _new_id() -> str:
    return str(uuid4())


def _job_criteria(job: SearchJob) -> dict[str, Any]:
    return {
        "keyword": job.keyword,
        "category": job.category,
        "min_views": job.min_views,
        "max_views": job.max_views,
        "min_age_days": job.min_age_days,
        "target_language": job.target_language,
        "language_requirement": job.language_requirement,
        "target_count": job.target_count,
    }


def process_records(session: Session, job: SearchJob, records: list[dict[str, Any]]) -> None:
    """Normalize, deduplicate, filter, and persist one provider result set."""
    session.query(SearchJobVideo).filter(SearchJobVideo.search_job_id == job.id).delete(synchronize_session=False)
    job.status = "processing"
    job.discovered_count = len(records)
    job.processed_count = 0
    job.matched_count = 0
    job.rejected_count = 0
    job.duplicate_count = 0
    job.unverified_count = 0
    job.error_summary = None
    job.completed_at = None
    session.commit()

    seen_in_collection: set[str] = set()
    for index, payload in enumerate(records):
        normalized = normalize_video(payload)
        identity_key = normalized.identity_key or f"unkeyed:{job.id}:{index}"
        job.processed_count += 1
        if identity_key in seen_in_collection:
            job.duplicate_count += 1
            continue
        seen_in_collection.add(identity_key)

        video = None
        if normalized.provider_post_id:
            video = session.scalar(
                select(Video).where(Video.provider_post_id == normalized.provider_post_id)
            )
        if video is None:
            video = session.scalar(select(Video).where(Video.identity_key == identity_key))
        if video is None and normalized.canonical_url:
            video = session.scalar(select(Video).where(Video.canonical_url == normalized.canonical_url))
        if video is not None and video.identity_key != identity_key:
            video.identity_key = identity_key
        if video is None:
            video = Video(id=_new_id(), identity_key=identity_key, raw_payload=normalized.raw_payload)
            session.add(video)
        else:
            video.last_seen_at = utc_now()
            video.raw_payload = normalized.raw_payload

        video.provider_post_id = normalized.provider_post_id
        video.canonical_url = normalized.canonical_url
        video.description = normalized.description
        video.created_at_source = normalized.created_at_source
        video.view_count = normalized.view_count
        video.like_count = normalized.like_count
        video.comment_count = normalized.comment_count
        video.share_count = normalized.share_count
        video.collect_count = normalized.collect_count
        video.duration_seconds = normalized.duration_seconds
        video.hashtags_json = normalized.hashtags
        video.creator_id = normalized.creator_id
        video.creator_username = normalized.creator_username
        video.creator_url = normalized.creator_url
        video.creator_avatar_url = normalized.creator_avatar_url
        video.thumbnail_url = normalized.thumbnail_url
        video.video_source_url = normalized.video_source_url
        video.region = normalized.region
        video.original_sound_json = normalized.original_sound
        video.last_seen_at = utc_now()
        session.flush()

        decision = evaluate_video(normalized, job)
        link = SearchJobVideo(
            id=_new_id(),
            search_job_id=job.id,
            video_id=video.id,
            decision=decision.decision,
            rejection_reasons_json=decision.reasons,
            category_label=decision.category_label,
            category_method=decision.category_method,
            category_confidence=decision.category_confidence,
            detected_language=decision.detected_language,
            language_evidence_type=decision.language_evidence_type,
            language_confidence=decision.language_confidence,
            language_status=decision.language_status,
        )
        session.add(link)
        if decision.decision == "matched":
            job.matched_count += 1
        elif decision.decision == "rejected":
            job.rejected_count += 1
        if decision.language_status == "unverified" or decision.decision == "unverified":
            job.unverified_count += 1

        if (index + 1) % 50 == 0:
            session.commit()

    if not records:
        job.status = "completed"
        job.error_summary = (
            f"The provider returned no records; 0 of {job.target_count} requested videos matched."
        )
    elif job.matched_count >= job.target_count:
        job.status = "completed"
        job.error_summary = None
    else:
        job.status = "partially_completed"
        job.error_summary = (
            f"{job.matched_count} of {job.target_count} requested videos matched. "
            "Filters were not relaxed to reach the target."
        )
    job.updated_at = utc_now()
    job.completed_at = utc_now()
    session.commit()


def recover_after_restart(session_factory: sessionmaker[Session]) -> None:
    """Keep resumable provider snapshots; fail interrupted sync calls safely."""
    with session_factory() as session:
        interrupted = session.scalars(
            select(SearchJob).where(SearchJob.status.in_(ACTIVE_STATUSES), SearchJob.snapshot_id.is_(None))
        ).all()
        for job in interrupted:
            job.status = "failed"
            job.error_summary = "The backend stopped before a resumable provider snapshot was recorded."
            job.completed_at = utc_now()
        if interrupted:
            session.commit()


class SearchWorkflowWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        poll_interval: float | None = None,
    ):
        self.session_factory = session_factory or get_session_factory()
        self.poll_interval = poll_interval or settings.snapshot_poll_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        recover_after_restart(self.session_factory)
        self._thread = threading.Thread(target=self._run, name="clip-scope-search-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            job_id, status = self._next_job()
            if job_id is None:
                self._stop.wait(self.poll_interval)
                continue
            try:
                if status == "queued":
                    self._collect(job_id)
                else:
                    self._retrieve_if_ready(job_id)
            except Exception:
                logger.exception("Search worker failed job_id=%s", job_id)
                self._mark_failed(job_id, "Search processing failed unexpectedly.", "internal_error")
            self._stop.wait(self.poll_interval)

    def _next_job(self) -> tuple[str | None, str | None]:
        with self.session_factory() as session:
            queued = session.scalar(
                select(SearchJob).where(SearchJob.status == "queued").order_by(SearchJob.created_at).limit(1)
            )
            if queued:
                return queued.id, queued.status
            resumable = session.scalar(
                select(SearchJob)
                .where(SearchJob.status.in_(ACTIVE_STATUSES), SearchJob.snapshot_id.is_not(None))
                .order_by(SearchJob.updated_at)
                .limit(1)
            )
            return (resumable.id, resumable.status) if resumable else (None, None)

    def _collect(self, job_id: str) -> None:
        with self.session_factory() as session:
            job = session.get(SearchJob, job_id)
            if job is None or job.status != "queued":
                return
            attempt = CollectionAttempt(
                id=_new_id(),
                search_job_id=job.id,
                dataset_id=settings.brightdata_keyword_dataset_id,
                attempt_number=len(job.attempts) + 1,
                status="running",
                request_metadata_json={
                    "keyword": job.keyword,
                    "country": "",
                    "limit_per_input": None,
                    "collection_batch_limit": settings.max_search_batches,
                    "collection_timeout_seconds": settings.max_collection_duration_seconds,
                },
                started_at=utc_now(),
            )
            job.status = "collecting"
            session.add(attempt)
            session.commit()

        try:
            result = keyword_discovery.search(keyword=job.keyword, country="")
            with self.session_factory() as session:
                job = session.get(SearchJob, job_id)
                attempt = session.scalar(
                    select(CollectionAttempt)
                    .where(CollectionAttempt.search_job_id == job_id)
                    .order_by(CollectionAttempt.started_at.desc())
                    .limit(1)
                )
                if job is None or attempt is None:
                    return
                if result.snapshot_id:
                    job.snapshot_id = result.snapshot_id
                    job.status = "collecting"
                    attempt.snapshot_id = result.snapshot_id
                    attempt.status = "snapshot_pending"
                    attempt.response_metadata_json = {
                        "http_status": result.status_code,
                        "response_kind": "snapshot",
                    }
                    session.commit()
                    return
                attempt.response_metadata_json = {
                    "http_status": result.status_code,
                    "response_kind": "records",
                    "record_count": len(result.records),
                }
                attempt.status = "processing"
                attempt.finished_at = utc_now()
                session.commit()
                process_records(session, job, result.records)
                attempt.status = "completed"
                attempt.finished_at = utc_now()
                session.commit()
        except KeywordDiscoveryError as error:
            detail = error.provider_detail
            summary = str(error) + (f": {detail}" if detail else "")
            self._mark_failed(job_id, summary[:2000], f"brightdata_{error.status_code}" if error.status_code else "brightdata_error")

    def _retrieve_if_ready(self, job_id: str) -> None:
        with self.session_factory() as session:
            job = session.get(SearchJob, job_id)
            if job is None or not job.snapshot_id:
                return
            snapshot_id = job.snapshot_id
            attempt = session.scalar(
                select(CollectionAttempt)
                .where(CollectionAttempt.search_job_id == job_id)
                .order_by(CollectionAttempt.started_at.desc())
                .limit(1)
            )
            if attempt is not None:
                started_at = attempt.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                elapsed_seconds = (utc_now() - started_at).total_seconds()
                if elapsed_seconds >= settings.max_collection_duration_seconds:
                    self._mark_failed(
                        job_id,
                        "The collection exceeded the configured time limit before its snapshot was ready.",
                        "collection_timeout",
                    )
                    return
        try:
            progress = keyword_discovery.get_progress(snapshot_id)
            provider_status = progress["status"]
            if provider_status in {"starting", "running"}:
                return
            if provider_status == "failed":
                self._mark_failed(job_id, "Bright Data reported that the collection snapshot failed.", "snapshot_failed")
                return
            if provider_status != "ready":
                self._mark_failed(job_id, "Bright Data returned an unknown snapshot status.", "unknown_snapshot_status")
                return

            with self.session_factory() as session:
                job = session.get(SearchJob, job_id)
                if job is None:
                    return
                job.status = "retrieving"
                session.commit()
            snapshot = keyword_discovery.get_snapshot(snapshot_id)
            with self.session_factory() as session:
                job = session.get(SearchJob, job_id)
                attempt = session.scalar(
                    select(CollectionAttempt)
                    .where(CollectionAttempt.search_job_id == job_id)
                    .order_by(CollectionAttempt.started_at.desc())
                    .limit(1)
                )
                if job is None:
                    return
                if attempt:
                    attempt.status = "processing"
                    attempt.response_metadata_json = {
                        "http_status": snapshot.status_code,
                        "response_kind": "snapshot_records",
                        "record_count": len(snapshot.records),
                    }
                process_records(session, job, snapshot.records)
                if attempt:
                    attempt.status = "completed"
                    attempt.finished_at = utc_now()
                    session.commit()
        except KeywordDiscoveryError as error:
            detail = error.provider_detail
            summary = str(error) + (f": {detail}" if detail else "")
            self._mark_failed(job_id, summary[:2000], f"brightdata_{error.status_code}" if error.status_code else "brightdata_error")

    def _mark_failed(self, job_id: str, summary: str, error_code: str) -> None:
        with self.session_factory() as session:
            job = session.get(SearchJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error_summary = summary[:2000]
            job.completed_at = utc_now()
            attempt = session.scalar(
                select(CollectionAttempt)
                .where(CollectionAttempt.search_job_id == job_id)
                .order_by(CollectionAttempt.started_at.desc())
                .limit(1)
            )
            if attempt:
                attempt.status = "failed"
                attempt.error_code = error_code
                attempt.error_summary = summary[:2000]
                attempt.finished_at = utc_now()
            session.commit()


def job_response_data(job: SearchJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "criteria": _job_criteria(job),
        "counts": {
            "discovered": job.discovered_count,
            "processed": job.processed_count,
            "matched": job.matched_count,
            "rejected": job.rejected_count,
            "duplicates": job.duplicate_count,
            "unverified": job.unverified_count,
        },
        "cutoff_at": job.cutoff_at,
        "shortfall": (
            max(job.target_count - job.matched_count, 0)
            if job.status in {"completed", "partially_completed"}
            else None
        ),
        "snapshot_id": job.snapshot_id,
        "error_summary": job.error_summary,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
    }
