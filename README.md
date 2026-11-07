# Zaldi

**Agentic AI for E-commerce**

Zaldi is an agentic AI shopping assistant that plugs into any online shop, with an admin portal to run it. Shoppers talk to a store: they find products, compare them, understand policies, build a cart, check out, or return an order. Behind the
chat is a tool-using AI agent that reads the shop's real catalogue and policies instead of guessing. Behind the agent is a built-in admin
portal where the person who builds the shop controls everything without code: which store the agent searches, what it may do, which AI
model (and whose key) answers, what it says, how it looks, and where it appears.

Zaldi began as an assistant for Indian ethnic fashion (INR prices; English, Hindi and Hinglish) and is now an e-commerce platform. It can sit on top of
**a shop built with Zaldi**, **an existing site** (Shopify, WooCommerce, a product feed or any API), or **products listed elsewhere**
(Amazon, Flipkart, or plain product pages).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Build-Vite-646CFF.svg)](https://vite.dev/)

------------------------------------------------------------------------

## Contents

-   [Why Zaldi](#why-zaldi)
-   [Features](#features)
-   [Documentation](#documentation)
-   [Quick start](#quick-start)
-   [How it works](#how-it-works)
-   [Connect any shop](#connect-any-shop)
-   [The admin portal](#the-admin-portal)
-   [Add the assistant to your website](#add-the-assistant-to-your-website)
-   [Quality, safety and cost](#quality-safety-and-cost)
-   [Technology](#technology)
-   [Project structure](#project-structure)
-   [Configuration](#configuration)
-   [Database](#database)
-   [Testing and CI](#testing-and-ci)
-   [Deployment](#deployment)
-   [Status and limitations](#status-and-limitations)
-   [Contributing, security, license](#contributing-security-license)

## Why Zaldi

There are two kinds of people. The **admin** builds the e-commerce website: they sign in to `/admin`, connect their products, set the
assistant's wording and permissions, choose the AI model, and paste one line into their site. The **shoppers** are normal visitors: they
only see the chat. One Zaldi server can run many shops, each completely separate.

What makes it *agentic* and not just a chatbot:

-   The model **chooses tools** (search, policies, cart, orders, preferences, asking the shopper) step by step and answers from what they return.
-   Every claim is **checked**: a price the tools did not return is caught and repaired before the shopper sees it.
-   Anything that changes something (cart, checkout, returns) is **limited in code** and ends in the shopper's own confirmation.
-   Behaviour is **measured**: evaluation suites, attack tests, latency, token and cost tracking, and shopper feedback.

## Features

| For shoppers | For the shop owner | For the server admin |
|---|---|---|
| Natural-language search with budgets, colours, sizes | Connect Shopify, WooCommerce, a feed, any API, product links, Amazon, Flipkart, or Zaldi's own shop | Several shops on one server, each isolated |
| Hindi, Hinglish and English | Edit products, policies, prompts, colours, quick actions | A **Stores** page: create stores, draft/live, owner and viewer accounts, reset links; sign-up on or off |
| Product cards with photos, prices, ratings, a −1+ stepper | Use your own Gemini or Groq key and pick the model from a live list | Admin password and database set from the portal |
| Questions asked back with tappable answers | Test connection checklist in plain words | Copy data from SQLite to Postgres, restart from the portal |
| Cart, checkout, order status, returns (with confirmation) | See every chat and the tools used; metrics on speed, cost, accuracy | One-command Docker, Render + Cloudflare + Neon |
| Live tool steps while it thinks; thumbs up/down | Embed on any website with one line; allowed websites per shop | Evaluation suites and a CI gate |
| Photo search and voice input | A/B test a second prompt on half the shoppers | Audit log of every tool call |

## Documentation

| Read | For |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the system is built and why: layers, the chat path, multi-store design, the data layer, auth |
| [docs/AGENT.md](docs/AGENT.md) | The agent: tools, loop, answer check, models and resilience, memory, retrieval, extending it |
| [docs/CONNECTORS.md](docs/CONNECTORS.md) | Every connector, capability levels, the card format, writing a new connector |
| [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md) | The portal for owners and the server admin: AI model and keys, passwords, database |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, Render, Cloudflare Pages, Neon, moving data, backups, upgrading |
| [docs/API.md](docs/API.md) | Every endpoint, with headers, bodies and responses |
| [docs/EVALUATION.md](docs/EVALUATION.md) | The evaluation suites, the live agent result and its caveats |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Set-up, repository map, tests, conventions |
| [SECURITY.md](SECURITY.md) | The threat model, deploy checklist, how to report a vulnerability |
| [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md) | How to help; what changed |

## Quick start

``` bash
git clone <repository-url> && cd Zaldi
python -m venv venv && source venv/bin/activate      # Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                                  # add GOOGLE_API_KEY and ADMIN_TOKEN
cd frontend && npm install && npm run build && cd ..
python wsgi.py
```

Open http://127.0.0.1:5000 for the shop and http://127.0.0.1:5000/admin for the portal (sign in with the **Server admin** tab and your
`ADMIN_TOKEN`). Without a Gemini key an offline embedder and a plain-text fallback keep the app usable, but real semantic search and
conversational answers need a model key (set one in the portal under Content -> AI model, or in `.env`). Prerequisites: Python 3.10+,
Node 18+. Or with Docker: `docker compose up --build`.

## How it works

``` text
 Shopper's browser                          Shop owner's website
   React chat page (/)                        <script src=".../widget.js" data-store="shop">
          \                                         |  isolated frame + message bridge
           \________________________________________|
                               |  /api   (X-Store picks the shop)
                               v
                           Flask API
        public: chat, stream, cart, feedback  |  admin: owner / viewer / server admin
                               |
     +-------------------------+---------------------------------------------+
     v                         v                                             v
 Chat service             Admin services                              Stores registry
   guardrails in            products, policies, prompts, settings,    (one data set per shop)
   router                   store connection, AI model + keys,
   agent loop  ---------->  metrics, embed, accounts, server settings
     |  tools built from what the connector supports
     v
 StoreConnector -- local | woocommerce | shopify | escuelajs | feed | rest | links | amazon | flipkart
     |
   answer check -> output scrub -> audit log -> metrics (latency, tokens, cost)
                               |
                               v
       SQLite files (per shop)   or   Postgres: one schema per shop + pgvector (Neon)
```

**One message:** guardrails (personal data removed, injection refused) -> router (search, cart, checkout, small talk) -> agent loop (the
model calls tools; read-only calls run in parallel) -> answer check (every amount must come from a tool) -> scrub -> log. If the model is
rate limited it is retried, then the next model is tried, then a plain-text pipeline answers, so a shopper always gets an answer.

The agent's tools, built per shop from what its connector supports:

| Tool | Does |
|---|---|
| `search_products`, `get_product` | Search with query, budget, category, "cheapest"/"top rated"; current details |
| `search_policies` | Returns, shipping, payment, COD, sizing; names the policy section it used |
| `view_cart`, `add_to_cart`, `remove_from_cart` | Cart with stock checks; only products the shopper was shown |
| `remember_preference` | Saves size, budget, who they shop for |
| `order_status`, `request_return` | Their orders; a return is only *staged* until they confirm |
| `start_checkout` | Opens the secure delivery form; nothing is bought until they confirm |
| `ask_shopper` | Asks one short question with up to four tappable answers |

Deep dives: [architecture](docs/ARCHITECTURE.md) and [agent](docs/AGENT.md).

## Connect any shop

The admin answers one question, "where do your products live today?"

| Path | Situation | Connect with | Shoppers can |
|---|---|---|---|
| **A. From scratch** | New shop | Zaldi's own catalogue, cart and checkout | Search, cart, check out, orders, returns |
| **B. I have a website** | Shopify, WooCommerce, custom | Store keys, a **product feed** link, or a **custom API** mapping | Search, compare, open on your site |
| **C. I only have links** | Products listed elsewhere | **Amazon** or **Flipkart** affiliate keys, or **product page links** | Search, compare, open the original page |

Set it up in **Admin -> Content -> Store connection**, then press **Test connection**: a checklist says in plain words what works and what
to fix. The agent only gets tools the connection supports (*capability levels*: `catalogue`, `cart`, `orders`), so it never offers what a
shop cannot do. Addresses must be public links; keys are write-only.

> **Amazon and Flipkart** are written from the providers' published docs (Amazon's Creators API replaced PA-API 5 in 2026) and tested against
> documented sample shapes and a local server that enforces their protocols over real HTTP, but **not yet against live accounts**. With your keys run
> `python scripts/check_marketplaces.py --live --record`. See [docs/CONNECTORS.md](docs/CONNECTORS.md).

## The admin portal

At `/admin`: sign in with your own account, create a store (if the server allows), or use the server admin password.

| Page | What it does |
|---|---|
| Overview, Products, Policies, Chats | Catalogue and policy editing; every conversation with the tools used |
| Metrics | Speed, cost per answer, tokens, tool failures, answer checks, thumbs by prompt version |
| Content -> Storefront / Assistant | Greeting, colours, quick actions; prompts and a variant B experiment |
| Content -> Store connection | Which shop the agent searches, with the Test checklist |
| **Content -> AI model** | Provider (Gemini or Groq), **your own API key** (encrypted, write-only, with a test button), and a **model dropdown** fed by the provider's live list |
| Content -> Add to your website | The embed line and the websites allowed to show the assistant |
| Content -> Account | Change your password; turn on **two-step sign-in** with an authenticator app |
| **Stores** *(server admin only)* | Create, delete and set draft/live; manage each store's accounts (roles, **reset links**, turn off two-step) |
| **Server** *(server admin only)* | Admin password set from the portal; **database address** (test, copy data, save, restart) |

Details and a recommended set-up order: [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md).

## Add the assistant to your website

``` html
<script src="https://YOUR-ZALDI-HOST/widget.js" data-store="your-store-id" async></script>
```

Optional: `data-position="left"`, `data-open="true"`. The assistant opens in an isolated frame; the server only lets the websites you list
frame it. The page and the assistant can talk:

``` js
Zaldi.setContext({ title: "Blue Kurta", price: "Rs. 999", sku: "K-9" });   // what the shopper is viewing
Zaldi.on("add-to-cart", (product) => myCart.add(product.id));             // the shopper added something in the chat
Zaldi.on("ready", () => {});  Zaldi.open();  Zaldi.close();
```

Page context reaches the agent as one quoted line of untrusted data (checked for injection, personal data removed). The widget accepts
messages only from its own frame. For marketplace and feed shops the assistant links to the product page; for a shop with its own cart,
listen for `add-to-cart` and use the shop's own cart and checkout.

## Quality, safety and cost

Every claim has a command and a test that fails the build if it stops being true. Details: [docs/EVALUATION.md](docs/EVALUATION.md).

``` bash
python -m zaldi evals all --write      # offline: product search + attack resistance (reproducible)
python -m zaldi evals agent --write    # live: 30 cases through a real model
python -m zaldi evals harvest          # turn thumbs-down and repaired answers into new test cases
```

| Measured | Result |
|---|---|
| Product search, 134 generated queries | keyword-only nDCG 0.899, meaning-only 0.888, **hybrid 0.918**, full pipeline 1.000 |
| Hostile messages refused | 57 / 57, with 0 of 40 ordinary messages wrongly refused |
| Instructions hidden in store data neutralised | 15 / 15 (7 / 7 normal texts untouched) |
| Tool-layer attacks stopped by code | 6 / 6 |
| Live agent, 30 cases (`openai/gpt-oss-120b`) | tool choice **100%**, faithfulness **100%**, median 4.3 s, about $0.0006 per chat |

Honest limits: search labels are rule-made from the catalogue (they test ranking consistency, not taste); the attack lists were written with
the rules (a regression gate, not proof of robustness); the live result is one run of one model on 30 self-written cases, and its first run
scored 96.7% before one case's rubric was corrected (the agent asked for a size, which is sensible). Safety is enforced in code, not only in
prompts: answer check, instruction neutralising, least-privilege tools, confirmation by code, audit log. See [SECURITY.md](SECURITY.md).

## Technology

| Area | Technologies |
|---|---|
| Frontend | React, Vite, JavaScript, CSS, Lenis smooth scrolling, WebGL orb |
| Backend | Python, Flask, Gunicorn |
| AI | LangChain components; Gemini and Groq chat models with tool calling; Gemini or offline embeddings |
| Retrieval | SQL filters, vector search (FAISS files, or pgvector on Postgres), keywords, Reciprocal Rank Fusion |
| Database | SQLite (default) or Postgres such as Neon (psycopg, pooled) |
| Browser automation | Playwright, headless Chromium (checkout preparation) |
| Testing | pytest on SQLite or Postgres, evaluation harness, headless-browser check scripts |
| Deployment | Docker; Cloudflare Pages (frontend) and Render (API) through GitHub Actions; Neon (data) |

## Project structure

``` text
zaldi/
  agent/        tool loop, tools built from capabilities, answer check
  ai/           models, prompts, router, guardrails, retry and cache, photo description
  api/          HTTP routes (chat, shop, admin, content, agents, insights, store_admin, server_admin, uploads, auth)
  connectors/   built-in, WooCommerce, Shopify, Platzi demo, feed, custom API, product links, Amazon, Flipkart
  db/           one connection API over SQLite and Postgres, schema, seed, migration
  search/       filter extraction, hybrid ranking, FAISS and pgvector indexes
  services/     chat, cart, returns, accounts, AI keys, server settings, metrics, settings, onboarding
  checkout/     Playwright automation and confirmation tokens
  evals/        retrieval, attack and live agent suites, harvest
frontend/       React app (chat page, admin portal) and public/widget.js
web/            separate TypeScript app for Agent Studio
tests/  evals/  scripts/  docs/  data/seed/
```

Full map and conventions: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Configuration

Environment variables (keep secrets in `.env`; never commit it). Anything an owner can set in the portal does not need a variable.

| Variable | Purpose |
|---|---|
| `ADMIN_TOKEN` | The server admin's credential. It also stays valid as a recovery key after a portal password is set |
| `SECRET_KEY` | Signs tokens and encrypts stored keys. Falls back to `ADMIN_TOKEN`. **Do not change it later** |
| `GOOGLE_API_KEY`, `GROQ_API_KEY` | The server's default model keys; each store can bring its own |
| `LLM_PROVIDER`, `LLM_MODEL` | Default chat model (`google` / `gemini-3.5-flash`); a store can choose its own |
| `LLM_MODEL_CHEAP` | A cheaper model for simple messages (empty means always `LLM_MODEL`) |
| `LLM_FALLBACK_PROVIDER`, `LLM_FALLBACK_MODEL` | Optional second model if the first fails |
| `LLM_RETRIES`, `LLM_RETRY_BASE` | Extra attempts (2) and first wait in seconds (0.8) on a rate limit |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | `local` for the offline embedder |
| `AGENT_ENABLED`, `AGENT_MAX_STEPS`, `AGENT_DAILY_RUNS` | Agent on/off, tool rounds per answer (5), runs per day cap (500; 0 = unlimited) |
| `STORE_CONNECTOR` and connector settings | Default shop kind and its settings; the portal overrides per store (`WOOCOMMERCE_*`, `SHOPIFY_*`, `ESCUELAJS_URL`, `FEED_URL`, `REST_CONFIG`, `LINK_URLS`, `AMAZON_*`, `FLIPKART_*`) |
| `DATABASE_URL` | Postgres address (Neon pooled). Empty means SQLite, or an address saved from the portal. `PG_SCHEMA`, `PG_POOL_SIZE` tune it |
| `DATA_DIR` | Where SQLite files, uploads and the saved database address live (a persistent disk in production) |
| `ALLOW_SIGNUP` | `1` lets visitors create their own shop and owner account |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | Optional: email password reset links to owners (without them the server admin makes links) |
| `ALLOW_PRIVATE_STORE_URLS` | `1` lets connectors reach localhost (development only) |
| `STOREFRONT_URL` | Storefront the checkout automation drives (default: the built-in demo) |
| `RATE_LIMIT_CHAT`, `RATE_LIMIT_LOGIN` | Requests per minute per visitor (0 = off) |
| `ZALDI_DEBUG` | `1` enables the Flask reloader (development) |

## Database

Zaldi runs on **SQLite** by default (`data/zaldi.db`, one folder per extra shop) or on **Postgres** such as Neon. Choose with
`DATABASE_URL`, or from **Admin -> Server -> Database** (test the address, copy your data, save, restart). On Postgres each shop is a
schema, search vectors live in the database (pgvector), and connections are pooled. The same `schema.sql` creates both.

``` bash
python -m zaldi migrate [--replace]   # copy SQLite data into Postgres (all shops, ids kept, SQLite files untouched)
python -m zaldi ingest                # rebuild the product vector index
```

Tables and the data-layer design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#5-the-data-layer).

## Testing and CI

``` bash
python -m pytest -m "not live"                                    # offline suite on SQLite (CI)
ZALDI_TEST_DATABASE_URL=postgresql://... python -m pytest -m "not live"   # the same suite on Postgres
python -m zaldi evals all                                         # search quality and attack resistance gate
python scripts/check_marketplaces.py                              # connectors on documented shapes and a simulated marketplace over HTTP
```

GitHub Actions: **CI and Build** runs the backend tests and builds the frontend on every push and pull request. **Test and deploy**
runs the tests, publishes the frontend to Cloudflare Pages, and Render redeploys the API from the same commit.

## Deployment

Frontend on Cloudflare Pages, API on Render (`render.yaml`), data on a persistent disk or Neon. To move an existing server to Postgres:
set the address in **Server -> Database**, **Copy my data**, restart. Step by step, with backups and a production checklist:
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Status and limitations

-   **Postgres** works and the whole suite passes on it, but the hosted API only uses it once `DATABASE_URL` (or a saved address) is set.
-   **Amazon and Flipkart** are tested against documented sample shapes and a simulated server over real HTTP, not against live accounts.
-   **Live agent evaluation** is one run of one model (Groq); Gemini was not measured because its free daily quota was used up.
-   **Connected shops are read-only:** shoppers buy on the shop itself. There is no payment gateway; the built-in checkout stops at the
    shopper's confirmation.
-   **Accounts:** owners have password reset (links), authenticator-app two-step sign-in and lockout after repeated wrong attempts; there
    is no SMS or hardware-key option, and the server admin is still a shared secret without two-step.
-   **Chat history** lives in the browser (the last six turns are sent); the server keeps no conversation.
-   **Prices and stock from other shops** appear in that shop's currency, and stock only when the shop reports it.
-   **Docker image builds** are not covered by CI.

## Contributing, security, license

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). To report a vulnerability,
see [SECURITY.md](SECURITY.md). Zaldi is released under the [MIT License](LICENSE). Built by
[shreyanshtri26](https://github.com/shreyanshtri26).
