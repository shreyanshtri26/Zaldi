"""Admin photo upload: only images, only for the admin, stored under random names, served back safely."""
import io

import pytest

from tests.helpers import ADMIN_HEADERS
from zaldi import config

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 64


def upload(client, data, name="photo.png", headers=ADMIN_HEADERS):
    return client.post("/api/admin/upload", data={"image": (io.BytesIO(data), name)}, headers=headers, content_type="multipart/form-data")


def test_upload_needs_the_admin_token(client):
    assert upload(client, PNG, headers={}).status_code == 401


@pytest.mark.parametrize("data, ext", [(PNG, ".png"), (JPEG, ".jpg"), (WEBP, ".webp")])
def test_an_image_is_stored_and_served_back_unchanged(client, data, ext):
    out = upload(client, data, name="whatever-name.bin")                # the claimed name is ignored; the bytes decide
    assert out.status_code == 201
    url = out.get_json()["url"]
    assert url.startswith("/uploads/") and url.endswith(ext) and len(url) == len("/uploads/") + 32 + len(ext)
    served = client.get(url)
    assert served.status_code == 200 and served.data == data
    assert served.headers["X-Content-Type-Options"] == "nosniff" and "immutable" in served.headers["Cache-Control"]


@pytest.mark.parametrize("data, why", [
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "svg can carry script"),
    (b"just some text pretending to be a photo", "not an image"),
    (b"", "empty"),
    (PNG + b"0" * (3 * 1024 * 1024), "over 3 MB"),
])
def test_other_files_are_refused(client, data, why):
    assert upload(client, data).status_code == 400, why
    assert not list(config.UPLOAD_DIR.glob("*")) if config.UPLOAD_DIR.exists() else True


def test_a_request_without_a_file_is_refused(client):
    assert client.post("/api/admin/upload", headers=ADMIN_HEADERS, data={}, content_type="multipart/form-data").status_code == 400


@pytest.mark.parametrize("name", ["../zaldi.db", "..%2Fzaldi.db", "notahexname.png", "a" * 32 + ".svg", "a" * 32 + ".png"])
def test_only_names_the_server_generated_can_be_fetched(client, name):
    assert client.get(f"/uploads/{name}").status_code == 404           # includes a well-formed name that was never uploaded


def test_an_uploaded_photo_can_become_a_products_image(client):
    url = upload(client, PNG).get_json()["url"]
    created = client.post("/api/products", headers=ADMIN_HEADERS, json={"product_code": "UP1", "product_name": "Photo Kurta", "price": 100, "image_url": url})
    assert created.status_code == 201 and created.get_json()["image_url"] == url
