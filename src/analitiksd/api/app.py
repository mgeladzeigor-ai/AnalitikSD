# src/analitiksd/api/app.py
from __future__ import annotations

from fastapi import FastAPI

from analitiksd.api.auth_routes import router as auth_router
from analitiksd.api.report_routes import router as report_router


def create_app() -> FastAPI:
    app = FastAPI(title="AnalitikSD")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(report_router)
    return app
