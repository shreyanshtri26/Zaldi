# Zaldi

An AI shopping assistant for an Indian ethnic-fashion store (sarees, kurtas, lehengas, sherwanis, footwear, jewellery), with a built-in **CMS** so store staff can edit products and policies without touching code.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## Features

- **Chat** (React): a raised graphite top bar (no sidebar) with **New chat** on the left and History, assistant settings, cart and apps on the right, a 3D lime **Zaldi orb** that reflects what the assistant is doing (idle, listening, thinking, replying, offline), suggestion chips, product cards, a cart panel and a composer with photo search and **voice input** (browser speech recognition, shown only where supported). While a reply is prepared a status box shows "Zaldi is responding" with a live plan, and a note appears if it takes longer than usual. Ask about products, prices in INR, sizes, COD/UPI, delivery, returns, GST invoices. All UI text is English; the assistant replies in the customer's language (English, Hindi or Hinglish), with a live plan while it works and a collapsible tool card under each answer.
- **Admin panel** (`/admin`): overview, products (table/grid, category chips, sort, slide-over editor), policies, chat transcripts and `Ctrl+K` search. Light and dark themes in the Obsidian Black x Electric Lime palette; the overview cards link straight to the matching list.
- **CMS-managed content** (admin → Content): the welcome greeting ("Hi there, Zaldi."), heading (wrap words in `*stars*` to highlight them), text, brand name and tagline, the five brand colours (which also recolour the logo and tab icon), the quick-action cards on the empty chat, and the assistant's prompts can all be edited without code. Every value starts as a built-in default; clearing a field or pressing "Reset to default" restores it. Prompt edits apply to the very next customer message.
- **Agentic shopping pipeline** (see `docs/IMPLEMENTATION_PLAN.md`): guardrails -> optional photo (vision) -> semantic router (products / cart / checkout / chitchat) -> entity extraction -> hybrid search -> cart -> browser-automated checkout that **stops for your confirmation**. The LLM only words the final reply; everything else is deterministic and testable offline.
- **Hybrid search**: free text becomes structured filters (budget, colour, size, category, brand, gender; English/Hinglish), applied as hard SQL filters, then ranked by FAISS vector similarity + lexical match (RRF). Saved shopper preferences are injected automatically; if nothing matches, soft filters are relaxed and the reply says so.
- **Cart and checkout**: stock-checked cart, shipping/coupon pricing from the store policy, then a Playwright run fills a multi-step checkout (built-in demo storefront at `/store-sim`, or point `STOREFRONT_URL` at another) and halts before payment. The customer confirms with a signed, expiring, single-use token. Addresses are typed into a form, never into the chat/LLM; no card or UPI details are ever handled.
- **Guardrails**: PII (phone, email, Aadhaar, PAN, card, UPI) is redacted before any LLM call and from logs; prompt-injection messages are refused before any model runs; replies are scrubbed for PII and system-prompt leaks.
- **Embeddings**: Gemini by default; with no `GOOGLE_API_KEY` (or `EMBEDDING_PROVIDER=local`) an offline hashing embedder keeps everything working (word-level matching only).

## Design system

- **Palette** (editable in admin -> Content -> Storefront): Black `#090B0A`, Electric Lime `#C1F75A`, Graphite `#202622`, Leaf Green `#79B83D`, Silver `#D8DED8`. `frontend/src/styles/tokens.css` derives every surface, border, text and focus colour from these with `color-mix`, in a dark theme (default) and a light theme. Status colours (success, warning, error, info) are fixed per theme.
- **Type and icons**: Inter; one hand-tuned SVG icon family in `shared/components/Icon.jsx` (no icon library).
- **Motion**: smooth scrolling with [Lenis](https://lenis.dev/); the orb and smoke respect `prefers-reduced-motion`. The orb's smoke is a small WebGL shader with a CSS fallback.
- **Speed**: one cached bundle (about 70 KB gzipped). Flask serves `/assets/*` with a one-year immutable cache and `index.html` with `no-cache`.

## Architecture

```
React (Vite) ──/api──▶ Flask
 POST /api/chat ─▶ chat_service: ai.guardrails ─▶ ai.vision? ─▶ ai.router ─┬ search.extract + services.preferences ─▶ search.hybrid (SQL + FAISS) ─▶ LLM wording
 /api/cart, /api/preferences                                                ├ services.cart_chat ─▶ services.cart
 /api/checkout/{prepare,confirm,cancel} ─▶ checkout.handshake ─▶ checkout.automation (Playwright) ─▶ /store-sim
                                                                            └ ai.chitchat
```

Run `python -m zaldi ingest` to rebuild the product vector index (it also rebuilds itself when products change).

## Deploy

`docker compose up --build` (needs a `.env`, see `.env.example`). The image bundles the built frontend, gunicorn and headless Chromium; data lives in a named volume. Note: the image build has not been tested in this repo's CI yet.

## Project structure

```
Zaldi/
├── wsgi.py                     Entry point (python wsgi.py / gunicorn wsgi:app)
├── pyproject.toml              Project metadata + pytest and ruff config
├── requirements.txt
├── zaldi/                      Backend package
│   ├── __init__.py             create_app() factory
│   ├── __main__.py, cli.py     Terminal chat: python -m zaldi
│   ├── config.py               Env vars and paths (read as config.NAME so tests can patch them)
│   ├── errors.py               Domain errors (ValidationError)
│   ├── api/                    HTTP layer
│   │   ├── auth.py             admin_required (X-Admin-Token)
│   │   ├── chat.py             POST /api/chat
│   │   ├── admin.py            /api/admin/login, stats, settings, prompts
│   │   ├── site.py             GET /api/site-config (public storefront text + quick actions)
│   │   ├── content.py          make_content_blueprint(): CRUD for products and policies
│   │   ├── errors.py           error handlers (400 / JSON 404)
│   │   └── frontend.py         serves frontend/dist with SPA fallback
│   ├── services/
│   │   ├── chat_service.py     handle_query(): route, answer, log
│   │   ├── site_config.py      setting defaults, validation, storefront config
│   │   └── prompt_service.py   list / update / reset the editable prompts
│   ├── ai/
│   │   ├── models.py           get_llm(), get_embeddings()
│   │   ├── prompts.py          all prompt text
│   │   ├── router.py           Route enum + SemanticRouter
│   │   ├── route_samples.py    example utterances per route
│   │   ├── agent.py, chitchat.py
│   │   └── tools/              product_search.py (SQL), policy_search.py (FAISS)
│   └── db/
│       ├── connection.py       connect(), init_db()
│       ├── schema.sql, seed.py
│       ├── content_repo.py     products / policies / quick_actions CRUD + validation
│       ├── override_repo.py    settings and prompt overrides (missing row = default)
│       └── chat_log_repo.py    chat logs + dashboard stats
├── frontend/                   React + Vite
│   └── src/
│       ├── api/client.js       all HTTP calls
│       ├── features/chat/      ChatPage, ChatPanel, useChats (history in localStorage)
│       ├── features/admin/     AdminPage (gate), LoginForm, AdminWorkspace, Dashboard,
│       │                       ProductsView, PoliciesView, ChatsView, SearchDialog, StockBadge,
│       │                       content/ (StorefrontSettings, QuickActionsEditor, PromptsEditor)
│       ├── shared/             components (AppShell, Drawer, Icon), context (Auth, Toast), utils
│       └── styles/             tokens, base, layout, controls, chat, admin, overlays, animations
├── data/
│   ├── seed/                   products.csv, policy.txt, raw_data.txt, synthetic_conversations.json
│   └── zaldi.db, policy_index/, router_cache/   generated (gitignored)
├── scripts/generate_synthetic_data.py   optional synthetic chat data via Groq
├── tests/                      api/ (offline), ai/ (offline), live/ (real API calls)
└── .github/workflows/ci.yml    backend tests + frontend build
```

### Naming conventions

- Python: `snake_case` modules, functions and variables; `PascalCase` classes; `UPPER_CASE` constants. Repositories are `*_repo.py`, HTTP modules live in `api/`, orchestration in `services/*_service.py`.
- JavaScript: components and pages are `PascalCase.jsx`; hooks are `useThing.js`; utilities and the API client are lowercase `.js`; feature code lives under `features/<name>/`, cross-feature code under `shared/`.
- CSS: one file per concern under `styles/`, design tokens as CSS variables in `tokens.css`.
- Tests mirror the package: `tests/api`, `tests/ai`, `tests/live`; live tests carry the `live` marker.

## Database schema (`data/zaldi.db`, created on first run)

| Table | Columns |
|-------|---------|
| `products` | `id`, `product_code` (unique), `product_name`, `category`, `material`, `size`, `color`, `brand`, `gender`, `stock_quantity` (>= 0), `price` (INR, GST inclusive, >= 0), `description`, `image_url`, `updated_at` |
| `policies` | `id`, `title` (unique), `content`, `updated_at` |
| `chat_logs` | `id`, `query`, `response`, `route`, `created_at` |
| `quick_actions` | `id`, `title`, `subtitle`, `message`, `icon`, `position`, `active`, `updated_at` |
| `settings` | `key`, `value`, `updated_at` (overrides only) |
| `prompts` | `name`, `content`, `updated_at` (overrides only) |

On first run `products`, `policies` and `quick_actions` are seeded from `data/seed/` (`products.csv`, the `## ` sections of `policy.txt`, `quick_actions.csv`). Older databases are migrated automatically (for example `products.image_url`). After that the **database is the source of truth**; to re-seed, delete `data/zaldi.db`.

## Setup

Prerequisites: Python 3.10+, Node 18+, a Google AI API key ([get one](https://ai.google.dev/)).

```bash
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env             # then fill in the keys (see below)

cd frontend && npm install && npm run build && cd ..
python wsgi.py                   # http://127.0.0.1:5000  (admin at /admin)
```

### Environment variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Gemini chat model + embeddings (embeddings are always Google) |
| `GROQ_API_KEY` | Only if `LLM_PROVIDER=groq` (e.g. `LLM_MODEL=openai/gpt-oss-120b`) |
| `ADMIN_TOKEN` | Password for the admin panel / CMS writes. If unset, write endpoints return 503 |
| `LLM_PROVIDER` / `LLM_MODEL` | Default `google` / `gemini-3.5-flash` |
| `EMBEDDING_MODEL` | Default `models/gemini-embedding-001` |

## Development

```bash
python wsgi.py                  # API on :5000 (debug, auto-reload). Run it inside the venv, or imports like langchain_classic will be missing
cd frontend && npm run dev      # UI on :5173, proxies /api to :5000
python -m zaldi                 # terminal chat
```

## API

| Method & path | Auth | Description |
|---------------|------|-------------|
| `POST /api/chat` `{message}` | public | Returns `{response, type}`; logged to `chat_logs` |
| `GET /api/site-config` | public | Storefront text + active quick actions |
| `GET /api/products?q=&category=` | public | List/search products |
| `GET /api/products/<id>`, `GET /api/policies[/<id>]` | public | Read |
| `POST/PUT/DELETE /api/products[/<id>]`, same for `/api/policies` | `X-Admin-Token` | Manage content |
| `POST/PUT/DELETE /api/quick_actions[/<id>]` | `X-Admin-Token` | Manage quick-action cards |
| `POST /api/admin/login`, `GET /api/admin/stats` | `X-Admin-Token` | Verify token / dashboard data |
| `GET/PUT /api/admin/settings` | `X-Admin-Token` | Read / change storefront text (empty value resets) |
| `GET /api/admin/prompts`, `PUT/DELETE /api/admin/prompts/<name>` | `X-Admin-Token` | Read / change / reset assistant prompts |

## Testing

```bash
python -m pytest -m "not live"     # offline: API, CMS, SQL guard, SPA serving
python -m pytest -m live           # real Google/Groq calls (needs keys and quota)
```

Live tests skip themselves without `GOOGLE_API_KEY`. `tests/api/test_rate_limit.py::test_chat_is_limited_per_visitor` calls the real model, so it fails when the quota is exhausted. The Gemini free tier is limited (about 20 generations per day, 100 embeddings per minute), so run them sparingly. CI (`.github/workflows/ci.yml`) runs the offline tests and builds the frontend; there is no deploy step yet.

## Troubleshooting

- **`Request failed (500)` / "Backend is not running"** in the dev UI: the Vite server on :5173 cannot reach Flask on :5000. Start `python wsgi.py` (from the activated venv).
- **`No module named 'langchain_classic'`** in a chat error: Flask is running under a Python without the project packages. Activate the venv (`venv\Scripts\activate`) or run `pip install -r requirements.txt` in the interpreter you use.
- **"Zaldi is very busy right now. Please try again in a few minutes."**: the model provider rejected the request (for example Gemini `429 RESOURCE_EXHAUSTED`, free tier about 20 generations a day). The customer sees only this message; the detail is in the server log. Wait for the quota to reset, or set `LLM_PROVIDER=groq` and `LLM_MODEL=openai/gpt-oss-120b`. Product and policy questions still get a plain-text answer without the model; model calls use one retry and a 15 second timeout so fallbacks arrive quickly.
- **Dev UI shows old styles or components**: if the project lives in OneDrive, Vite can miss file changes. Restart `npm run dev`.

## Known limitations

- The API is stateless: chat history lives in the browser and the bot does not remember earlier messages.
- Admin auth is a single shared token; use HTTPS and a long random `ADMIN_TOKEN` in production.
- Embeddings use Google even when `LLM_PROVIDER=groq`.

## License

MIT. Made by [shreyanshtri26](https://github.com/shreyanshtri26).
