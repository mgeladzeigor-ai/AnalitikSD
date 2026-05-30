# src/analitiksd/api/app.py
from __future__ import annotations

from fastapi import Depends, FastAPI

from analitiksd.api.auth_routes import router as auth_router
from analitiksd.api.deps import require_report, require_source


def create_app() -> FastAPI:
    app = FastAPI(title="AnalitikSD")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/demo/source/bitrix")
    def demo_source(_=Depends(require_source("bitrix"))) -> dict[str, str]:
        return {"ok": "source"}

    @app.get("/demo/report/5")
    def demo_report(_=Depends(require_report(5, "view"))) -> dict[str, str]:
        return {"ok": "report"}

    app.include_router(auth_router)
    return app
