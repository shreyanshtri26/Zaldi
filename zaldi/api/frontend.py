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
        response = send_from_directory(dist, relative)
        if relative.startswith("assets/"):  # Vite fingerprints these names, so a changed file always gets a new URL
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    response = send_from_directory(dist, "index.html")
    response.headers["Cache-Control"] = "no-cache"  # always revalidate so a new build is picked up
    return response
