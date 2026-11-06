from zaldi.db import content_repo, init_db
from zaldi.search import index
from zaldi.db import connect, pg
from zaldi.search.ingest import ingest


def test_ingest_indexes_every_product(temp_db):
    n = ingest()
    assert n == len(content_repo.list_rows("products")) > 20
    if pg.enabled():  # on Postgres the vectors live in a table, with the index's fingerprint beside them
        with connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM vectors WHERE kind = 'products'").fetchone()[0] == n
            assert conn.execute("SELECT fingerprint FROM vector_meta WHERE kind = 'products'").fetchone()
    else:
        assert (temp_db / "product_index" / "index.faiss").exists()


def test_vector_search_finds_semantically_close_product(temp_db):
    ingest()
    ids = index.vector_search("banarasi silk saree maroon", k=3)
    names = [content_repo.get_row("products", i)["product_name"] for i in ids]
    assert any("Banarasi" in n for n in names)


def test_index_rebuilds_after_product_edit(temp_db):
    ingest()
    new = content_repo.create_row("products", {"product_code": "Z999", "product_name": "Zebra Print Anarkali",
                                               "price": 1234, "stock_quantity": 3})
    ids = index.vector_search("zebra print anarkali", k=1)  # stale index would not know it
    assert ids == [new["id"]]


def test_index_not_rebuilt_when_unchanged(temp_db, monkeypatch):
    ingest()
    monkeypatch.setattr(index, "build_index", lambda *a, **k: (_ for _ in ()).throw(AssertionError("rebuilt")))
    index.vector_search("kurta")


def test_empty_catalogue_returns_nothing(temp_db):
    init_db()
    for row in content_repo.list_rows("products"):
        content_repo.delete_row("products", row["id"])
    assert index.vector_search("kurta") == []
