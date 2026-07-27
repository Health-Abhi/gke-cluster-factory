from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.auth import actor_from_request, enforce_api_token
from app.config import get_settings
from app.github import GitHubError
from app.ipam import IPAMError
from app.models import ClusterRequestCreate, RequestSubmission, RequestSummary, ValidationResult
from app.repository import RequestRepositoryError
from app.service import ClusterFactoryService, RequestValidationError

logger = logging.getLogger("gke-cluster-factory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app.state.service = ClusterFactoryService(settings)
    yield
    await app.state.service.close()


app = FastAPI(
    title="GKE Cluster Factory",
    version="0.1.0",
    description="Self-service, policy-driven GKE cluster request API",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Email"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def service_from_request(request: Request) -> ClusterFactoryService:
    return request.app.state.service


Service = Annotated[ClusterFactoryService, Depends(service_from_request)]
Protected = Annotated[None, Depends(enforce_api_token)]


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/healthz", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
async def readiness(service: Service) -> dict[str, str]:
    service.catalog()
    return {"status": "ready"}


@app.get("/api/v1/catalog", tags=["catalog"])
async def catalog(service: Service, _: Protected) -> dict:
    return service.catalog()


@app.post("/api/v1/requests/validate", response_model=ValidationResult, tags=["requests"])
async def validate_request(
    payload: ClusterRequestCreate,
    service: Service,
    _: Protected,
) -> ValidationResult:
    try:
        return service.validate(payload)
    except RequestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": exc.errors, "warnings": exc.warnings},
        ) from exc


@app.post("/api/v1/requests", response_model=RequestSubmission, status_code=201, tags=["requests"])
async def submit_request(
    payload: ClusterRequestCreate,
    request: Request,
    service: Service,
    _: Protected,
) -> RequestSubmission:
    try:
        return await service.submit(payload, actor_from_request(request))
    except RequestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": exc.errors, "warnings": exc.warnings},
        ) from exc
    except (GitHubError, IPAMError, RequestRepositoryError) as exc:
        logger.exception("Request submission failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/requests", response_model=list[RequestSummary], tags=["requests"])
async def list_requests(service: Service, _: Protected) -> list[RequestSummary]:
    try:
        return await service.summaries()
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
