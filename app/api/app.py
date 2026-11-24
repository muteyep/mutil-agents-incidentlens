from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.persistence.db import init_db


def create_app() -> FastAPI:
    init_db()
    app = FastAPI(
        title="IncidentLens API",
        description="Multi-agent root cause analysis service",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
