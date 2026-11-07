# Architecture

This document explains how Zaldi is built and why. For the agent's internals see [AGENT.md](AGENT.md); for connecting a shop see
[CONNECTORS.md](CONNECTORS.md).

## 1. The system in one picture

``` text
 Shopper's browser                          Shop owner's website
   React chat page (/)                        <script src=".../widget.js" data-store="shop">
          \                                         |  isolated iframe + postMessage bridge
           \________________________________________|
                               |  HTTPS  /api   (X-Store: which shop, X-Session-Id: which shopper)
                               v
                          Flask API  (gunicorn: 2 workers x 8 threads)
        public: chat, stream, cart, feedback  |  admin: owner / viewer / server admin
                               |
     +-------------------------+---------------------------------------------+
     |                         |                                             |
     v                         v                                             v
 Chat service             Admin services                              Stores registry
   guardrails in            products, policies, prompts, settings,    (one data set per shop)
   router                   store connection, AI model + keys,
   agent loop  ---------->  metrics, embed, accounts, server settings
     |  tools (built from what the connector supports)
     v
 StoreConnector -- local | woocommerce | shopify | escuelajs | feed | rest | links | amazon | flipkart
     |
     +-- local store: search (SQL + vectors), cart, orders, returns, checkout (Playwright)
     |
   answer check -> output scrub -> audit log -> metrics (latency, tokens, cost)
                               |
                               v
       SQLite files (one folder per shop)   or   Postgres: one schema per shop + pgvector
```

## 2. Layers and what lives where

| Layer | Code | Responsibility |
|---|---|---|
| HTTP | `zaldi/api/` | Routes, request parsing, authentication, rate limits, store selection, serving the built frontend |
| Services | `zaldi/services/` | Business rules: chat orchestration, cart, returns, accounts, metrics, settings, AI keys, server settings |
| Agent | `zaldi/agent/` | The tool loop, the tools, the answer check |
| AI plumbing | `zaldi/ai/` | Model and embedding factories, prompts, router, guardrails, retry and cache, photo description |
| Connectors | `zaldi/connectors/` | One class per kind of shop, behind one interface |
| Search | `zaldi/search/` | Filter extraction, hybrid ranking, vector indexes (FAISS or pgvector) |
| Data | `zaldi/db/` | One connection API over SQLite and Postgres, schema, seed, repositories, migration |
| Checkout | `zaldi/checkout/` | Playwright automation, confirmation tokens, demo storefront |
| Quality | `zaldi/evals/`, `tests/` | Evaluation suites and the test suite |
| Frontend | `frontend/` | The chat page and the admin portal (React, Vite) |

Dependencies point downward: the API calls services, services call the agent and the data layer, connectors are the only code that
knows about a particular shop platform.

## 3. A chat message, step by step

1. **API** (`api/chat.py`): rate limit, read `X-Session-Id` and `X-Store`, validate input.
2. **Store scope** (`stores.py`): the store slug goes into a context variable, so every database call below reaches that shop's data.
3. **Guardrails** (`ai/guardrails.py`): cap the length, remove personal data, refuse prompt injection.
4. **Router** (`ai/router.py`): decides product search, cart, checkout or small talk, using embeddings plus cue words as a safety check.
5. **Agent or fixed path** (`services/chat_service.py`): a multi-step message, or any message on a connected (non-built-in) store, goes to
   the agent; simple messages on the built-in store use the fast deterministic pipeline.
6. **Agent loop** (`agent/loop.py`): the model calls tools, reads results, calls more, then answers.
7. **Answer check** (`agent/verify.py`): every amount in the reply must come from a tool result.
8. **Output scrub**, then the exchange is logged with latency, tokens, estimated cost, model, prompt version and the check result.
9. **Streaming** (`POST /api/chat/stream`): the same path, with each tool step sent as a server-sent event while it runs.

If the model is rate limited it is retried with backoff, then the next model is tried, then the fixed pipeline answers in plain text.

## 4. Multi-store design

One server can run many shops. The unit of isolation is the **store**:

-   A request names its store in `X-Store` (the widget and the chat page set it from `?store=`). No header means the original default store.
-   `stores.current` is a context variable. `db.connect()` reads it, so repositories and services never pass a store around.
-   **SQLite:** each store is a folder `<data>/stores/<slug>/` with its own `zaldi.db` and search indexes.
-   **Postgres:** each store is a schema `<base>_s_<slug>`; the default store uses the base schema. Each connection sets its `search_path`
    inside the same transaction as the queries, so it is safe behind PgBouncer.
-   The **registry** of stores and the **owner accounts** live in the default store's database.
-   Threads do not inherit context variables, so anything handed to a worker thread (parallel tool calls, the stream endpoint) is wrapped
    with `stores.carry(fn)`. A test fails if a worker reaches the wrong store.

## 5. The data layer

`db.connect()` yields a connection with the sqlite3 surface the whole app was written against: `conn.execute(sql, params)` with `?`
placeholders, rows readable by name or position, `cursor.lastrowid`, `rowcount`.

-   **SQLite** is used directly.
-   **Postgres** (`db/pg.py`) wraps a pooled psycopg connection with the same surface: `?` becomes `%s`, `LIKE` becomes `ILIKE`, an
    `INSERT` into a table with an `id` returns it via `RETURNING`, and `CURRENT_TIMESTAMP` is rewritten so timestamps are text in the same
    format on both databases. `schema.sql` is the single source of truth; the Postgres layer translates it
    (`INTEGER PRIMARY KEY AUTOINCREMENT` becomes `SERIAL`, `REAL` becomes `DOUBLE PRECISION`). Server-side prepared statements are off so it
    works behind Neon's pooled endpoint.
-   **Which database:** the environment's `DATABASE_URL` wins; otherwise an address saved from the admin portal (encrypted in
    `<data>/bootstrap.json`, see `bootstrap.py`); otherwise SQLite. The address cannot live in the database it points to, hence the file.
-   **Vectors:** FAISS files per store on SQLite; on Postgres a `vectors` table (pgvector) with a `vector_meta` fingerprint, so an index
    rebuilds itself when its data or the embedding model changes.
-   **Moving between them:** `python -m zaldi migrate` (also the portal's "Copy my data") copies every store, keeps ids, moves serial
    counters, and refuses to write into a non-empty target unless told to replace it.

Main tables: `products`, `policies`, `quick_actions`, `settings`, `prompts`, `chat_logs`, `feedback`, `audit_log`, `cart_items`,
`preferences`, `session_state`, `orders`, `returns`, `agents`, `agent_runs`, `approvals`, and in the default store `stores` and
`admin_users`. On Postgres also `vectors` and `vector_meta`.

## 6. Authentication and authorisation

| Who | Credential | Can |
|---|---|---|
| Shopper | Random `X-Session-Id` (a UUID the browser makes) | Chat, cart, preferences, checkout for that session |
| Store viewer | Signed account token | Read their store's admin data |
| Store owner | Signed account token (12 h), optionally after a two-step code | Change everything in their store, including AI keys and model |
| Server admin | `ADMIN_TOKEN` environment token, or a password set in the portal | Everything, in every store, plus stores, accounts, database, restart |

The environment `ADMIN_TOKEN` always works as a recovery key, so a forgotten portal password cannot lock the admin out. Account tokens are
signed with `SECRET_KEY`, tied to one store, role and *auth version*, and stop working if the account is deleted or if its password,
role or two-step setting changes. See [SECURITY.md](../SECURITY.md).

## 7. Settings and secrets

| Setting | Where it lives | Who can change it |
|---|---|---|
| Storefront text, colours, quick actions | `settings` table of the store | Owner |
| Prompts and the variant B experiment | `prompts` table of the store | Owner |
| Store connection (which shop, keys) | `settings` rows `store.*` of the store; secrets write-only | Owner |
| AI provider, API keys, model | `settings` rows `ai.*` of the store; keys encrypted (Fernet from `SECRET_KEY`) | Owner |
| Allowed websites for the widget | `settings` row of the store | Owner |
| Admin password | Hash in the default store's `settings` | Server admin |
| Database address | Encrypted `bootstrap.json` on the server's disk | Server admin |
| Everything else (`GOOGLE_API_KEY`, limits, ...) | Environment variables | Whoever runs the server |

Secrets are never returned by any endpoint: the portal is told that a key is set and its last four characters.

## 8. Frontend

Two React apps' worth of screens in one Vite build (`frontend/`): the chat page (`features/chat`) and the admin portal
(`features/admin`). The chat page streams answers, shows live tool steps, product cards, quick replies, a cart panel and the orb
(WebGL, with a CSS fallback). The portal is organised around the owner's tasks: Overview, Products, Policies, Chats, Metrics, Content
(Storefront, Assistant, Store connection, AI model, Add to your website, Account) and, for the server admin only, Server.
`frontend/public/widget.js` is the one-line embed. A separate TypeScript app in `web/` hosts Agent Studio screens.

## 9. Deployment topology

``` text
 GitHub push to main
     |  GitHub Actions: tests, then build
     +--> Cloudflare Pages ......... the built frontend  (zaldi.pages.dev)
     +--> Render (Docker) .......... Flask API + the built frontend, gunicorn, headless Chromium
                                     |
                                     +--> Neon Postgres (optional): all data + pgvector
                                     +--> Persistent disk (/var/data): SQLite, uploads, bootstrap.json
```

See [DEPLOYMENT.md](DEPLOYMENT.md).

## 10. Design decisions

| Decision | Reason |
|---|---|
| One interface over two databases, not an ORM | The whole app already spoke sqlite3's style; a thin wrapper kept every query and test, and made the Postgres move a layer, not a rewrite |
| Store isolation by folder or schema, not a `store_id` column | No query can forget a filter; deleting a shop is dropping a schema; per-store settings and indexes come for free |
| Tools built from connector capabilities | The agent never offers what a shop cannot do; a catalogue-only marketplace and a full shop use the same agent |
| Checks in code, not only in the prompt | A model can be talked out of a rule; it cannot be talked out of a failing validation |
| Deterministic fast path kept beside the agent | Cheap, instant and testable for simple messages; also the fallback when a model is down |
| Provider-neutral AI settings, per store | The owner pays for and chooses their model; the server's key is only a default |
| Recovery key via environment | Portal-managed credentials must never be able to lock the owner out of their own server |
