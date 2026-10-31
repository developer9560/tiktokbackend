"""SQLAlchemy 2.x models for persisted search jobs and video decisions."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    min_views: Mapped[int | None] = mapped_column(Integer)
    max_views: Mapped[int | None] = mapped_column(Integer)
    min_age_days: Mapped[int | None] = mapped_column(Integer)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_language: Mapped[str | None] = mapped_column(String(35))
    language_requirement: Mapped[str] = mapped_column(String(20), nullable=False, default="spoken")
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(128), index=True)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unverified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video_links: Mapped[list["SearchJobVideo"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    attempts: Mapped[list["CollectionAttempt"]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_search_jobs_status_created", "status", "created_at"),)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    provider_post_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    created_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    view_count: Mapped[int | None] = mapped_column(Integer, index=True)
    like_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    share_count: Mapped[int | None] = mapped_column(Integer)
    collect_count: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    hashtags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    creator_id: Mapped[str | None] = mapped_column(String(128))
    creator_username: Mapped[str | None] = mapped_column(String(255), index=True)
    creator_url: Mapped[str | None] = mapped_column(String(2048))
    creator_avatar_url: Mapped[str | None] = mapped_column(String(2048))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    video_source_url: Mapped[str | None] = mapped_column(String(2048))
    region: Mapped[str | None] = mapped_column(String(32))
    original_sound_json: Mapped[Any | None] = mapped_column(JSON)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    job_links: Mapped[list["SearchJobVideo"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class SearchJobVideo(Base):
    __tablename__ = "search_job_videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    search_job_id: Mapped[str] = mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    rejection_reasons_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    category_label: Mapped[str | None] = mapped_column(String(100))
    category_method: Mapped[str | None] = mapped_column(String(32))
    category_confidence: Mapped[float | None] = mapped_column(Float)
    detected_language: Mapped[str | None] = mapped_column(String(35))
    language_evidence_type: Mapped[str | None] = mapped_column(String(32))
    language_confidence: Mapped[float | None] = mapped_column(Float)
    language_status: Mapped[str | None] = mapped_column(String(32))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    job: Mapped[SearchJob] = relationship(back_populates="video_links")
    video: Mapped[Video] = relationship(back_populates="job_links")

    __table_args__ = (
        UniqueConstraint("search_job_id", "video_id", name="uq_job_video"),
        Index("ix_search_job_videos_job_decision", "search_job_id", "decision"),
    )


class CollectionAttempt(Base):
    __tablename__ = "collection_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    search_job_id: Mapped[str] = mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(128))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    response_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[SearchJob] = relationship(back_populates="attempts")
