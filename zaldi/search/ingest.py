"""Catalogue ingestion: (re)build the product vector index. Run with ``python -m zaldi ingest``."""
from zaldi.db import init_db
from zaldi.search.index import build_index


def ingest() -> int:
    init_db()
    return build_index()[1]
