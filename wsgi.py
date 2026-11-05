"""WSGI entry point: ``python wsgi.py`` for development, or ``gunicorn wsgi:app`` / ``flask --app wsgi run``."""
from zaldi import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
