"""FastAPI application creation and lifecycle."""

import logging
from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from app.api.routes.job import router as job_router
from app.api.routes.jobs import router as jobs_router
from app.clients.authenticated_client import (
    AuthenticatedLinkedInClient,
    create_authenticated_http_client,
)
from app.core.config import get_settings
from app.core.dependencies import create_job_cache
from app.core.observability import REQUEST_ID_CONTEXT, choose_request_id, configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Creates and closes the reusable HTTP session for the LinkedIn integration."""

    settings = get_settings()
    application.state.job_cache = create_job_cache(settings)
    authenticated_http_client = create_authenticated_http_client(settings)
    application.state.authenticated_linkedin_client = AuthenticatedLinkedInClient(
        authenticated_http_client,
        settings,
    )
    try:
        yield
    finally:
        await authenticated_http_client.aclose()


def create_app() -> FastAPI:
    """Builds the application, its routes, and the automatic API documentation."""

    configure_logging()
    application = FastAPI(
        title="LinkedIn Scrapper API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def observe_requests(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Correlates and logs each request without including query parameters or headers."""

        request_id = choose_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        context_token = REQUEST_ID_CONTEXT.set(request_id)
        started_at = perf_counter()
        response: Response
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            logger.exception(
                "Exceção não tratada durante a requisição.",
                extra={
                    "event": "http.request.exception",
                    "request_id": request_id,
                    "method": request.method,
                    "route": getattr(request.scope.get("route"), "path", "unmatched"),
                },
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Erro interno do servidor.", "request_id": request_id},
            )

        route = request.scope.get("route")
        route_path = getattr(route, "path", None) or "unmatched"
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        log_level = (
            logging.ERROR
            if status_code >= 500
            else (logging.WARNING if status_code >= 400 else logging.INFO)
        )
        logger.log(
            log_level,
            "Requisição HTTP concluída.",
            extra={
                "event": "http.request.completed",
                "request_id": request_id,
                "method": request.method,
                "route": route_path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        REQUEST_ID_CONTEXT.reset(context_token)
        return response

    application.include_router(jobs_router, prefix="/api")
    application.include_router(job_router, prefix="/api")
    return application


app = create_app()
