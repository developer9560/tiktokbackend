import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, SearchJob, SearchJobVideo, Video
from app.services.filtering import evaluate_video
from app.services.search_workflow import process_records
from app.services.video_normalization import canonical_tiktok_url, normalize_video, parse_source_datetime

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "brightdata_keyword_sample.json").read_text(encoding="utf-8"))[0]


def test_normalize_documented_fields_and_safe_url() -> None:
    video = normalize_video(FIXTURE)
    assert video.identity_key == "url:https://www.tiktok.com/@football_skills_81/video/7664728137988656417"
    assert video.view_count == 268000
    assert video.hashtags == ["football", "respect", "moment"]
    assert video.created_at_source == datetime(2026, 7, 20, 21, 39, 49, tzinfo=timezone.utc)
    assert video.raw_payload == FIXTURE
    assert canonical_tiktok_url("https://attacker.example/video") is None
    assert canonical_tiktok_url("http://www.tiktok.com/video/1") is None


def test_parse_epoch_and_naive_timestamp_as_utc() -> None:
    assert parse_source_datetime(1_700_000_000) == datetime.fromtimestamp(1_700_000_000, timezone.utc)
    assert parse_source_datetime("2026-07-20T21:39:49") == datetime(2026, 7, 20, 21, 39, 49, tzinfo=timezone.utc)
    assert parse_source_datetime("not-a-date") is None


def make_job(**overrides: object) -> SearchJob:
    values: dict[str, object] = {
        "id": "job-test",
        "keyword": "football",
        "category": "football",
        "min_views": 500,
        "max_views": 500000,
        "min_age_days": 2,
        "cutoff_at": datetime(2026, 10, 30, tzinfo=timezone.utc),
        "target_language": None,
        "language_requirement": "spoken",
        "target_count": 10,
        "status": "processing",
    }
    values.update(overrides)
    return SearchJob(**values)  # type: ignore[arg-type]


def test_filters_are_inclusive_and_use_saved_age_cutoff() -> None:
    video = normalize_video(FIXTURE)
    decision = evaluate_video(video, make_job())
    assert decision.decision == "matched"
    assert decision.reasons == []
    assert decision.category_label == "football"

    too_new = normalize_video({**FIXTURE, "create_time": "2026-10-29T12:00:00Z"})
    assert "video_too_recent" in evaluate_video(too_new, make_job()).reasons

    below_range = normalize_video({**FIXTURE, "play_count": 499})
    assert "views_below_minimum" in evaluate_video(below_range, make_job()).reasons
    above_range = normalize_video({**FIXTURE, "play_count": 500001})
    assert "views_above_maximum" in evaluate_video(above_range, make_job()).reasons


def test_missing_view_and_spoken_language_evidence_never_match() -> None:
    missing_views = normalize_video({**FIXTURE, "play_count": None})
    assert "view_count_missing_or_invalid" in evaluate_video(missing_views, make_job()).reasons

    spoken_job = make_job(target_language="ru", language_requirement="spoken")
    decision = evaluate_video(normalize_video(FIXTURE), spoken_job)
    assert decision.decision == "unverified"
    assert decision.language_status == "unverified"
    assert decision.detected_language is None
    assert decision.language_evidence_type == "unknown"


def test_process_records_persists_explanations_and_deduplicates(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'search-test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        job = make_job(target_count=2)
        session.add(job)
        session.commit()
        process_records(session, job, [FIXTURE, FIXTURE])
        session.refresh(job)

        assert job.status == "partially_completed"
        assert job.discovered_count == 2
        assert job.processed_count == 2
        assert job.matched_count == 1
        assert job.duplicate_count == 1
        assert "Filters were not relaxed" in (job.error_summary or "")
        link = session.scalar(select(SearchJobVideo).where(SearchJobVideo.search_job_id == job.id))
        video = session.get(Video, link.video_id)
        assert link.decision == "matched"
        assert link.rejection_reasons_json == []
        assert video.raw_payload == FIXTURE
    engine.dispose()


def test_spoken_target_is_counted_unverified_and_not_matched(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'language-test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        job = make_job(target_count=1, target_language="ru", language_requirement="spoken")
        session.add(job)
        session.commit()
        process_records(session, job, [FIXTURE])
        session.refresh(job)
        assert job.matched_count == 0
        assert job.unverified_count == 1
        link = session.scalar(select(SearchJobVideo).where(SearchJobVideo.search_job_id == job.id))
        assert link.decision == "unverified"
        assert "spoken_language_evidence_unavailable" in link.rejection_reasons_json
    engine.dispose()


def test_empty_provider_snapshot_completes_with_zero_matches(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'empty-search.db'}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        job = make_job(target_count=5)
        session.add(job)
        session.commit()
        process_records(session, job, [])
        session.refresh(job)
        assert job.status == "completed"
        assert job.matched_count == 0
        assert "provider returned no records" in (job.error_summary or "").lower()
    engine.dispose()
