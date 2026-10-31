"""Defensive normalization for fields documented in the TikTok dataset response."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4


def _string(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.isdigit():
            return int(text)
    return None


def parse_source_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            seconds = float(value) / 1000 if value >= 10**12 else float(value)
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.isdigit():
        return parse_source_datetime(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_tiktok_url(value: Any) -> str | None:
    url = _string(value)
    if not url:
        return None
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
    except ValueError:
        return None
    if parsed.scheme != "https" or not (hostname == "tiktok.com" or hostname.endswith(".tiktok.com")):
        return None
    if parsed.username or parsed.password or not parsed.path:
        return None
    return urlunsplit(("https", hostname, parsed.path.rstrip("/"), "", ""))


def _hashtags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        tag = _string(item)
        if tag:
            clean = tag.lstrip("#").strip()
            if clean and clean.casefold() not in {existing.casefold() for existing in normalized}:
                normalized.append(clean)
    return normalized


@dataclass(frozen=True)
class NormalizedVideo:
    identity_key: str | None
    provider_post_id: str | None
    canonical_url: str | None
    description: str | None
    created_at_source: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None
    collect_count: int | None
    duration_seconds: float | None
    hashtags: list[str]
    creator_id: str | None
    creator_username: str | None
    creator_url: str | None
    creator_avatar_url: str | None
    thumbnail_url: str | None
    video_source_url: str | None
    region: str | None
    original_sound: Any | None
    raw_payload: dict[str, Any]


def normalize_video(payload: dict[str, Any]) -> NormalizedVideo:
    post_id = _string(payload.get("post_id"))
    canonical_url = canonical_tiktok_url(payload.get("url"))
    identity_key = f"post:{post_id}" if post_id else f"url:{canonical_url.casefold()}" if canonical_url else None
    duration = payload.get("video_duration")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0:
        duration_seconds: float | None = float(duration)
    else:
        duration_seconds = None

    return NormalizedVideo(
        identity_key=identity_key,
        provider_post_id=post_id,
        canonical_url=canonical_url,
        description=_string(payload.get("description")),
        created_at_source=parse_source_datetime(payload.get("create_time")),
        view_count=_count(payload.get("play_count")),
        like_count=_count(payload.get("digg_count")),
        comment_count=_count(payload.get("comment_count")),
        share_count=_count(payload.get("share_count")),
        collect_count=_count(payload.get("collect_count")),
        duration_seconds=duration_seconds,
        hashtags=_hashtags(payload.get("hashtags")),
        creator_id=_string(payload.get("profile_id")),
        creator_username=_string(payload.get("profile_username")),
        creator_url=canonical_tiktok_url(payload.get("profile_url")),
        creator_avatar_url=_string(payload.get("profile_avatar")),
        thumbnail_url=_string(payload.get("preview_image")),
        video_source_url=_string(payload.get("video_url")),
        region=_string(payload.get("region")),
        original_sound=payload.get("original_sound"),
        raw_payload=payload,
    )


def new_video_id() -> str:
    return str(uuid4())
