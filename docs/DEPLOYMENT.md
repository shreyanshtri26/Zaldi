# Deployment

## 1. What runs where

| Piece | Where | Notes |
|---|---|---|
| Frontend (the built React app) | Cloudflare Pages (`zaldi.pages.dev`) and also served by the API | Published by GitHub Actions on every push to `main` once tests pass |
| API (Flask + gunicorn) | Render, Docker (`render.yaml`) | Redeploys from the same commit; health check `/api/health` |
| Database | SQLite on Render's disk, or Postgres on Neon | See section 4 |
| Photos, search indexes, `bootstrap.json` | The persistent disk (`DATA_DIR`, `/var/data` on Render) | Needs a plan with a persistent disk |

## 2. Docker

``` bash
docker compose up --build
```

The image bundles the built frontend, gunicorn (2 workers x 8 threads) and headless Chromium for the checkout automation. Data lives in a
named volume. The image build is not verified by CI: check it, and the checkout automation, in staging first.

## 3. Render

`render.yaml` is a Blueprint. Secrets marked `sync: false` are entered once in the Render dashboard.

| Variable | Purpose |
|---|---|
| `ADMIN_TOKEN` | The server admin's recovery key (always keep one) |
| `SECRET_KEY` | Signs tokens and encrypts stored keys. Generated for you; **do not change it later** or saved keys and the saved database address cannot be read |
| `GOOGLE_API_KEY`, `GROQ_API_KEY` | The server's default model keys (stores can bring their own) |
| `DATA_DIR` | `/var/data` (the disk) |
| `DATABASE_URL` | Optional: Neon's pooled connection string |

## 4. Moving to Postgres (Neon)

Set `DATABASE_URL`, or use **Admin -> Server -> Database** (see the [admin guide](ADMIN_GUIDE.md)). Use Neon's **pooled** connection string and
make sure the `vector` extension is available (Neon includes it).

On the first start with a Postgres address the app creates the tables and, like a fresh install, seeds the sample catalogue.

**Carrying over data you already have on SQLite**, choose one:

-   **From the portal** (works on the hosted server, no shell needed): Server -> Database -> paste the address -> Test connection ->
    Copy my data (tick *replace* if the database already holds the sample data, and type `REPLACE`).
-   **From a shell on the server:** `python -m zaldi migrate` (add `--replace` to erase what is in the target first).

The copy keeps ids, moves the counters past them, never changes the SQLite files, and the search index rebuilds on the first search.
Afterwards the SQLite files remain on the disk as a backup.

## 5. Cloudflare Pages

`.github/workflows/deploy.yml` publishes `frontend/dist` to Cloudflare Pages after the tests pass. It needs the repository secrets for the
Cloudflare account and project (see the workflow file). The API on Render redeploys itself from the same commit.

## 6. Configuration summary

See the README's configuration table for every variable. Anything an owner can change in the portal (store connection, AI keys and model,
prompts, storefront) does not need an environment variable.

## 7. Backups

-   **SQLite:** back up `DATA_DIR` (databases, uploads). Copying while the app runs is safe for reading, but stop it for a perfect copy.
-   **Postgres:** use Neon's branching and point-in-time restore, or `pg_dump` per schema (`public` and `public_s_<store>`).
-   Keep `SECRET_KEY` with the backup: without it saved API keys and the saved database address cannot be decrypted.

## 8. Upgrading

Pull the new commit and restart. New columns and tables are added automatically on start (`MIGRATIONS` in `db/connection.py`, plus
`CREATE TABLE IF NOT EXISTS`); nothing is dropped.

## 9. Restarting

Server -> Database -> **Restart now** (type `RESTART`). Under gunicorn the master reloads every worker; elsewhere the process exits and
the platform (Render, Docker's restart policy) starts it again. A development server simply stops.

## 10. Production checklist

-   [ ] HTTPS everywhere; `ADMIN_TOKEN` and `SECRET_KEY` are long and random.
-   [ ] A persistent disk, or Postgres, so data survives redeploys.
-   [ ] Model keys set (server or per store) and a daily agent cap (`AGENT_DAILY_RUNS`) you are comfortable with.
-   [ ] Each shop lists its allowed websites.
-   [ ] Rate limits left on (`RATE_LIMIT_CHAT`, `RATE_LIMIT_LOGIN`).
-   [ ] `ALLOW_SIGNUP` off unless you want strangers to create shops; `ALLOW_PRIVATE_STORE_URLS` off.
