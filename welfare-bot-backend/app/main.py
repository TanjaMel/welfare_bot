from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

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

# Serve React frontend — check multiple possible static paths
POSSIBLE_STATIC_DIRS = [
    os.path.join(os.path.dirname(__file__), "static"),  # local: app/static
    "/app/static",                                        # Railway absolute path
    os.path.join(os.getcwd(), "static"),                 # cwd/static
]

static_dir = None
for path in POSSIBLE_STATIC_DIRS:
    if os.path.exists(path) and os.path.exists(os.path.join(path, "index.html")):
        static_dir = path
        break

if static_dir:
    app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")

    @app.get("/")
    def serve_frontend():
        return FileResponse(f"{static_dir}/index.html")

    @app.get("/{full_path:path}")
    def serve_frontend_routes(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not found"}
        index_path = f"{static_dir}/index.html"
        return FileResponse(index_path)
else:
    @app.get("/")
    def root():
        # Debug: show what paths were checked
        checked = {p: os.path.exists(p) for p in POSSIBLE_STATIC_DIRS}
        return {"message": "Welfare Bot backend is running", "static_checked": checked}