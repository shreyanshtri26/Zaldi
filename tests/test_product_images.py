"""Bulk photo import: files named after product codes get stored and linked; everything else is reported, never linked."""
import pytest

from zaldi import config
from zaldi.cli import main
from zaldi.db import connect, init_db
from zaldi.errors import ValidationError
from zaldi.services.product_images import import_folder

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@pytest.fixture(autouse=True)
def env(temp_db):
    init_db()


@pytest.fixture
def photos(temp_db):
    folder = temp_db / "photos"          # its own folder: the temp directory also holds the test database
    folder.mkdir()
    return folder


def image_of(code):
    with connect() as conn:
        return conn.execute("SELECT image_url FROM products WHERE product_code = ?", (code,)).fetchone()["image_url"]


def test_photos_named_after_codes_are_linked_whatever_the_case_or_extension(photos):
    (photos / "P001.png").write_bytes(PNG)
    (photos / "p002.jpeg").write_bytes(JPEG)
    report = import_folder(photos)
    assert sorted(report["linked"]) == ["P001", "P002"]
    for code, ext in (("P001", ".png"), ("P002", ".jpg")):                      # stored by content type, under random names
        url = image_of(code)
        assert url.startswith("/uploads/") and url.endswith(ext) and (config.UPLOAD_DIR / url.rsplit("/", 1)[1]).read_bytes()
    assert "P001" not in report["without_photo"] and "P003" in report["without_photo"]


def test_bad_files_are_reported_and_never_linked(photos):
    (photos / "P001.png").write_bytes(b"this is not an image")
    (photos / "P002.png").write_bytes(PNG + b"0" * (3 * 1024 * 1024))
    (photos / "NOPE99.png").write_bytes(PNG)
    (photos / "notes.txt").write_bytes(b"hello")
    report = import_folder(photos)
    assert report["linked"] == []
    assert {name for name, _ in report["rejected"]} == {"P001.png", "P002.png"}
    assert sorted(report["unmatched"]) == ["NOPE99.png", "notes.txt"]
    assert image_of("P001") in (None, "") and image_of("P002") in (None, "")


def test_a_missing_folder_is_a_plain_error(photos):
    with pytest.raises(ValidationError):
        import_folder(photos / "nowhere")


def test_the_command_line_reports_what_it_did(photos, monkeypatch, capsys):
    (photos / "P001.png").write_bytes(PNG)
    monkeypatch.setattr("sys.argv", ["zaldi", "import-images", str(photos)])
    main()
    out = capsys.readouterr().out
    assert "Linked 1 photos." in out and "products still have no photo." in out
    monkeypatch.setattr("sys.argv", ["zaldi", "import-images"])
    with pytest.raises(SystemExit):
        main()
