"""FastAPI app entrypoint. Wires routes, CORS, lifecycle, metrics."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    # Defer detector + worker spinup to first scan to keep cold-start light.
    yield
    # Shutdown — nothing to clean up yet


app = FastAPI(
    title="Bosch Forgetter — Scan Service",
    description="Local-first GDPR data discovery, tiered routing, sovereign AI.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "scan", "version": app.version}


# Route imports deferred to avoid circular + heavy detector loads on import.
def _mount_routes() -> None:
    from .routes import agents, chat, dsar, findings, mosaic, scan  # noqa: WPS433

    app.include_router(scan.router, tags=["scan"])
    app.include_router(agents.router, tags=["agents"])
    app.include_router(findings.router, tags=["findings"])
    app.include_router(dsar.router, tags=["dsar"])
    app.include_router(mosaic.router, tags=["mosaic"])
    app.include_router(chat.router, tags=["chat"])

    # Prometheus instrumentation
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except ImportError:
        pass  # /metrics optional


_mount_routes()
