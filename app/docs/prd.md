# Product Requirements Document (PRD)

## TikTok Video Discovery Platform

**Version:** 1.0\
**Status:** Draft for Codex implementation\
**Date:** 30 October 2026\
**Stack:** React, FastAPI, MySQL, Bright Data

------------------------------------------------------------------------

## 1. Executive Summary

The TikTok Video Discovery Platform enables a client to discover,
filter, review, save, and export TikTok video metadata that matches
configurable criteria.

Bright Data is the external discovery/data provider. FastAPI securely
orchestrates provider requests, tracks asynchronous collection
snapshots, normalizes and filters records, and stores data in MySQL.
React provides the dashboard.

Example search criteria: - Topic/category: football, programming,
Tetris, or another topic. - Minimum video age: e.g. at least 2 days
old. - View-count range: e.g. 500--500,000. - Target language:
e.g. Russian. - Desired result count: e.g. 500 matching videos.

**Accuracy is more important than forcing a target count.** The system
must never silently relax filters to return a requested number. If only
327 valid records are found, report 327 and explain why the target was
not reached.

This PRD does not imply that TikTok or Bright Data guarantees exhaustive
coverage, a particular result count, or authorization for every
commercial use. The client must confirm the provider contract and
applicable platform terms before production use.

## 2. Product Vision

Provide a straightforward workspace where users can: 1. Configure a
video search. 2. Start collection without exposing provider credentials.
3. Monitor collection progress. 4. Review matching video records. 5.
Inspect available metadata and classification evidence. 6. Save search
history. 7. Export results as CSV or JSON.

The experience should resemble an e-commerce discovery dashboard:
searchable cards/table, filters, sorting, pagination, and a detailed
record view.

## 3. Goals, Non-goals, and Success Criteria

### Goals

-   Secure Bright Data integration through the backend.
-   Support asynchronous collection and snapshot retrieval.
-   Normalize inconsistent or optional provider fields.
-   Filter by date, views, category, and language evidence.
-   Deduplicate videos across collection runs.
-   Persist jobs and metadata in MySQL.
-   Show progress and results in React.
-   Export results and preserve source metadata for auditing.

### Success criteria

-   User can submit a search and receive a persistent job ID.
-   Backend triggers the configured dataset and tracks its snapshot.
-   Completed snapshots are retrieved and parsed safely.
-   Repeated imports do not create duplicate canonical videos.
-   Date, view, and category filters behave as configured.
-   Language decisions include evidence type and confidence where
    available.
-   Dashboard distinguishes matched, rejected, and unverified records.
-   User can inspect a video and open its original TikTok URL.
-   CSV and JSON exports contain the job's matching records.
-   Bright Data credentials never reach the browser.

### Non-goals for initial release

-   Downloading or hosting TikTok video files.
-   Publishing or editing TikTok videos.
-   Guaranteeing exhaustive TikTok-wide search or exactly 500 results.
-   Bypassing access controls, rate limits, or provider restrictions.
-   Inferring creator location from a provider region field.
-   Treating captions or hashtags as proof of spoken language.
-   Building a recommendation engine or public multi-tenant SaaS unless
    separately approved.

## 4. Users and Roles

**Research/client user:** Creates searches, monitors jobs, reviews
videos, exports results.

**Administrator:** Configures provider settings, inspects failures,
manages limits, and monitors system health.

The first deployment may be single-client/internal, but authentication
must be considered before public exposure. Provider credentials are
backend secrets and must never be returned by an API.

## 5. Core User Journeys

### Create a search

1.  User enters topic/category, view range, minimum age, target
    language, and target count.
2.  Frontend submits criteria to FastAPI.
3.  Backend validates and persists a search job.
4.  Backend starts collection and returns a job ID.
5.  User is taken to the job progress page.

### Monitor collection

1.  User opens an active job.
2.  Dashboard shows lifecycle status and known counts.
3.  Backend checks provider snapshot status.
4.  When ready, backend retrieves and processes the snapshot.
5.  Job becomes completed, partially completed, or failed.

Closing the browser must not stop a collection. Do not show a fabricated
percentage when the provider does not supply enough progress
information.

### Review results

1.  User opens a completed/partially completed job.
2.  User searches, filters, sorts, and paginates matching records.
3.  User opens a detailed video view.
4.  User can open the original TikTok post in a new tab.

### Export

User selects a job and downloads its matching records as CSV or JSON.
Export must include relevant filter and verification fields.

## 6. Functional Requirements

Priority: **P0** = first release; **P1** = next iteration; **P2** =
optional.

### 6.1 Search configuration

  -----------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -----------------------
  SRCH-001                P0                      Enter a keyword/topic.

  SRCH-002                P0                      Select or enter a
                                                  category.

  SRCH-003                P0                      Set minimum and maximum
                                                  views.

  SRCH-004                P0                      Set minimum age in days
                                                  or an explicit date
                                                  range.

  SRCH-005                P0                      Select target language;
                                                  Russian is an example,
                                                  not a hardcoded-only
                                                  option.

  SRCH-006                P0                      Set target matching
                                                  count.

  SRCH-007                P0                      Validate min views \<=
                                                  max views and all
                                                  numeric inputs are
                                                  within configured
                                                  limits.

  SRCH-008                P0                      Save the exact criteria
                                                  and cutoff timestamp
                                                  with the job.

  SRCH-009                P1                      Support multiple
                                                  keywords/hashtags and
                                                  category aliases.

  SRCH-010                P1                      Allow a configurable
                                                  maximum collection
                                                  budget/batch count.
  -----------------------------------------------------------------------

Minimum age of two days means the video must have been published at
least two full days before the saved search cutoff time. Store that
cutoff for reproducibility.

### 6.2 Bright Data integration

  ------------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- ------------------------
  BD-001                  P0                      Call Bright Data only
                                                  from FastAPI using a
                                                  server-side token.

  BD-002                  P0                      Configure dataset ID
                                                  through
                                                  environment/secrets.

  BD-003                  P0                      Match request body and
                                                  parameters to the
                                                  selected dataset's
                                                  actual schema.

  BD-004                  P0                      Trigger asynchronous
                                                  collection.

  BD-005                  P0                      Save returned snapshot
                                                  ID.

  BD-006                  P0                      Check snapshot progress.

  BD-007                  P0                      Retrieve completed
                                                  snapshot results.

  BD-008                  P0                      Handle timeouts, HTTP
                                                  errors, and provider
                                                  errors.

  BD-009                  P0                      Log safe
                                                  request/response
                                                  metadata without
                                                  secrets.

  BD-010                  P0                      Never expose provider
                                                  credentials in frontend
                                                  code or API responses.

  BD-011                  P1                      Bounded retries with
                                                  exponential backoff for
                                                  transient errors.

  BD-012                  P1                      Respect provider
                                                  rate-limit/retry-after
                                                  guidance.

  BD-013                  P1                      Configurable timeouts
                                                  and concurrency limits.

  BD-014                  P1                      Admin provider health
                                                  check without token
                                                  disclosure.
  ------------------------------------------------------------------------

Bright Data datasets have different schemas and parameters. Use the
exact generated cURL and input schema for the chosen dataset in the
client's account. Do not assume the search dataset schema applies to
profile, video URL, or Shop datasets.

### 6.3 Collection jobs and lifecycle

  -----------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -----------------------
  JOB-001                 P0                      Every search creates a
                                                  persistent job.

  JOB-002                 P0                      Store criteria, status,
                                                  timestamps, and
                                                  snapshot ID.

  JOB-003                 P0                      Status values: queued,
                                                  collecting, retrieving,
                                                  processing, completed,
                                                  partially_completed,
                                                  failed, canceled.

  JOB-004                 P0                      Jobs can resume status
                                                  checks after backend
                                                  restart.

  JOB-005                 P0                      Complete only after
                                                  retrieval and
                                                  processing finish.

  JOB-006                 P0                      Mark
                                                  partially_completed
                                                  when budget is
                                                  exhausted below target.

  JOB-007                 P0                      Store safe error
                                                  summary and internal
                                                  diagnostics.

  JOB-008                 P1                      Support cancellation
                                                  where provider/worker
                                                  supports it.

  JOB-009                 P1                      Retry eligible failed
                                                  jobs while preserving
                                                  attempt history.

  JOB-010                 P1                      Track discovered,
                                                  processed, matched,
                                                  rejected, duplicate,
                                                  and unverified counts.
  -----------------------------------------------------------------------

Do not hold one HTTP request open for a long collection. Use a
persistent job record and backend worker. A browser tab closing must not
terminate work.

### 6.4 Data normalization

The user's sample response included fields such as `url`, `post_id`,
`description`, `create_time`, `digg_count`, `share_count`,
`collect_count`, `comment_count`, `play_count`, `video_duration`,
`hashtags`, `original_sound`, `profile_id`, `profile_username`,
`profile_url`, `profile_avatar`, `preview_image`, `post_type`,
`discovery_input`, `video_url`, `subtitle_url`, `subtitle_info`, and
`region`.

These fields may be missing, null, empty, or different across datasets.
The parser must be defensive.

  -----------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -----------------------
  DATA-001                P0                      Normalize post ID and
                                                  original post URL where
                                                  available.

  DATA-002                P0                      Normalize description,
                                                  creation time, views,
                                                  and engagement counts.

  DATA-003                P0                      Normalize hashtags into
                                                  a consistent array.

  DATA-004                P0                      Normalize available
                                                  creator/profile fields.

  DATA-005                P0                      Preserve original
                                                  provider JSON for
                                                  audit/reprocessing.

  DATA-006                P0                      Missing optional fields
                                                  must not crash
                                                  processing.

  DATA-007                P0                      Parse timestamps
                                                  consistently and store
                                                  UTC.

  DATA-008                P0                      Store dataset and
                                                  collection provenance.

  DATA-009                P0                      Deduplicate by stable
                                                  post ID, falling back
                                                  to normalized URL.

  DATA-010                P1                      Store thumbnail,
                                                  duration, sound
                                                  metadata when supplied.
  -----------------------------------------------------------------------

Do not assume `video_url` is permanent or downloadable. Initial scope
requires metadata, optional thumbnail, and original TikTok link only.

### 6.5 Filtering and matching

Filtering is authoritative on the backend. Frontend filters may narrow
already retrieved results but cannot replace backend validation.

  -----------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -----------------------
  FILT-001                P0                      Apply inclusive
                                                  minimum/maximum view
                                                  range.

  FILT-002                P0                      Exclude missing/invalid
                                                  views from a
                                                  view-constrained
                                                  search.

  FILT-003                P0                      Apply minimum-age
                                                  cutoff against saved
                                                  cutoff timestamp.

  FILT-004                P0                      Exclude missing/invalid
                                                  timestamps from
                                                  date-constrained
                                                  searches.

  FILT-005                P0                      Use transparent
                                                  description/hashtag
                                                  rules as initial
                                                  category matching.

  FILT-006                P0                      Store match/rejection
                                                  reasons.

  FILT-007                P0                      Never silently relax
                                                  filters to reach target
                                                  count.

  FILT-008                P0                      Deduplicate before
                                                  counting toward target.

  FILT-009                P0                      Report actual
                                                  qualifying count and
                                                  shortfall.

  FILT-010                P1                      Add semantic category
                                                  classification with
                                                  method/confidence.

  FILT-011                P1                      Support multiple
                                                  category aliases and
                                                  terms.
  -----------------------------------------------------------------------

A future classifier must store its decision separately from raw source
data and include confidence/evidence where available.

### 6.6 Language detection and verification

Distinguish: - **Text language:** description, caption, hashtags, or
subtitle text. - **Spoken language:** speech detected from
audio/transcript.

A Russian caption does not prove Russian speech. Videos may contain
music, no speech, multiple languages, or no usable subtitles.

  -----------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -----------------------
  LANG-001                P0                      Store requested target
                                                  language.

  LANG-002                P0                      Store detected language
                                                  separately.

  LANG-003                P0                      Store evidence type:
                                                  description, caption,
                                                  subtitle, transcript,
                                                  audio, unknown.

  LANG-004                P0                      Store confidence where
                                                  supplied by the
                                                  detection method.

  LANG-005                P0                      Status values:
                                                  verified_match,
                                                  likely_match, mismatch,
                                                  unverified,
                                                  unavailable.

  LANG-006                P0                      Never claim
                                                  spoken-language
                                                  verification from
                                                  hashtags/description
                                                  alone.

  LANG-007                P0                      Insufficient evidence
                                                  remains unverified.

  LANG-008                P1                      Detect language from
                                                  usable
                                                  subtitle/transcript
                                                  text.

  LANG-009                P1                      Add authorized audio
                                                  transcription only if
                                                  required and permitted.

  LANG-010                P1                      Store transcription
                                                  model/provider and
                                                  processing metadata.

  LANG-011                P1                      Allow manual review of
                                                  uncertain results.
  -----------------------------------------------------------------------

Before audio transcription, confirm that media access is technically
available and permitted by the provider contract, platform terms, and
applicable law. A `video_url` field alone does not establish permission
or reliable access.

The client must decide whether "Russian videos" means Russian
metadata/subtitles or Russian spoken audio. The UI must label evidence
precisely.

### 6.7 Results, search history, and exports

  -------------------------------------------------------------------------
  ID                      Priority                Requirement
  ----------------------- ----------------------- -------------------------
  RES-001                 P0                      View all matching records
                                                  for a job.

  RES-002                 P0                      Server-side pagination.

  RES-003                 P0                      Sort by views, upload
                                                  date, and creator.

  RES-004                 P0                      Search descriptions and
                                                  creator usernames.

  RES-005                 P0                      Open original TikTok URL.

  RES-006                 P0                      Detail view of all
                                                  normalized available
                                                  metadata.

  RES-007                 P0                      Show language
                                                  status/evidence and
                                                  category decision.

  HIST-001                P0                      List prior search jobs
                                                  and their
                                                  criteria/status/counts.

  HIST-002                P0                      Reopen previous search
                                                  results.

  EXP-001                 P0                      Export a job's matching
                                                  records as CSV.

  EXP-002                 P0                      Export a job's matching
                                                  records as JSON.

  EXP-003                 P0                      Include TikTok URL,
                                                  metadata, category, and
                                                  language evidence.

  HIST-003                P1                      Duplicate a previous
                                                  search's criteria.

  HIST-004                P1                      Delete jobs according to
                                                  retention policy.

  RES-008                 P1                      Save/bookmark individual
                                                  records.

  RES-009                 P1                      Compare records across
                                                  searches.

  EXP-004                 P1                      Export manually selected
                                                  records.

  EXP-005                 P1                      Include search criteria
                                                  and export timestamp in
                                                  metadata.
  -------------------------------------------------------------------------

## 7. Dashboard Requirements

### Navigation

-   Overview
-   New Search
-   Active Jobs
-   Search History
-   Video Results
-   Settings (admin)

### Overview

Show actual backend metrics: total jobs, active jobs, unique videos,
matching videos, unverified language records, and recent failures. Never
hardcode production metrics.

### New Search

Fields: - Keyword/topic and category. - Minimum/maximum views. - Minimum
age or date range. - Target language. - Language requirement type, once
confirmed. - Target result count. - Optional collection budget.

Validate on frontend and backend.

### Job progress

Show job ID, criteria, lifecycle status, timestamps, provider snapshot
state, and known counts. Do not fabricate a percentage.

### Video results

Responsive table/card layout with thumbnail, description, creator,
upload date, views, engagement, category, language, evidence type,
confidence, verification status, and original link. Support pagination,
sorting, and filtering.

### Video detail

Show post ID/URL, full description, hashtags, upload time, metrics,
duration, sound, creator fields, thumbnail, provider region (clearly
labeled; not proof of creator location), category evidence, language
evidence, collection provenance, and optionally expandable raw JSON for
administrators.

### UX states

Implement loading, empty, error, partial-result, and completed states.
Do not display broken thumbnails when no valid image exists. Clearly
distinguish verified, unverified, mismatch, failed, and in-progress
states.

## 8. Technical Architecture

### Stack

  -----------------------------------------------------------------------
  Layer                   Technology              Responsibility
  ----------------------- ----------------------- -----------------------
  Frontend                React                   Dashboard

  Routing                 React Router or         Navigation
                          equivalent              

  Data fetching           TanStack Query or       API state and polling
                          equivalent              

  Backend                 FastAPI                 REST API and
                                                  orchestration

  HTTP client             HTTPX                   Bright Data requests

  Validation              Pydantic                API contracts

  ORM                     SQLAlchemy 2.x          Database access

  Migrations              Alembic                 Schema changes

  Database                MySQL 8.x               Persistent data

  Worker                  Initial persistent      Long-running jobs
                          worker; Celery/RQ later 
                          if needed               

  Queue/cache             Redis optional later    Queue/transient state

  Deployment              Docker Compose          Local/production
                                                  services
  -----------------------------------------------------------------------

Do not add Redis/Celery prematurely. First implement persistent jobs
that survive browser closure and application restart. Introduce a
dedicated queue when workload warrants it.

### Suggested backend structure

``` text
backend/
├── app/
│   ├── main.py
│   ├── api/routes/
│   │   ├── health.py
│   │   ├── search_jobs.py
│   │   ├── videos.py
│   │   └── exports.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── db/
│   │   ├── session.py
│   │   └── base.py
│   ├── models/
│   │   ├── search_job.py
│   │   ├── collection_attempt.py
│   │   └── video.py
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   │   ├── brightdata_service.py
│   │   ├── collection_service.py
│   │   ├── normalization_service.py
│   │   ├── filtering_service.py
│   │   ├── language_service.py
│   │   └── export_service.py
│   └── workers/
│       └── collection_worker.py
├── alembic/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

### API contract

Base prefix: `/api/v1`

  Method   Endpoint                                Purpose
  -------- --------------------------------------- -------------------------------------
  GET      `/health`                               Application health
  GET      `/health/ready`                         Readiness check
  POST     `/search-jobs`                          Create and queue search
  GET      `/search-jobs`                          List jobs, pagination/status filter
  GET      `/search-jobs/{job_id}`                 Job detail and criteria
  GET      `/search-jobs/{job_id}/progress`        Status and counts
  POST     `/search-jobs/{job_id}/retry`           Retry eligible failed job
  POST     `/search-jobs/{job_id}/cancel`          Request cancellation
  GET      `/search-jobs/{job_id}/videos`          Paginated matching records
  GET      `/videos/{video_id}`                    Video detail
  GET      `/videos/{video_id}/raw`                Admin-only raw payload
  GET      `/search-jobs/{job_id}/videos/export`   CSV/JSON export
  GET      `/admin/provider/status`                Provider configuration status
  POST     `/admin/provider/test`                  Admin provider connection test

Do not create an arbitrary proxy endpoint that accepts arbitrary URLs or
provider paths from the frontend.

Example create-search request:

``` json
{
  "keyword": "football",
  "category": "football",
  "min_views": 500,
  "max_views": 500000,
  "min_age_days": 2,
  "target_language": "ru",
  "language_requirement": "spoken",
  "target_count": 500
}
```

`language_requirement` is illustrative and must be finalized with the
client. If spoken audio processing is not implemented or permitted,
reject that mode or mark records unverified. Never silently substitute
caption detection.

Example job response:

``` json
{
  "id": "job_example",
  "status": "collecting",
  "criteria": {
    "keyword": "football",
    "category": "football",
    "min_views": 500,
    "max_views": 500000,
    "min_age_days": 2,
    "target_language": "ru",
    "target_count": 500
  },
  "counts": {
    "discovered": 0,
    "processed": 0,
    "matched": 0,
    "rejected": 0,
    "duplicates": 0,
    "unverified": 0
  },
  "created_at": "2026-10-30T12:00:00Z"
}
```

These are application examples, not real Bright Data responses.

## 9. Database Requirements

Use MySQL with SQLAlchemy 2.x and Alembic. Store timestamps in UTC.

### `search_jobs`

-   `id` (UUID primary key)
-   `keyword`, `category`
-   `min_views`, `max_views`
-   `min_age_days`, `cutoff_at`
-   `target_language`, `language_requirement`
-   `target_count`
-   `status`, `snapshot_id`
-   `discovered_count`, `processed_count`, `matched_count`
-   `rejected_count`, `duplicate_count`, `unverified_count`
-   `error_summary`
-   `created_at`, `updated_at`, `completed_at`

### `videos`

-   `id` (primary key)
-   `provider_post_id` (nullable)
-   `canonical_url`
-   `description`
-   `created_at_source`
-   `view_count`, `like_count`, `comment_count`, `share_count`,
    `collect_count`
-   `duration_seconds`
-   `hashtags_json`
-   `creator_id`, `creator_username`, `creator_url`,
    `creator_avatar_url`
-   `thumbnail_url`, `video_source_url`
-   `region`, `original_sound_json`
-   `raw_payload` (JSON)
-   `first_seen_at`, `last_seen_at`

Use a unique provider post ID where available; otherwise use a
deterministic normalized URL key. Do not merge records without a
reliable identity key.

### `search_job_videos`

Links videos to jobs and stores per-search decisions: - `id` -
`search_job_id` (FK) - `video_id` (FK) - `decision`
(matched/rejected/unverified) - `rejection_reasons_json` -
`category_label`, `category_method`, `category_confidence` -
`detected_language`, `language_evidence_type` - `language_confidence`,
`language_status` - `processed_at`

Unique constraint: `(search_job_id, video_id)`.

### `collection_attempts`

Stores attempt history: - `id`, `search_job_id`, `dataset_id`,
`snapshot_id` - `attempt_number`, `status` - `request_metadata_json` (no
secrets) - `response_metadata_json` - `error_code`, `error_summary` -
`started_at`, `finished_at`

Recommended indexes: - `search_jobs(status, created_at)` -
`videos(created_at_source)` - `videos(view_count)` -
`videos(creator_username)` -
`search_job_videos(search_job_id, decision)` - Unique
`(search_job_id, video_id)` - Unique provider post ID where applicable.

Avoid placing all searchable fields only inside JSON. Add indexes based
on real query patterns.

## 10. Collection and Processing Workflow

1.  Validate criteria.
2.  Create persistent job with `queued` status.
3.  Start backend worker.
4.  Build provider request using the selected dataset's exact schema.
5.  Trigger Bright Data.
6.  Save snapshot ID and attempt record.
7.  Set `collecting`.
8.  Poll with bounded intervals and retry policy.
9.  When ready, set `retrieving`.
10. Download snapshot.
11. Preserve original provider records.
12. Set `processing`.
13. Normalize records.
14. Deduplicate canonical videos.
15. Apply date, view, and category filters.
16. Apply configured language evidence workflow.
17. Persist per-job decisions and counts.
18. Mark completed if target reached or collection process is complete.
19. Mark partially_completed if collection budget is exhausted below
    target.
20. Mark failed on non-recoverable errors.

### Collection budget

Support configurable maximum batches, maximum provider records, maximum
elapsed time, and (where measurable) estimated spend. Record the limits
used per job.

### No silent relaxation

If target is 500 but only 327 qualify, report target 500, matched 327,
shortfall 173, and the reason. Never expand view range, lower minimum
age, broaden category, or substitute language evidence without explicit
user approval.

## 11. Non-functional Requirements

### Security

-   Store Bright Data token only in backend secrets/environment.
-   Exclude `.env` from Git.
-   Redact authorization headers and secrets from logs.
-   Validate inputs and constrain limits.
-   Add authentication before public deployment.
-   Use HTTPS and restrict CORS to approved origins.
-   Protect admin endpoints.
-   Avoid arbitrary URL fetching/SSRF.
-   Sanitize errors returned to the browser.

### Reliability

-   Persist job state before provider work.
-   Make processing idempotent.
-   Resume jobs after restart.
-   Use bounded retries/backoff for transient errors.
-   Do not retry authorization/validation errors indefinitely.
-   Preserve raw payloads.
-   Isolate malformed records when safe.

### Performance and scale

Initial engineering targets to validate: - Dashboard API reads under 500
ms p95 for moderate indexed datasets. - Server-side pagination; do not
send thousands of records at once. - Never hold a request open for a
long collection. - Process large snapshots in batches. - Avoid repeated
snapshot downloads where possible. - Limit concurrent jobs according to
provider rate limits and budget.

### Observability

Log job/attempt IDs and lifecycle events: created, triggered, snapshot
received, status changed, downloaded, discovered, normalized, duplicate,
matched, rejected, unverified, completed, failed. Never log secrets.

## 12. Error Handling

  -----------------------------------------------------------------------
  Condition                           Expected behavior
  ----------------------------------- -----------------------------------
  Invalid criteria                    HTTP 422 with field errors

  Missing provider config             Fail safely; admin sees
                                      configuration error

  Provider unauthorized               Fail attempt; no endless retry

  Rate limited                        Respect retry guidance with bounded
                                      backoff

  Timeout                             Retry within configured limit

  Snapshot still running              Return current status, not failure

  Snapshot failed                     Mark job failed and retain safe
                                      diagnostics

  Snapshot has zero records           Complete with zero matches unless
                                      provider reports failure

  Malformed record                    Record processing error and
                                      continue where safe

  Database unavailable                Do not mark complete; recover/retry

  Duplicate record                    Link existing video to job; do not
                                      duplicate canonical row
  -----------------------------------------------------------------------

## 13. Testing Requirements

### Unit tests

-   Criteria validation.
-   Timestamp/timezone parsing.
-   View/date filtering.
-   Category matching.
-   Language status classification.
-   URL normalization and deduplication.
-   Parsing missing/null/malformed fields.
-   CSV/JSON serialization.

### Integration tests

-   Mock Bright Data HTTP calls.
-   Trigger/progress/snapshot endpoints.
-   MySQL repositories.
-   Job lifecycle transitions.
-   Reprocessing without duplicate inserts.
-   Export endpoint.

### End-to-end tests

-   Create search.
-   Verify job persistence.
-   Simulate collection completion.
-   Verify normalized/filtered records.
-   Verify dashboard result states.
-   Export and compare to database.

Maintain sanitized fixtures covering valid match, too few/many views,
too recent, missing date/views, duplicate post, missing hashtags, empty
subtitle data, Russian caption with unknown speech, no language
evidence, and malformed optional fields. Do not trigger paid live
collections in every automated test.

## 14. Deployment Requirements

### Local

Provide Docker Compose or clear local setup for FastAPI and MySQL, plus
optional frontend/worker. Include `.env.example`, migration commands,
test instructions, seed data instructions, and API docs.

### Production

-   Production ASGI server and reverse proxy.
-   Protected secrets.
-   MySQL backups and restore test.
-   HTTPS and restricted database access.
-   Health checks, monitoring, log rotation.
-   Provider usage and job limits.
-   Data retention policy.
-   Provider/platform compliance review.

## 15. Compliance and Data Governance

This is a production release gate: 1. Confirm Bright Data plan/dataset
license permits intended commercial use. 2. Review applicable TikTok
terms and restrictions on automated collection/use. 3. Confirm what data
may be retained, displayed, exported, and shared. 4. Avoid unnecessary
personal data. 5. Define retention and deletion rules. 6. Do not bypass
access controls, technical protections, or rate limits. 7. Do not assume
third-party scraper availability means TikTok authorizes the activity.
8. Confirm permission for media access/audio processing before
spoken-language verification.

TikTok Research API is not a general commercial alternative; access is
restricted to eligible research use cases. Do not design around assumed
commercial eligibility.

## 16. Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                    Impact                  Mitigation
  ----------------------- ----------------------- -----------------------
  Dataset schema changes  Parser breaks           Isolate provider
                                                  parser, fixtures,
                                                  validation, raw payload
                                                  retention

  Too few matching videos Target not met          Transparent partial
                                                  completion; no filter
                                                  relaxation

  Missing language        False classification    Evidence types,
  evidence                                        unverified state,
                                                  optional authorized ASR

  Limited search coverage Low recall              Explain coverage
                                                  limits; approved extra
                                                  discovery batches

  Duplicate records       Inflated counts         Stable keys and DB
                                                  constraints

  Provider                Delayed jobs            Persistent jobs,
  latency/failure                                 bounded retries, clear
                                                  status

  Cost overrun            Unexpected spend        Per-job/monthly limits
                                                  and usage tracking

  Token leak              Unauthorized provider   Backend-only secrets
                          use                     and redaction

  Contract/terms issue    Product cannot be used  Review before
                          as intended             production

  Expiring media URL      Broken                  Treat media URL as
                          preview/transcription   optional; retain post
                                                  URL and metadata
  -----------------------------------------------------------------------

## 17. Release Milestones

### M1 --- Backend foundation

FastAPI structure, config, health checks, Bright Data
trigger/progress/snapshot service, endpoints, mocked tests.\
**Acceptance:** Small test collection can be triggered and retrieved
using the real dataset schema.

### M2 --- MySQL and normalization

SQLAlchemy, Alembic, models, repositories, parser, deduplication, raw
payload persistence.\
**Acceptance:** Re-importing a fixture does not create duplicate
canonical video records.

### M3 --- Filtering and job orchestration

Persistent lifecycle, criteria validation, date/view/category filtering,
match reasons, partial completion, restart recovery.\
**Acceptance:** Fixture-driven end-to-end job produces correct counts
and decisions.

### M4 --- React dashboard

Overview, new search, active job progress, history, result list, detail
view, pagination/sorting.\
**Acceptance:** User can create a search and inspect saved results
without Swagger.

### M5 --- Language verification and export

Client-confirmed language definition, text/subtitle and/or authorized
audio pipeline, confidence/evidence, CSV/JSON.\
**Acceptance:** UI distinguishes text-language detection from
spoken-language verification.

### M6 --- Production hardening

Authentication, deployment, backups, monitoring, usage/cost limits,
compliance review.\
**Acceptance:** Production checklist is completed and approved.

## 18. Definition of Done

A feature is complete when: - Requirements and acceptance criteria are
implemented. - Backend validation exists. - Loading, empty, and error
states are handled. - Automated tests cover success and failure. -
Secrets are protected. - Migrations are included when needed. - API
contracts are documented. - Logs contain useful diagnostics without
secrets. - UI reflects actual backend state. - Documentation is updated.

A search is complete only after collection, snapshot retrieval,
normalization, filtering, persistence, and result retrieval succeed---or
the job is explicitly marked partially completed/failed with a reason.

## 19. Open Questions for Client

These decisions must be confirmed: 1. Does "Russian videos" mean Russian
captions/descriptions, subtitles, or spoken audio? 2. Is category based
on hashtags/keywords, semantic video content, or both? 3. Which Bright
Data dataset is licensed and selected? Confirm exact ID, input schema,
trigger parameters, and output schema. 4. Is geography required? Does it
refer to video region, creator location, or language? 5. Is target count
a maximum/up-to value or a desired target? System reports actual matches
either way. 6. Is minimum age measured from exact search submission time
or a timezone date boundary? 7. How long should raw and processed data
be retained? 8. Is this a single-client dashboard or multi-account
product? 9. Are CSV and JSON sufficient, or is Excel required? 10. What
is the maximum provider spend per search and per month? 11. Are
metadata, thumbnails, and post links sufficient, or is media downloading
required? 12. Should users manually approve uncertain classifications?

## 20. Codex Implementation Instructions

Treat this PRD as the product source of truth. Implement incrementally;
do not generate the entire system in one pass.

1.  Inspect the existing repository before changing files.
2.  If empty, create the structure described above.
3.  Implement M1 only first.
4.  Inspect the actual Bright Data dataset schema and sanitized
    generated cURL before implementing provider calls.
5.  Never invent dataset IDs, fields, or request parameters.
6.  Use type hints, Pydantic, SQLAlchemy 2.x patterns, and Alembic.
7.  Keep routers thin and business logic in services.
8.  Isolate provider-specific parsing from the canonical internal video
    model.
9.  Never expose provider tokens to React.
10. Do not add Redis/Celery/auth providers unless justified by a
    requirement.
11. Do not implement spoken-language verification until client
    requirement and media permissions are confirmed.
12. Never fabricate progress, counts, or confidence.
13. Never silently relax filters to meet target count.
14. After each milestone, run tests, report changed files, explain how
    to run the app, and list blockers.

### First Codex task --- M1 only

Implement: - FastAPI app and health endpoints. - Environment-based
configuration. - Bright Data trigger, progress, and snapshot methods. -
Router endpoints and Pydantic schemas. - Safe errors and secret
redaction. - Mocked HTTP unit tests. - `.env.example`, `.gitignore`,
`requirements.txt`, and README.

Do **not** implement MySQL persistence or React in this first task.
Prove Bright Data integration against the actual dataset schema first.

------------------------------------------------------------------------

**End of PRD**
