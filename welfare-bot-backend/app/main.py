from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.db.base import Base
from app.db.session import engine

# Auto-create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Welfare Bot API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


# Serve React frontend
POSSIBLE_STATIC_DIRS = [
    Path(__file__).resolve().parent / "static",  # app/static
    Path("/app/static"),                         # Railway absolute path
    Path.cwd() / "static",                       # cwd/static
]

static_dir: Path | None = None

for path in POSSIBLE_STATIC_DIRS:
    if path.exists() and (path / "index.html").exists():
        static_dir = path
        break


if static_dir:
    assets_dir = static_dir / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        return FileResponse(static_dir / "index.html")

    @app.get("/site.webmanifest", include_in_schema=False)
    def serve_manifest():
        return FileResponse(
            static_dir / "site.webmanifest",
            media_type="application/manifest+json",
        )

    @app.get("/logo.png", include_in_schema=False)
    def serve_logo():
        return FileResponse(static_dir / "logo.png")

    @app.get("/icon.png", include_in_schema=False)
    def serve_icon():
        icon_path = static_dir / "icon.png"
        if icon_path.exists():
            return FileResponse(icon_path)

        # fallback if you use logo.png as UI logo
        return FileResponse(static_dir / "logo.png")

    @app.get("/favicon.ico", include_in_schema=False)
    def serve_favicon_ico():
        return FileResponse(static_dir / "favicon.ico")

    @app.get("/favicon.svg", include_in_schema=False)
    def serve_favicon_svg():
        return FileResponse(static_dir / "favicon.svg")

    @app.get("/favicon-16x16.png", include_in_schema=False)
    def serve_favicon_16():
        return FileResponse(static_dir / "favicon-16x16.png")

    @app.get("/favicon-32x32.png", include_in_schema=False)
    def serve_favicon_32():
        return FileResponse(static_dir / "favicon-32x32.png")

    @app.get("/apple-touch-icon.png", include_in_schema=False)
    def serve_apple_touch_icon():
        return FileResponse(static_dir / "apple-touch-icon.png")

    @app.get("/android-chrome-192x192.png", include_in_schema=False)
    def serve_android_192():
        return FileResponse(static_dir / "android-chrome-192x192.png")

    @app.get("/android-chrome-512x512.png", include_in_schema=False)
    def serve_android_512():
        return FileResponse(static_dir / "android-chrome-512x512.png")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_routes(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)

        return FileResponse(static_dir / "index.html")

else:
    @app.get("/", include_in_schema=False)
    def root():
        checked = {str(path): path.exists() for path in POSSIBLE_STATIC_DIRS}
        return {
            "message": "Welfare Bot backend is running",
            "static_checked": checked,
        }