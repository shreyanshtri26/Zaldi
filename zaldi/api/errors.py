"""App-wide error handling: domain errors become 400s, unknown paths become JSON 404s or the React app."""
from flask import Flask, jsonify, request

from zaldi.api.frontend import serve_frontend
from zaldi.errors import ValidationError


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(404)
    def handle_not_found(_):
        if request.path.startswith("/api/"):
            return jsonify(error="not found"), 404
        return serve_frontend(request.path)
