"""Mount the Phase 6 static workbench on the FastAPI app."""

from __future__ import annotations

from drama_web import static_dir
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_workbench(app: FastAPI) -> None:
    root = static_dir()
    index = root / "index.html"

    @app.get("/", include_in_schema=False)
    def workbench_index() -> FileResponse:
        return FileResponse(index)

    @app.get("/workbench", include_in_schema=False)
    def workbench_alias() -> FileResponse:
        return FileResponse(index)

    if root.is_dir():
        app.mount("/static", StaticFiles(directory=str(root)), name="workbench-static")
