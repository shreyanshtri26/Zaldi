"""Serve the built React app (``frontend/dist``) with a client-side-routing fallback."""
from flask import send_from_directory

from zaldi import config

BUILD_HINT = "Frontend not built. Run: cd frontend && npm install && npm run build"


def serve_frontend(path: str):
    dist = config.FRONTEND_DIST
    if not (dist / "index.html").exists():
        return BUILD_HINT, 404
    relative = path.lstrip("/")
    if relative and (dist / relative).is_file():
        return send_from_directory(dist, relative)
    return send_from_directory(dist, "index.html")
