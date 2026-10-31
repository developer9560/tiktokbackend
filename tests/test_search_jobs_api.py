import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, CollectionAttempt, SearchJob, SearchJobVideo, Video
from app.routers.search_jobs import (
    export_search_job_videos,
    get_overview_metrics,
    get_search_job_videos,
    get_video_detail,
)
from app.services.search_workflow import job_response_data


def test_search_filter_dashboard_metrics_video_detail_and_shortfall(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dashboard.db'}")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        job = SearchJob(
            id="job-1",
            keyword="football",
            cutoff_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
            target_count=5,
            status="partially_completed",
            matched_count=1,
        )
        matching_video = Video(
            id="video-1",
            identity_key="post:1",
            provider_post_id="1",
            canonical_url="https://www.tiktok.com/@creator/video/1",
            description="Football practice",
            creator_id="creator-id",
            creator_username="football_creator",
            original_sound_json={"title": "Original sound"},
            raw_payload={"post_id": "1"},
        )
        unverified_video = Video(
            id="video-2",
            identity_key="post:2",
            provider_post_id="2",
            canonical_url="https://www.tiktok.com/@other/video/2",
            description="Other topic",
            creator_username="other_creator",
            raw_payload={"post_id": "2"},
        )
        session.add_all([job, matching_video, unverified_video])
        session.flush()
        session.add_all(
            [
                SearchJobVideo(
                    id="link-1",
                    search_job_id=job.id,
                    video_id=matching_video.id,
                    decision="matched",
                    category_label="football",
                    category_method="description_keyword",
                    category_confidence=0.93,
                ),
                SearchJobVideo(
                    id="link-2",
                    search_job_id=job.id,
                    video_id=unverified_video.id,
                    decision="unverified",
                    language_status="unverified",
                ),
                CollectionAttempt(
                    id="attempt-1",
                    search_job_id=job.id,
                    dataset_id="gd_lu702nij2f790tmv9h",
                    attempt_number=1,
                    status="completed",
                    request_metadata_json={"keyword": "football"},
                    started_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
                    finished_at=datetime(2026, 10, 30, 0, 1, tzinfo=timezone.utc),
                ),
            ]
        )
        session.commit()

        assert job_response_data(job)["shortfall"] == 4
        metrics = get_overview_metrics(session)
        assert metrics.total_jobs == 1
        assert metrics.active_jobs == 0
        assert metrics.unique_videos == 2
        assert metrics.matching_videos == 1
        assert metrics.unverified_videos == 1

        results = get_search_job_videos(
            job.id,
            page=1,
            page_size=24,
            sort_by="views",
            order="desc",
            decision=None,
            include_unverified=False,
            search="football",
            session=session,
        )
        assert results.total == 1
        assert results.items[0].creator_id == "creator-id"
        assert results.items[0].original_sound == {"title": "Original sound"}
        assert results.items[0].category_confidence == 0.93
        assert results.items[0].first_seen_at is not None
        assert results.items[0].last_seen_at is not None

        details = get_video_detail(matching_video.id, session)
        assert details.provider_post_id == "1"
        assert details.category_method == "description_keyword"
        assert details.category_confidence == 0.93
        assert details.first_seen_at is not None
        assert details.last_seen_at is not None
        assert details.collection_provenance is not None
        assert details.collection_provenance.dataset_id == "gd_lu702nij2f790tmv9h"

    engine.dispose()


def test_video_sort_places_null_values_last_for_both_directions(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'video-sort.db'}")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        job = SearchJob(
            id="job-sort",
            keyword="test",
            cutoff_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
            target_count=2,
            status="completed",
        )
        populated_video = Video(
            id="video-populated",
            identity_key="post:populated",
            view_count=100,
            raw_payload={},
        )
        null_video = Video(
            id="video-null",
            identity_key="post:null",
            view_count=None,
            raw_payload={},
        )
        session.add_all([job, populated_video, null_video])
        session.flush()
        session.add_all(
            [
                SearchJobVideo(
                    id="link-populated",
                    search_job_id=job.id,
                    video_id=populated_video.id,
                    decision="matched",
                ),
                SearchJobVideo(
                    id="link-null",
                    search_job_id=job.id,
                    video_id=null_video.id,
                    decision="matched",
                ),
            ]
        )
        session.commit()

        for order in ("asc", "desc"):
            results = get_search_job_videos(
                job.id,
                page=1,
                page_size=24,
                sort_by="views",
                order=order,
                decision=None,
                include_unverified=False,
                search=None,
                session=session,
            )
            assert [item.id for item in results.items] == ["video-populated", "video-null"]

    engine.dispose()


def test_all_decisions_are_queryable_and_exports_download_selected_records(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'all-video-decisions.db'}")
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as session:
        job = SearchJob(
            id="job-decisions",
            keyword="football",
            cutoff_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
            target_count=10,
            status="partially_completed",
        )
        decisions = ("matched", "unverified", "rejected")
        videos = [
            Video(id=f"video-{decision}", identity_key=f"post:{decision}", raw_payload={})
            for decision in decisions
        ]
        session.add(job)
        session.add_all(videos)
        session.flush()
        session.add_all(
            SearchJobVideo(
                id=f"link-{decision}",
                search_job_id=job.id,
                video_id=video.id,
                decision=decision,
                rejection_reasons_json=["video_too_recent"] if decision == "rejected" else [],
            )
            for decision, video in zip(decisions, videos)
        )
        session.commit()

        all_results = get_search_job_videos(
            job.id,
            page=1,
            page_size=24,
            sort_by="views",
            order="desc",
            decision="all",
            include_unverified=None,
            search=None,
            session=session,
        )
        assert all_results.total == 3
        assert {item.decision for item in all_results.items} == set(decisions)

        for selected in decisions:
            results = get_search_job_videos(
                job.id,
                page=1,
                page_size=24,
                sort_by="views",
                order="desc",
                decision=selected,
                include_unverified=None,
                search=None,
                session=session,
            )
            assert results.total == 1
            assert results.items[0].decision == selected

        json_response = export_search_job_videos(
            job.id,
            output_format="json",
            decision="all",
            include_unverified=None,
            search=None,
            session=session,
        )
        assert json_response.media_type == "application/json"
        assert json_response.headers["content-disposition"].endswith(f'{job.id}-videos.json"')
        assert len(json.loads(json_response.body)) == 3

        csv_response = export_search_job_videos(
            job.id,
            output_format="csv",
            decision="all",
            include_unverified=None,
            search=None,
            session=session,
        )
        assert csv_response.media_type == "text/csv; charset=utf-8"
        assert csv_response.headers["content-disposition"].endswith(f'{job.id}-videos.csv"')
        assert len(csv_response.body.decode("utf-8").splitlines()) == 4

    engine.dispose()
