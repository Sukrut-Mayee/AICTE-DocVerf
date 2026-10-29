"""AICTE-DocVerf officer API (TRD §11).

Run locally from the repository root:

    .venv/Scripts/python -m uvicorn services.api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .pipeline import PipelineRepository
from .routers import applications, files, findings, network
from .settings import ApiSettings
from .store import OfficerStore


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    resolved = settings or ApiSettings.from_env()

    app = FastAPI(
        title="AICTE-DocVerf Officer API",
        version="0.1.0",
        description=(
            "Read-only pipeline results plus officer finding actions and decisions. "
            "The API never approves or rejects an application on its own."
        ),
    )
    app.state.settings = resolved
    app.state.pipelines = PipelineRepository(resolved.pipeline_dir)
    app.state.store = OfficerStore(resolved.db_path)
    app.state.store.init_db()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.web_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(applications.router, prefix="/v1")
    app.include_router(findings.router, prefix="/v1")
    app.include_router(files.router, prefix="/v1")
    app.include_router(network.router, prefix="/v1")

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
