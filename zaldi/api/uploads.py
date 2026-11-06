"""Product photos uploaded from the admin editor.

Saved under ``DATA_DIR/uploads`` (the same persistent volume as the database) with a random name and served back from
``/uploads/<name>``. The type is decided from the file's own first bytes, never from its claimed name or content type, and
SVG is not accepted (it can carry script). The product's ``image_url`` then simply holds the returned ``/uploads/...`` path.
"""
import re
import uuid

from flask import Blueprint, abort, jsonify, request, send_from_directory

from zaldi import config
from zaldi.api.auth import admin_required
from zaldi.errors import ValidationError

MAX_BYTES = 3 * 1024 * 1024
NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

bp = Blueprint("uploads", __name__)      # under /api: the admin-only upload
files = Blueprint("files", __name__)     # at the site root: serving what was uploaded


def _extension(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_image(data: bytes) -> str:
    """Validate a photo by its own bytes and store it under a random name. Returns its ``/uploads/...`` path."""
    if not data or len(data) > MAX_BYTES:
        raise ValidationError("image must be between 1 byte and 3 MB")
    extension = _extension(data)
    if extension is None:
        raise ValidationError("image must be a JPEG, PNG or WebP file")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex + extension
    (config.UPLOAD_DIR / name).write_bytes(data)
    return f"/uploads/{name}"


@bp.post("/admin/upload")
@admin_required
def upload():
    photo = request.files.get("image")
    if photo is None:
        raise ValidationError("choose an image file")
    return jsonify(url=save_image(photo.read(MAX_BYTES + 1))), 201


@files.get("/uploads/<name>")
def serve(name: str):
    if not NAME.match(name):  # only names this module generated: no paths, no other files
        abort(404)
    response = send_from_directory(config.UPLOAD_DIR, name)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # names are random and never reused
    return response
