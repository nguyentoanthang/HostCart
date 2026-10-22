"""
HostCart Main Application.
FastAPI entrypoint mounting CORS middleware, health probes, v1 API routers,
and production React Single Page Application (SPA).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.v1.auth import router as auth_router
from src.api.v1.collection import router as collection_router
from src.api.v1.import_export import router as import_export_router
from src.api.v1.search import router as search_router
from src.api.v1.settings import router as settings_router
from src.core.config import get_settings
from src.data.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes database tables on startup."""
    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title="HostCart Multi-Media Rebuild",
        description="Self-hosted multi-media collection and analytics platform",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/api/health")
    def health_check():
        return {"status": "ok", "app": "HostCart"}

    # Register API routers under /api/v1 prefix
    api_prefix = settings.server.api_prefix
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(collection_router, prefix=api_prefix)
    app.include_router(search_router, prefix=api_prefix)
    app.include_router(import_export_router, prefix=api_prefix)
    app.include_router(settings_router, prefix=api_prefix)

    # Mount frontend SPA if built
    project_root = Path(__file__).resolve().parents[1]
    frontend_dist = project_root / "frontend" / "dist"

    if frontend_dist.is_dir() and (frontend_dist / "index.html").is_file():
        assets_dir = frontend_dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend_assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            normalized = full_path.lstrip("/")
            if (
                normalized.startswith("api")
                or normalized.startswith("docs")
                or normalized.startswith("redoc")
                or normalized == "openapi.json"
            ):
                raise HTTPException(status_code=404, detail="Not Found")

            target_file = frontend_dist / normalized
            if normalized and target_file.is_file():
                return FileResponse(target_file)

            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.debug,
    )
