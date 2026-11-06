# Development

## 1. Set up

``` bash
git clone <repository-url> && cd Zaldi
python -m venv venv && source venv/bin/activate      # Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                  # add keys if you have them; none are needed to run the tests
cd frontend && npm install && npm run build && cd ..
python wsgi.py                                        # http://127.0.0.1:5000  and  /admin
```

For frontend work run `npm run dev` in `frontend/` (port 5173, proxies `/api` to 5000). Set `ZALDI_DEBUG=1` for the Flask reloader.
Run Python through the project's virtual environment so dependencies resolve.

## 2. Repository map

``` text
zaldi/
  agent/        loop.py (tool loop), tools.py (tools from capabilities), verify.py (answer check)
  ai/           models (chat + embeddings), prompts, router, routing (model choice), guardrails, resilience, vision, tools/ (policy search)
  api/          chat, shop, admin, content, agents, insights, store_admin, server_admin, uploads, auth, ratelimit, frontend
  checkout/     Playwright automation, handshake + tokens, demo storefront
  connectors/   base, local, woocommerce, shopify, escuelajs, feed, rest, linkpage, amazon, flipkart, catalogue, netguard
  db/           connection (SQLite or Postgres), pg, schema.sql, seed, migrate, repositories
  search/       extract, hybrid, index (FAISS), pgvec (pgvector), ingest
  services/     chat_service, cart, returns, preferences, accounts, ai_key, server_settings, onboarding, metrics, site_config, store_settings, ...
  evals/        retrieval, redteam, agent_eval, harvest, runner
  bootstrap.py, stores.py, telemetry.py, experiments.py, config.py, cli.py
frontend/       React + Vite: src/features/{chat,admin}, src/shared, src/styles; public/widget.js
web/            separate TypeScript app for Agent Studio
tests/          pytest suite; fakes.py (fake network, connector contract); fixtures/ (recorded API responses)
evals/          agent_cases.jsonl, thresholds.json, RESULTS.md
scripts/        check_marketplaces.py, generate_synthetic_data.py
docs/           this documentation
```

## 3. Running the tests

``` bash
python -m pytest -m "not live"                                    # the offline suite on SQLite (what CI runs)
ZALDI_TEST_DATABASE_URL=postgresql://... python -m pytest -m "not live"   # the same suite on Postgres
python -m pytest -m live                                          # real model calls (needs keys and quota)
python -m zaldi evals all                                         # search quality and attack resistance
python scripts/check_marketplaces.py                              # connectors on recorded responses
```

-   Every test gets a throwaway data directory (`temp_db` in `tests/conftest.py`). On Postgres each test gets its own schema, dropped
    afterwards, so tests never see each other's data. It is slow because each query is a network round trip.
-   Tests are offline by design: models are **scripted** (`tests/test_agent_loop.py`), the network is **fake** (`tests/fakes.py:
    FakeHttp`), and embeddings are the offline hashing embedder. A test that needs the real thing is marked `live`.
-   Browser behaviour (the widget bridge, live steps, the admin screens) is checked with headless Playwright scripts against the built
    frontend and a small stand-in API; see the pull request notes for how.

## 4. Conventions

-   **Python:** `snake_case`, `PascalCase` classes, `UPPER_CASE` constants; type hints on public functions; comments explain *why*.
    Line length 110 (`pyproject.toml`).
-   **React:** `PascalCase.jsx` components, `useThing.js` hooks; one feature per folder; styles in `frontend/src/styles/` by concern, colours
    only through the tokens in `tokens.css`.
-   **SQL:** write queries once, for both databases: `?` placeholders, `LOWER(x) = LOWER(?)` for case-insensitive equality, no SQLite-only
    functions (`datetime('now')`, `COLLATE NOCASE`), cast aggregates you return as numbers (`CAST(SUM(...) AS INTEGER)`).
-   **Secrets:** never log or return a key. New secret settings are write-only and encrypted (see `services/ai_key.py`).
-   **Errors:** raise `ValidationError` with a message a person can act on; it becomes a 400.

## 5. Adding things

| To add | Do |
|---|---|
| A setting an owner changes | Add it to `services/site_config.py: SETTINGS` (validate it), show it in a Content panel |
| An endpoint | Put it in the right `api/` module; `@admin_required` (owner/viewer) or `@server_admin_required`; add tests including the 401/403 cases |
| A table or column | New table: add it to `db/schema.sql`. New column on an existing table: add to `MIGRATIONS` in `db/connection.py` and `schema.sql` |
| A connector | See [CONNECTORS.md](CONNECTORS.md) section 7 |
| An agent tool | See [AGENT.md](AGENT.md) section 8 |
| A model provider | `services/ai_key.py: PROVIDERS` and `ai/models.py: get_llm` |

## 6. Pull request checklist

-   [ ] Tests for the behaviour, including failure and permission cases.
-   [ ] `python -m pytest -m "not live"` passes; `npm run build` passes.
-   [ ] If you touched SQL or the data layer, the affected tests also pass on Postgres.
-   [ ] New environment variables and settings are in the README configuration table and the docs.
-   [ ] No secrets, databases, indexes or `.env` files committed.

## 7. Troubleshooting a dev machine

| Problem | Fix |
|---|---|
| `No module named 'langchain_classic'` | Wrong interpreter: activate the venv and reinstall requirements |
| A script named `typing.py` or `json.py` next to your script breaks imports | Run Python with `-I` (isolated mode) |
| Stale styles on a OneDrive folder | Restart `npm run dev` |
| Many `wsgi.py` processes use memory | Stop strays; the server runs one process unless `ZALDI_DEBUG=1` |
