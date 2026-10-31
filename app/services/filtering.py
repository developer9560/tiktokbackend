"""Authoritative, explainable filtering and language-evidence decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.config import settings
from app.models import SearchJob
from app.services.video_normalization import NormalizedVideo

DetectorFactory.seed = 0
_HASHTAG_PATTERN = re.compile(r"#[\w\u0080-\uffff]+", re.UNICODE)


@dataclass(frozen=True)
class FilterDecision:
    decision: str
    reasons: list[str]
    category_label: str | None
    category_method: str | None
    category_confidence: float | None
    detected_language: str | None
    language_evidence_type: str | None
    language_confidence: float | None
    language_status: str | None


def _detect_text_language(description: str | None) -> tuple[str | None, float | None]:
    if not description:
        return None, None
    text_only = _HASHTAG_PATTERN.sub(" ", description).strip()
    if len(text_only) < 20 or len(re.findall(r"[A-Za-z\u00C0-\u024F\u0400-\u04FF]", text_only)) < 12:
        return None, None
    try:
        predictions = detect_langs(text_only)
    except LangDetectException:
        return None, None
    if not predictions:
        return None, None
    return predictions[0].lang, float(predictions[0].prob)


def evaluate_video(video: NormalizedVideo, job: SearchJob) -> FilterDecision:
    reasons: list[str] = []
    category_label: str | None = None
    category_method: str | None = None
    category_confidence: float | None = None

    if job.min_age_days is not None:
        if video.created_at_source is None:
            reasons.append("upload_date_missing_or_invalid")
        else:
            cutoff = job.cutoff_at
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            required_cutoff = cutoff.astimezone(timezone.utc) - timedelta(days=job.min_age_days)
            if video.created_at_source > required_cutoff:
                reasons.append("video_too_recent")

    if job.min_views is not None or job.max_views is not None:
        if video.view_count is None:
            reasons.append("view_count_missing_or_invalid")
        elif job.min_views is not None and video.view_count < job.min_views:
            reasons.append("views_below_minimum")
        elif job.max_views is not None and video.view_count > job.max_views:
            reasons.append("views_above_maximum")

    if job.category:
        category = job.category.strip().casefold()
        description = video.description or ""
        matching_tags = [tag for tag in video.hashtags if category in tag.casefold()]
        if category in description.casefold() or matching_tags:
            category_label = job.category
            category_method = "description_hashtag_rule"
            category_confidence = 1.0
        else:
            reasons.append("category_not_found_in_description_or_hashtags")

    detected_language: str | None = None
    language_confidence: float | None = None
    language_status: str | None = None
    language_evidence_type: str | None = None
    if video.canonical_url is None:
        reasons.append("original_tiktok_url_missing_or_invalid")
    if job.target_language:
        if job.language_requirement == "spoken":
            language_status = "unverified"
            language_evidence_type = "unknown"
            reasons.append("spoken_language_evidence_unavailable")
        else:
            detected_language, language_confidence = _detect_text_language(video.description)
            language_evidence_type = "description" if detected_language else "unknown"
            if detected_language is None:
                language_status = "unverified"
                reasons.append("description_language_unverified")
            elif detected_language.casefold() != job.target_language.casefold():
                if language_confidence is not None and language_confidence >= settings.language_confidence_threshold:
                    language_status = "mismatch"
                    reasons.append("description_language_mismatch")
                else:
                    language_status = "unverified"
                    reasons.append("description_language_unverified")
            elif language_confidence is not None and language_confidence >= settings.language_confidence_threshold:
                language_status = "verified_match"
            else:
                language_status = "likely_match"
                reasons.append("description_language_confidence_below_threshold")

    hard_reasons = [reason for reason in reasons if reason not in {
        "spoken_language_evidence_unavailable",
        "description_language_unverified",
        "description_language_confidence_below_threshold",
    }]
    if hard_reasons:
        decision = "rejected"
    elif reasons:
        decision = "unverified"
    else:
        decision = "matched"

    return FilterDecision(
        decision=decision,
        reasons=reasons,
        category_label=category_label,
        category_method=category_method,
        category_confidence=category_confidence,
        detected_language=detected_language,
        language_evidence_type=language_evidence_type,
        language_confidence=language_confidence,
        language_status=language_status,
    )
