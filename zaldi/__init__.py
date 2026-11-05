"""Zaldi: an AI shopping assistant and CMS for an Indian ethnic-fashion store."""
from flask import Flask


def create_app() -> Flask:
    """Application factory: initialise the database and register the API (and the built frontend)."""
    from zaldi.api import register_api
    from zaldi.db import init_db

    app = Flask(__name__, static_folder=None)
    init_db()
    register_api(app)
    return app
