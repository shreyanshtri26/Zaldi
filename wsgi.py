"""WSGI entry point: ``python wsgi.py`` for development, or ``gunicorn wsgi:app`` / ``flask --app wsgi run``."""
import os

from zaldi import create_app

app = create_app()

if __name__ == "__main__":
    # One process by default. Flask's debug mode starts an auto-reloader that runs the whole app twice (about double the
    # memory, and a stray copy after a crash), so set ZALDI_DEBUG=1 only while you are editing backend code.
    app.run(debug=os.getenv("ZALDI_DEBUG") == "1", host="127.0.0.1", port=5000, threaded=True)
