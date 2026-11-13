"""Serve the built single-page frontend from the API process (single-container deploy)."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

# Keep in sync with frontend/nginx.conf (tests/test_static.py compares them).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'"
    ),
}
ASSETS_PREFIX = "assets/"
API_PREFIX = "api"
INDEX = "index.html"
# Vite emits content-hashed filenames under /assets, so they can never go stale.
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
# Revalidate (ETag) every time so a redeploy is picked up immediately.
REVALIDATE_CACHE = "no-cache"


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _resolve_file(root: Path, path: str) -> Path | None:
    """The file under root for path, or None if absent or outside root (traversal, symlink)."""
    try:
        candidate = (root / path).resolve()
    except (ValueError, OSError):  # e.g. NUL byte in the path
        return None
    if candidate.is_file() and candidate.is_relative_to(root):
        return candidate
    return None


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Register the catch-all last, so every real /api route matches before it."""
    root = static_dir.resolve()
    index = root / INDEX

    def respond(file: Path, cache_control: str) -> Response:
        headers = {**SECURITY_HEADERS, "Cache-Control": cache_control}
        return FileResponse(file, headers=headers)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> Response:
        if _is_api_path(path):
            raise HTTPException(status_code=404, detail="Not Found")
        file = _resolve_file(root, path)
        if file is not None:
            immutable = file.is_relative_to(root / ASSETS_PREFIX)
            return respond(file, IMMUTABLE_CACHE if immutable else REVALIDATE_CACHE)
        if path.startswith(ASSETS_PREFIX):  # a missing asset must not be answered with HTML
            raise HTTPException(status_code=404, detail="Not Found")
        return respond(index, REVALIDATE_CACHE)
