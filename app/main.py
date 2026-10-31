"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import check_database_connection
from app.routers.brightdata import router as brightdata_router
from app.routers.search_jobs import router as search_jobs_router
from app.services.search_workflow import SearchWorkflowWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker: SearchWorkflowWorker | None = None
    if check_database_connection():
        worker = SearchWorkflowWorker()
        worker.start()
    else:
        logger.error(
            "Search worker not started because the configured MySQL database is not ready; "
            "check the preceding database log and run 'python -m alembic upgrade head'"
        )
    yield
    if worker is not None:
        worker.stop()


app = FastAPI(title="ClipScope API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(brightdata_router, prefix="/api/brightdata", tags=["Bright Data"])
app.include_router(search_jobs_router)


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(_: Request, __: SQLAlchemyError) -> JSONResponse:
    logger.error("Database operation failed; returning service unavailable")
    return JSONResponse(status_code=503, content={"detail": "Search database is unavailable"})


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    return {"name": "ClipScope API", "docs": "/docs"}


@app.get("/api/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["Health"], response_model=None)
async def readiness() -> JSONResponse | dict[str, str]:
    if not check_database_connection():
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unavailable"})
    return {"status": "ready"}
