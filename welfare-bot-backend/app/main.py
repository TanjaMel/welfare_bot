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

# Serve React frontend static files if they exist
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")

    @app.get("/")
    def serve_frontend():
        return FileResponse(f"{static_dir}/index.html")

    @app.get("/{full_path:path}")
    def serve_frontend_routes(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not found"}
        index_path = f"{static_dir}/index.html"
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"detail": "Frontend not built"}
else:
    @app.get("/")
    def root():
        return {"message": "Welfare Bot backend is running"}