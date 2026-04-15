from pathlib import Path
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app.db import initialize_database

HELLO_WORLD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>PM MVP</title>
  </head>
  <body>
    <h1>Hello World from FastAPI</h1>
    <p>Use <code>/api/health</code> to verify API reachability.</p>
  </body>
</html>
"""


def create_app(frontend_dist_dir: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        db_path = os.getenv("PM_DB_PATH")
        initialize_database(Path(db_path) if db_path else None)
        yield

    app = FastAPI(title="PM MVP Backend", version="0.1.0", lifespan=lifespan)
    frontend_dist = (
        frontend_dist_dir
        if frontend_dist_dir is not None
        else Path(__file__).resolve().parents[1] / "frontend_dist"
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index():
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return HTMLResponse(content=HELLO_WORLD_HTML)

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        requested_file = frontend_dist / full_path
        if requested_file.is_file():
            return FileResponse(requested_file)

        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)

        raise HTTPException(status_code=404, detail="Not Found")

    return app


app = create_app()
