# --- 1. build the React frontend -------------------------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- 2. runtime: Flask API + built frontend + headless Chromium for the checkout automation ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8000 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    STOREFRONT_URL=http://127.0.0.1:8000 BROWSER_NO_SANDBOX=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt gunicorn \
 && playwright install --with-deps chromium && chmod -R a+rX /ms-playwright
COPY zaldi/ ./zaldi/
COPY data/seed/ ./data/seed/
COPY wsgi.py ./
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN useradd -m app && mkdir -p data && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health')"
# gthread: the checkout automation calls back into this same server, so it needs more than one request thread.
CMD ["sh", "-c", "gunicorn wsgi:app -b 0.0.0.0:${PORT} -w 2 --threads 8 --timeout 120"]
