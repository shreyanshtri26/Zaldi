"""Serve the built React app (``frontend/dist``) with a client-side-routing fallback."""
from flask import request, send_from_directory

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
    ancestors = frame_ancestors()
    if ancestors:
        response.headers["Content-Security-Policy"] = ancestors
    return response


def frame_ancestors() -> str | None:
    """Which websites may show the assistant in a frame. Only the embed view (``?embed=1``) is restricted. A store with no websites listed
    cannot be framed anywhere until its owner adds one; the original default store stays open so existing widgets keep working."""
    if request.args.get("embed") != "1":
        return None
    from zaldi import stores
    from zaldi.services import site_config

    slug = (request.args.get("store") or stores.DEFAULT).lower()
    if not stores.SLUG.fullmatch(slug) and slug != stores.DEFAULT or not stores.exists(slug):
        return "frame-ancestors 'none'"
    with stores.use(slug):
        origins = [o.strip() for o in site_config.get_settings()["embed_origins"].split(",") if o.strip()]
    if not origins:
        return None if slug == stores.DEFAULT else "frame-ancestors 'self'"
    return "frame-ancestors 'self' " + " ".join(origins)
