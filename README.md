# ClipScope backend

FastAPI backend for Bright Data collection and TikTok keyword discovery.

## Setup (PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Non-secret local settings are hard-coded in `app/config.py`: Bright Data API URL and keyword dataset, a 120-second HTTP timeout, and MySQL 8 at `127.0.0.1:3306` using database `tiktokdb` and local user `root`. The backend does not read `.env` files. Only `MYSQL_PASSWORD` and `BRIGHTDATA_API_TOKEN` are read from the backend process environment; neither secret is stored in source code. Root access is for this temporary local setup only; use a least-privilege database account before deployment.

Create the database if it does not already exist, using a MySQL administrator account:

```sql
CREATE DATABASE tiktokdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Run

In PowerShell, enter both secrets securely and run migrations and Uvicorn from the same terminal. Use the password for the local MySQL `root` account. Do not put either value in source code or commit it:

```powershell
$secureDatabasePassword = Read-Host "MySQL clipscope_app password" -AsSecureString
$env:MYSQL_PASSWORD = [System.Net.NetworkCredential]::new("", $secureDatabasePassword).Password
$secureToken = Read-Host "Bright Data API token" -AsSecureString
$env:BRIGHTDATA_API_TOKEN = [System.Net.NetworkCredential]::new("", $secureToken).Password
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The application reads configuration when it starts. Restart Uvicorn after setting or changing either secret. Check `GET /api/health/ready` and `GET /api/brightdata/config`; they report readiness and whether a token is configured without returning secret values.

Stop the server with Ctrl+C, then clear process environment variables when finished:

```powershell
Remove-Item Env:BRIGHTDATA_API_TOKEN
Remove-Item Env:MYSQL_PASSWORD
Remove-Variable secureToken
Remove-Variable secureDatabasePassword
```

Only non-secret settings are hard-coded. No values from `.env` are loaded.

Run the frontend in a second terminal:

```powershell
cd ..\fronted
npm run dev
```

Health: `GET /api/health`; API docs: `http://localhost:8000/docs`.

## Bright Data API

`POST /api/brightdata/jobs` accepts `{ "payload": <dataset-specific JSON> }`. The dataset can be selected with the optional `dataset_id` query parameter; otherwise the hard-coded default dataset is used. The body must match that dataset's current input schema. The API returns the provider response and snapshot ID when one is present.

Poll `GET /api/brightdata/jobs/{snapshot_id}/progress`, then retrieve `GET /api/brightdata/jobs/{snapshot_id}/results?output_format=json` when ready. Result formats accepted by this API are `json`, `ndjson`, `jsonl`, and `csv`.

`GET /api/brightdata/config` reports whether credentials and a default dataset are configured, and the configured dataset ID. It never returns the token.

### Test a keyword collection in Postman

To call Bright Data directly, create a `POST` request to:

```text
https://api.brightdata.com/datasets/v3/scrape?dataset_id={{BRIGHTDATA_KEYWORD_DATASET_ID}}&notify=false&include_errors=true&type=discover_new&discover_by=keyword
```

In Postman, set **Authorization** to **Bearer Token** and use the local variable `{{BRIGHTDATA_API_TOKEN}}`. Set `Content-Type` to `application/json`, then select **Body → raw → JSON** and send:

```json
{
  "input": [
    {
      "search_keyword": "football",
      "country": ""
    }
  ],
  "limit_per_input": 10
}
```

The provider may return records directly, or return a `snapshot_id`. If it returns a snapshot ID, check it with:

```text
GET https://api.brightdata.com/datasets/v3/progress/{{SNAPSHOT_ID}}
```

Use the same Bearer Token authorization. When the response says `"status": "ready"`, download the records with:

```text
GET https://api.brightdata.com/datasets/v3/snapshot/{{SNAPSHOT_ID}}?format=json
```

An HTTP 200 response is not by itself proof that data was collected: with `include_errors=true`, Bright Data can return a per-input `error`/`error_code` object in a successful HTTP response. Fix that provider-reported input error before expecting video records. Do not share the token in chat, screenshots, or source control.

For the ClipScope dashboard instead, submit `POST http://127.0.0.1:8000/api/v1/search-jobs` with `{"keyword":"football","target_count":10}`. This is a different API: it queues a database-backed job and the worker searches using the app's filters. Poll `GET /api/v1/search-jobs/{job_id}/progress`; when it completes, read `GET /api/v1/search-jobs/{job_id}/videos`. The worker currently requests an unrestricted provider candidate set (`limit_per_input: null`) so application-side filtering can determine how many videos actually match; the target count is not a guarantee.

The Bright Data token is unset by default. Provider requests fail safely until `BRIGHTDATA_API_TOKEN` is set in the backend process environment. Never hard-code or commit a real token.

The `backend/app/docs/Apis.md` file contains generated synchronous `/scrape` cURLs for multiple datasets. M1 does not infer a universal request schema from them. Confirm the selected dataset's input schema in the Bright Data account before making a billable request. Do not use the synchronous cURLs as proof that a dataset accepts a particular asynchronous trigger body.

## Tests

```powershell
python -m pytest
```

Tests use mocked HTTP responses and make no provider calls.

# TikTok keyword discovery backend

## Local setup

The development configuration uses MySQL 8. The local host, port, user, database name, and dataset ID are hard-coded; set the MySQL password and Bright Data API token as process environment variables as shown above. The `.env` file is not read.

Create the schema before starting the API:

```powershell
python -m alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The worker starts only when MySQL is reachable and the `search_jobs` migration is present. If readiness returns 503, check the backend log for a missing password, rejected MySQL login, or unapplied migration.

## Keyword discovery API

- `POST /api/v1/search-jobs` validates the criteria and creates a queued job (`202`). The worker calls the documented keyword discovery `/datasets/v3/scrape` operation using `type=discover_new` and `discover_by=keyword`.
- `GET /api/v1/search-jobs/{job_id}/progress` returns status and discovered, processed, matching, rejected, duplicate, and unverified counts.
- `GET /api/v1/search-jobs/{job_id}/videos` returns paginated results. Use `include_unverified=true` to include spoken-language requests that have no audio evidence.
- `GET /api/v1/videos/{video_id}` returns the saved decision and normalized provider fields.
- `GET /api/v1/search-jobs/{job_id}/videos/export?output_format=csv|json` exports matching results.

The current provider response is asynchronous: `/scrape` returned HTTP 202 and a `snapshot_id` during the live integration check. The worker polls `/datasets/v3/progress/{snapshot_id}` and fetches `/datasets/v3/snapshot/{snapshot_id}` once ready. Text language classification uses the returned description only; spoken language stays unverified until audio transcription exists. No filter is relaxed when fewer than the requested number match.

`/api/health` is a liveness check. `/api/health/ready` additionally checks database access and migrations.
