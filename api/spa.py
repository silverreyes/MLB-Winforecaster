"""SPA static file serving for React frontend.

Subclasses FastAPI's StaticFiles to serve index.html for unknown paths,
enabling client-side routing in single-page applications.
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse


class SPAStaticFiles(StaticFiles):
    """StaticFiles mount that falls back to index.html for SPA routing."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except Exception:
            return FileResponse(Path(self.directory) / "index.html")
