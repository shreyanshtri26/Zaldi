# Zaldi

**An AI-powered shopping assistant and content management platform for
Indian ethnic fashion.**

Zaldi helps customers discover products, compare options, understand
store policies, and prepare purchases through a conversational
interface. It also includes a built-in CMS that allows store
administrators to manage products, policies, storefront content, and
assistant prompts without changing application code.

The platform is designed for an Indian ethnic-fashion storefront,
including categories such as sarees, kurtas, lehengas, sherwanis,
footwear, and jewellery. It supports INR pricing and customer
conversations in English, Hindi, and Hinglish.

[![License:
MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Build-Vite-646CFF.svg)](https://vite.dev/)

------------------------------------------------------------------------

## Contents

-   [Overview](#overview)
-   [Key capabilities](#key-capabilities)
-   [Customer experience](#customer-experience)
-   [Admin CMS](#admin-cms)
-   [AI and product discovery](#ai-and-product-discovery)
-   [Cart and checkout workflow](#cart-and-checkout-workflow)
-   [Security and privacy](#security-and-privacy)
-   [Technology stack](#technology-stack)
-   [System architecture](#system-architecture)
-   [Design system](#design-system)
-   [Project structure](#project-structure)
-   [Getting started](#getting-started)
-   [Configuration](#configuration)
-   [Running in development](#running-in-development)
-   [Database](#database)
-   [API reference](#api-reference)
-   [Testing](#testing)
-   [Deployment](#deployment)
-   [Troubleshooting](#troubleshooting)
-   [Current limitations](#current-limitations)
-   [Contributing](#contributing)
-   [License](#license)

## Overview

Zaldi brings product discovery, shopping assistance, and storefront
content management into one application.

Customers can ask natural-language questions about products, prices,
sizes, availability, delivery, cash on delivery, UPI, returns, and GST
invoices. The assistant interprets the request, searches the product
catalogue, and presents relevant results in a conversational shopping
experience.

Store administrators can maintain the catalogue and customer-facing
content through the `/admin` workspace. Storefront messaging, quick
actions, brand styling, and assistant prompts are configurable through
the CMS, allowing the experience to evolve without requiring frontend or
backend code changes.

The application combines a React frontend with a Flask API, a structured
product database, hybrid product retrieval, and an optional
browser-automation checkout flow.

## Key capabilities

### Conversational shopping

-   Natural-language product discovery for ethnic-fashion categories.
-   Product information and pricing displayed in Indian rupees (INR).
-   Support for English, Hindi, and Hinglish customer conversations.
-   Product cards, suggested actions, cart panel, and chat history.
-   Photo-based product discovery where image input is available.
-   Browser voice input on supported browsers.
-   Assistant activity states for listening, thinking, responding, and
    offline conditions.

### Store administration

-   Dedicated admin workspace at `/admin`.
-   Product and policy management.
-   Dashboard overview and chat transcript views.
-   Storefront content and brand configuration.
-   Editable assistant prompts and quick-action cards.
-   Search dialog accessible with `Ctrl+K`.
-   Light and dark themes.

### Product discovery

-   Natural-language query interpretation.
-   Structured filtering by budget, colour, size, category, brand, and
    gender.
-   SQL filtering combined with vector similarity and lexical relevance.
-   Saved shopper preferences incorporated into retrieval.
-   Controlled relaxation of filters when no exact match is found.

### Shopping workflow

-   Cart operations with stock checks.
-   Shipping and coupon calculations based on store policies.
-   Checkout preparation through Playwright browser automation.
-   A confirmation step before the checkout flow proceeds to payment.
-   A built-in demo storefront available at `/store-sim`.

### Tool-using agent and store connectors

-   For multi-step requests (for example "compare these and add the
    cheaper one"), the model chooses store tools step by step, up to
    `AGENT_MAX_STEPS` (default 5), then answers. Simple messages stay on
    the fast deterministic path, and if the model fails the normal
    pipeline answers.
-   Tools are built from what the connected store supports. The
    shopper's session is bound on the server and never visible to the
    model, tool errors are returned to the model so it can recover, and
    checkout still ends at the secure form and a human confirmation.
-   The tools used are shown under each answer and saved with the chat
    log, so the admin transcript shows what really happened.
-   Policy answers come from per-section chunks that carry the section
    title (the citation), ranked by vector similarity fused with keyword
    overlap.
-   The page sends the last six turns with each message as untrusted
    context (PII-redacted, injection-checked, quoted in one block).
    Lasting preferences such as size and budget are saved through a
    tool.
-   Stores are connected through `StoreConnector` classes in
    `zaldi/connectors/`, selected with `STORE_CONNECTOR`: `local` (this
    app's catalogue and cart), `woocommerce` and `shopify` (read-only
    search; each product card links to the store's own page, so no cart
    or payment data passes through Zaldi), or `escuelajs` (the free
    [Platzi Fake Store API](https://api.escuelajs.co/docs) demo catalogue,
    no key, catalogue only). Adding a platform means writing one class.
    The Platzi connector reads only the documented `GET /products` and
    `GET /categories` endpoints (cached for ten minutes), understands
    "cheapest" and "most expensive", and shows each product's image
    exactly as the API sends it (a real photo wins over a placeholder box,
    and a dead image link falls back to a fabric tile). Its write
    endpoints are never used. The API is an open sandbox that anyone can
    write to, so its data can include junk such as odd category names:
    hide those under Admin -> Content -> Storefront -> Hidden categories.
-   Product answers end with a short comparison ("Lowest price", "Top
    rated" when the store has ratings) and tappable follow-ups such as
    "Cheapest jewelery".
    Amazon and Flipkart offer only affiliate catalogue APIs, so they
    would be catalogue-and-link connectors; they are not built yet.
-   The assistant asks for what it needs. A vague request ("suggest
    something") gets a question with tappable category answers; the
    agent can ask mid-run with its `ask_shopper` tool (up to four
    tappable options); and at checkout it lists exactly what the secure
    form wants (name, mobile, address, city, state, PIN code, delivery
    speed) and opens the form. Those details never go through the chat
    or the model.
-   Admin -> Content -> **Store connection** lets staff pick the store
    and enter its address and keys without editing `.env`, with a Test
    connection button. Secrets are write-only (never sent back to the
    browser) and are stored in the app database, so production
    deployments should prefer environment variables. Changes apply to the
    next customer message.
-   The admin link in the chat navbar appears only while an admin is
    signed in; visitors do not see it.
-   Product images appear on the cards in replies (larger when there is a
    single result). The built-in catalogue ships without photos: open
    Admin -> Products -> Edit and use **Upload a photo** (JPEG, PNG or
    WebP, up to 3 MB; checked by content, never SVG) or paste an image
    link. Uploads are saved under `DATA_DIR/uploads`, which is on the same
    persistent volume as the database.
-   The home page's "Shop by category" opens every category, grouped by
    department (Women, Men, Kids, Everyone). A category whose products
    mix genders belongs to Everyone; the number shown is set under Admin
    -> Content -> Storefront (default 24, up to 60), and any category can
    be hidden there.
-   Scripted-model evals (`tests/test_agent_loop.py`,
    `tests/test_agent_evals.py`, `tests/test_connectors.py`) and a
    retrieval test set run offline in CI.

Embed the assistant on another site with one tag; it opens in an
isolated frame and never reads the host page's data:

``` html
<script src="https://YOUR-ZALDI-HOST/widget.js" async></script>
```

## Customer experience

The chat interface is designed to keep product discovery simple and
focused.

-   A graphite top bar provides access to new conversations, history,
    assistant settings, the cart, and apps.
-   The Zaldi orb provides a visual indication of the assistant's
    current activity.
-   Suggested prompts help customers get started.
-   Product cards make relevant catalogue results easier to browse.
-   The cart panel provides access to selected items.
-   The composer supports text, photo search, and browser-based voice
    input where supported.
-   A response status panel can show the assistant's current plan while
    a reply is being prepared.

The interface uses English for its controls and navigation, while
assistant responses can follow the customer's language.

## Admin CMS

The CMS is available at `/admin` and is intended for store staff
managing the storefront.

### Catalogue and policy management

Administrators can create, review, update, and remove products and store
policies. Product management includes table and grid views, category
filters, sorting, and a slide-over editor.

### Storefront content

Under **Admin → Content**, administrators can manage customer-facing
content, including:

-   Welcome greeting and main heading.
-   Supporting storefront text.
-   Brand name and tagline.
-   Brand colour palette.
-   Quick-action cards shown on the empty chat screen.
-   Assistant prompts.

Text in the main heading can be wrapped in asterisks to apply the
configured highlight treatment.

### Defaults and reset behaviour

The application starts with built-in default values. Clearing an
editable value or choosing **Reset to default** restores its built-in
value. Prompt changes are applied to the next customer message.

## AI and product discovery

Zaldi uses a staged request pipeline so that customer intent is
interpreted and handled before the final response is generated.

### Request processing

1.  **Guardrails:** validate and screen the incoming message.
2.  **Optional image analysis:** process an attached product image when
    image input is provided.
3.  **Intent routing:** classify the request into a supported route,
    such as product search, cart, checkout, or general conversation.
4.  **Entity extraction:** identify relevant product attributes and
    constraints.
5.  **Product retrieval:** apply structured database filters and hybrid
    ranking.
6.  **Action handling:** invoke the relevant cart or checkout service
    when required.
7.  **Response generation:** prepare the customer-facing explanation.

The LLM is primarily responsible for interpreting language and wording
the final response. Core shopping operations are handled by application
services so they can be validated and tested independently.

### Hybrid search

Product discovery combines structured filtering with relevance ranking:

-   Natural-language requests are converted into structured attributes.
-   SQL filters enforce applicable constraints such as budget, size,
    colour, category, brand, and gender.
-   FAISS vector similarity helps retrieve semantically relevant
    products.
-   Lexical matching contributes exact-term relevance.
-   Reciprocal Rank Fusion (RRF) combines ranking signals.

Saved shopper preferences can be added to the search context. If the
initial search produces no suitable results, selected soft filters may
be relaxed, and the assistant communicates that adjustment to the
customer.

### Embeddings and model providers

Gemini is the default model provider for the configured AI workflow. An
offline hashing-based embedding option is available when
`EMBEDDING_PROVIDER=local` is configured or when `GOOGLE_API_KEY` is
unavailable. The local option supports basic word-level matching and is
intended as a fallback rather than a replacement for semantic
embeddings.

The chat model provider can be configured independently using the
environment variables described below.

## Cart and checkout workflow

The shopping flow separates cart preparation from checkout confirmation.

1.  Products are added to the cart and checked against available stock.
2.  Shipping and coupon pricing are calculated using configured store
    policies.
3.  The checkout service prepares the required steps using Playwright.
4.  The browser automation fills the checkout form in the configured
    storefront.
5.  The flow pauses and requests customer confirmation before payment.

The default automation target is the built-in demo storefront at
`/store-sim`. A different storefront can be configured with
`STOREFRONT_URL`.

Customer addresses are entered through a form rather than sent as chat
content to the LLM. Zaldi does not collect or process card or UPI
payment credentials as part of this workflow. Confirmation uses a
signed, expiring, single-use token.

## Security and privacy

Security checks are applied at multiple points in the request lifecycle.

-   Personally identifiable information (PII), including phone numbers,
    email addresses, Aadhaar, PAN, card, and UPI details, is redacted
    before LLM requests and from application logs.
-   Prompt-injection attempts are rejected before model execution.
-   Generated responses are checked for PII and system-prompt
    disclosure.
-   Checkout automation pauses for explicit customer confirmation before
    payment.
-   Admin write operations are protected by the configured
    `ADMIN_TOKEN`.

For production use, deploy behind HTTPS and configure a long, randomly
generated admin token. The current admin authentication model uses one
shared token; see [Current limitations](#current-limitations).

## Technology stack

  -----------------------------------------------------------------------
  Area                                Technologies
  ----------------------------------- -----------------------------------
  Frontend                            React, Vite, JavaScript, CSS

  Backend                             Python, Flask, Gunicorn

  AI orchestration                    LangChain components, configurable
                                      LLM provider, Gemini embeddings

  Product retrieval                   SQL, FAISS, lexical matching,
                                      Reciprocal Rank Fusion

  Database                            SQLite

  Browser automation                  Playwright, headless Chromium

  Motion and visual effects           Lenis, CSS animations, WebGL shader
                                      with CSS fallback

  Testing                             pytest, frontend production build

  Deployment                          Docker, Docker Compose
  -----------------------------------------------------------------------

## System architecture

The application is divided into a React client, a Flask API, and backend
services for AI routing, search, cart operations, checkout automation,
and persistence.

``` text
                         Customer
                            |
                            v
                    React + Vite UI
                            |
                         /api
                            |
                            v
                       Flask API
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
        Chat service    Cart service   Checkout service
             |                             |
             v                             v
        AI guardrails                 Handshake / token
             |                             |
       +-----+------+                      v
       |            |                Playwright
       v            v                      |
   Image vision  Intent router             v
                    |                  Storefront
          +---------+---------+          /store-sim
          |         |         |
          v         v         v
       Product    Cart     General
       search    actions  conversation
          |
          v
    SQL filters + FAISS
          |
          v
     Product database
```

The Flask application exposes the API and serves the built frontend in
production. The backend package separates HTTP endpoints, business
services, AI components, and database repositories.

## Design system

Zaldi uses an **Obsidian Black × Electric Lime** visual direction, with
a dark theme by default and a corresponding light theme.

  Design role          Colour          Hex
  -------------------- --------------- -----------
  Primary background   Black           `#090B0A`
  Accent               Electric Lime   `#C1F75A`
  Secondary surface    Graphite        `#202622`
  Supporting accent    Leaf Green      `#79B83D`
  Neutral              Silver          `#D8DED8`

The five base colours can be changed in **Admin → Content →
Storefront**. Other interface colours are derived from these design
tokens, including surfaces, borders, text, and focus treatments. Status
colours remain theme-specific.

Additional design details:

-   **Typography:** Inter.
-   **Icons:** a shared, custom SVG icon family.
-   **Motion:** Lenis-powered smooth scrolling and CSS animations.
-   **Reduced motion:** the orb and smoke effects respect
    `prefers-reduced-motion`.
-   **Visual effects:** the orb smoke uses a lightweight WebGL shader
    with a CSS fallback.

Design tokens are maintained in `frontend/src/styles/tokens.css`.

## Project structure

``` text
Zaldi/
├── wsgi.py
├── pyproject.toml
├── requirements.txt
├── zaldi/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── admin.py
│   │   ├── site.py
│   │   ├── content.py
│   │   ├── errors.py
│   │   └── frontend.py
│   ├── services/
│   │   ├── chat_service.py
│   │   ├── site_config.py
│   │   └── prompt_service.py
│   ├── ai/
│   │   ├── models.py
│   │   ├── prompts.py
│   │   ├── router.py
│   │   ├── route_samples.py
│   │   ├── agent.py
│   │   ├── chitchat.py
│   │   └── tools/
│   └── db/
│       ├── connection.py
│       ├── schema.sql
│       ├── seed.py
│       ├── content_repo.py
│       ├── override_repo.py
│       └── chat_log_repo.py
├── frontend/
│   └── src/
│       ├── api/
│       ├── features/
│       │   ├── chat/
│       │   └── admin/
│       ├── shared/
│       └── styles/
├── data/
│   └── seed/
├── scripts/
├── tests/
└── docs/
```

### Backend responsibilities

  -----------------------------------------------------------------------
  Module                              Responsibility
  ----------------------------------- -----------------------------------
  `zaldi/api/`                        HTTP routes, request handling,
                                      authentication, and frontend
                                      serving

  `zaldi/services/`                   Chat orchestration, storefront
                                      configuration, and prompt
                                      management

  `zaldi/ai/`                         Model setup, prompts, intent
                                      routing, agents, and AI tools

  `zaldi/db/`                         Database connection, schema, seed
                                      data, and repository operations

  `frontend/src/features/chat/`       Customer chat experience and chat
                                      state

  `frontend/src/features/admin/`      Admin dashboard, catalogue,
                                      policies, and CMS editors

  `frontend/src/shared/`              Shared UI components, context, and
                                      utilities

  `frontend/src/styles/`              Design tokens and interface styles

  `tests/`                            API, AI, and live integration tests
  -----------------------------------------------------------------------

### Naming conventions

-   **Python:** `snake_case` for modules, functions, and variables;
    `PascalCase` for classes; `UPPER_CASE` for constants.
-   **React:** `PascalCase.jsx` for components and pages; `useThing.js`
    for hooks.
-   **Frontend utilities:** lowercase `.js` files.
-   **Styles:** separate CSS files by concern, with shared variables in
    `tokens.css`.
-   **Tests:** organised to mirror the backend package. Tests requiring
    real provider calls use the `live` marker.

## Getting started

### Prerequisites

-   Python 3.10 or later.
-   Node.js 18 or later.
-   npm.
-   A Google AI API key for the default Gemini-backed workflow. Local
    embedding fallback is available for offline development.

### 1. Clone the repository

``` bash
git clone <repository-url>
cd Zaldi
```

Replace `<repository-url>` with the repository's clone URL.

### 2. Create and activate a Python virtual environment

``` bash
python -m venv venv
```

**Windows (PowerShell):**

``` powershell
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

``` bash
source venv/bin/activate
```

### 3. Install backend dependencies

``` bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local environment file:

``` bash
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` using your preferred terminal
or editor. Add the required configuration values before starting the
application.

### 5. Install and build the frontend

``` bash
cd frontend
npm install
npm run build
cd ..
```

### 6. Start the application

``` bash
python wsgi.py
```

Open the application at:

-   **Storefront:** http://127.0.0.1:5000
-   **Admin CMS:** http://127.0.0.1:5000/admin

## Configuration

Zaldi reads its runtime configuration from environment variables. Keep
secrets in `.env` for local development and do not commit that file.

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `GOOGLE_API_KEY`                    Enables the Gemini-backed model and
                                      embedding workflow.

  `GROQ_API_KEY`                      Required when `LLM_PROVIDER=groq`.

  `ADMIN_TOKEN`                       Shared token used to protect admin
                                      operations. Write endpoints return
                                      `503` when it is not configured.

  `LLM_PROVIDER`                      Selects the chat model provider.
                                      Defaults to `google`.

  `LLM_MODEL`                         Selects the chat model. The
                                      documented default is
                                      `gemini-3.5-flash`.

  `EMBEDDING_PROVIDER`                Selects the embedding
                                      implementation; `local` enables the
                                      offline hashing embedder.

  `EMBEDDING_MODEL`                   Embedding model identifier. The
                                      documented default is
                                      `models/gemini-embedding-001`.

  `STOREFRONT_URL`                    Optional URL for the storefront
                                      used by checkout automation.
                                      Defaults to the built-in demo
                                      storefront.

  `STORE_CONNECTOR`                   `local` (default), `woocommerce`,
                                      `shopify` or `escuelajs`. Per-store
                                      settings: `WOOCOMMERCE_URL`,
                                      `WOOCOMMERCE_KEY`,
                                      `WOOCOMMERCE_SECRET`,
                                      `SHOPIFY_DOMAIN`,
                                      `SHOPIFY_STOREFRONT_TOKEN`,
                                      `SHOPIFY_API_VERSION`,
                                      `ESCUELAJS_URL`.

  `AGENT_ENABLED`                     Turns the tool-using agent on
                                      (default) or off (`0`).

  `AGENT_MAX_STEPS`                   Tool rounds per answer. Default 5.

  `AGENT_DAILY_RUNS`                  Agent runs per day per server
                                      process (cost cap). Default 500;
                                      `0` means unlimited.

  `LLM_FALLBACK_PROVIDER`,            Optional second model used when the
  `LLM_FALLBACK_MODEL`                first fails, for example `groq` and
                                      `openai/gpt-oss-120b`.
  -----------------------------------------------------------------------

Example configuration:

``` dotenv
GOOGLE_API_KEY=your_google_api_key
ADMIN_TOKEN=replace_with_a_long_random_secret

LLM_PROVIDER=google
LLM_MODEL=gemini-3.5-flash
EMBEDDING_MODEL=models/gemini-embedding-001
```

If using Groq for chat, configure `GROQ_API_KEY` and set
`LLM_PROVIDER=groq`. For example, the project documentation references
`openai/gpt-oss-120b` as a possible `LLM_MODEL` value.

Do not put real credentials in source control, screenshots, issue
reports, or chat transcripts.

## Running in development

For frontend and backend hot-reload workflows, run the API and Vite
development server in separate terminals.

**Terminal 1 --- Flask API:**

``` bash
# Activate the virtual environment first
python wsgi.py
```

The API runs on port `5000`.

**Terminal 2 --- Vite frontend:**

``` bash
cd frontend
npm install
npm run dev
```

The frontend development server runs on port `5173` and proxies `/api`
requests to the Flask server on port `5000`.

### Terminal chat

A command-line chat interface is also available:

``` bash
python -m zaldi
```

Run Python commands from the activated virtual environment so the
installed project dependencies are available.

### Rebuild the product index

After product data changes, rebuild the vector index with:

``` bash
python -m zaldi ingest
```

The index is also rebuilt automatically when the application detects
product changes.

## Database

The application uses SQLite. The database is created on first run at
`data/zaldi.db`.

  -----------------------------------------------------------------------
  Table                               Purpose
  ----------------------------------- -----------------------------------
  `products`                          Product catalogue, attributes,
                                      stock, INR price, and image URL

  `policies`                          Store policies and their content

  `chat_logs`                         Customer queries, assistant
                                      responses, route, and timestamp

  `quick_actions`                     Configurable suggestion cards for
                                      the chat interface

  `settings`                          Storefront setting overrides

  `prompts`                           Assistant prompt overrides
  -----------------------------------------------------------------------

### Product data

The `products` table includes fields such as product code, name,
category, material, size, colour, brand, gender, stock quantity, price,
description, image URL, and update timestamp. Product codes are unique;
stock and price values are constrained to non-negative values. Prices
are stored in INR and are documented as GST-inclusive.

### Initial seed data

On first run, the application seeds the database from files in
`data/seed/`, including the product catalogue and policy content. After
initial setup, the database is the source of truth for managed content.

To recreate the initial seeded database, stop the application and remove
`data/zaldi.db`. The next application start will initialise and seed the
database again. **This deletes locally stored catalogue, policy, and
application data**, so back up the database first if it contains changes
you need to retain.

## API reference

The following routes are exposed by the Flask application.

  -----------------------------------------------------------------------------------
  Method            Endpoint                      Access            Description
  ----------------- ----------------------------- ----------------- -----------------
  `POST`            `/api/chat`                   Public            Submit a customer
                                                                    message and
                                                                    receive an
                                                                    assistant
                                                                    response.

  `GET`             `/api/site-config`            Public            Retrieve
                                                                    storefront text
                                                                    and active quick
                                                                    actions.

  `GET`             `/api/products`               Public            List or search
                                                                    products;
                                                                    supports `q` and
                                                                    `category` query
                                                                    parameters.

  `GET`             `/api/products/<id>`          Public            Retrieve a
                                                                    product.

  `GET`             `/api/policies`               Public            List store
                                                                    policies.

  `GET`             `/api/policies/<id>`          Public            Retrieve a
                                                                    policy.

  `POST`, `PUT`,    `/api/products` and           Admin             Create, update,
  `DELETE`          `/api/products/<id>`                            or delete
                                                                    products.

  `POST`, `PUT`,    `/api/policies` and           Admin             Create, update,
  `DELETE`          `/api/policies/<id>`                            or delete
                                                                    policies.

  `POST`, `PUT`,    `/api/quick_actions` and      Admin             Manage
  `DELETE`          `/api/quick_actions/<id>`                       quick-action
                                                                    cards.

  `POST`            `/api/admin/login`            Admin             Verify the admin
                                                                    token.

  `GET`             `/api/admin/stats`            Admin             Retrieve
                                                                    dashboard
                                                                    statistics.

  `GET`, `PUT`      `/api/admin/settings`         Admin             Read or update
                                                                    storefront
                                                                    settings.

  `GET`             `/api/admin/prompts`          Admin             List assistant
                                                                    prompts.

  `PUT`, `DELETE`   `/api/admin/prompts/<name>`   Admin             Update or reset
                                                                    an assistant
                                                                    prompt.
  -----------------------------------------------------------------------------------

Admin endpoints use the `X-Admin-Token` request header. The exact
request and response schemas should be checked in the corresponding
route implementation.

## Testing

Run the offline test suite:

``` bash
python -m pytest -m "not live"
```

Run tests that make real AI provider calls:

``` bash
python -m pytest -m live
```

The offline suite covers application functionality such as API
behaviour, CMS operations, SQL safeguards, and frontend serving. Live
tests require valid provider credentials and available API quota.

Live tests may be skipped when the required Google API key is
unavailable. Provider rate limits can also affect tests that make real
model requests. Run live tests selectively to avoid unnecessary quota
consumption.

The CI workflow in `.github/workflows/ci.yml` runs offline tests and
builds the frontend. The repository does not currently define a
deployment step in CI.

## Deployment

The project includes a Docker Compose setup.

``` bash
docker compose up --build
```

Before starting:

1.  Create and configure `.env` using `.env.example` as a reference.
2.  Set a strong `ADMIN_TOKEN`.
3.  Configure the required model-provider credentials.
4.  Review the storefront URL and checkout settings for the target
    environment.

The Docker image is configured to bundle the built frontend, Gunicorn,
and headless Chromium. Application data is stored in a named Docker
volume.

**Deployment note:** the Docker image build has not been verified by the
repository's CI workflow. Validate the image and checkout automation in
a staging environment before relying on this deployment path in
production.

## Troubleshooting

  -----------------------------------------------------------------------------------------------------
  Problem                                  Likely cause            Suggested action
  ---------------------------------------- ----------------------- ------------------------------------
  The UI reports that the backend is       The Vite frontend       Start the Flask server with
  unavailable or a request returns `500`.  cannot reach Flask.     `python wsgi.py` and confirm it is
                                                                   listening on port `5000`.

  `No module named 'langchain_classic'`.   Flask is running with a Activate the project virtual
                                           Python interpreter that environment and run
                                           does not have the       `pip install -r requirements.txt`.
                                           project dependencies    
                                           installed.              

  The assistant reports that it is busy.   The model provider may  Check the server logs, wait for
                                           have rejected the       quota recovery, or configure another
                                           request because of rate supported chat provider.
                                           limits, quota, or       
                                           temporary availability. 

  The development UI shows outdated styles The development server  Stop and restart `npm run dev`.
  or components.                           may not have detected   
                                           file changes,           
                                           particularly when the   
                                           repository is stored in 
                                           a synchronised folder.  

  Product results are not up to date after The product vector      Run `python -m zaldi ingest`.
  catalogue changes.                       index may need          
                                           rebuilding.             
  -----------------------------------------------------------------------------------------------------

The application includes fallback behaviour for some provider failures.
Product and policy requests may still return plain-text responses when
model generation is unavailable.

## Current limitations

-   **Chat persistence:** the API keeps no conversation. Chat history is
    stored in the browser, which sends the last six turns with each
    message; only preferences and the cart are stored per session.
-   **One store per server:** `STORE_CONNECTOR` is global, so serving
    several stores currently means one deployment each. Connected stores
    are read-only: shoppers buy on the store itself.
-   **Prices and stock from other stores:** a connected store's prices
    are shown in its own currency, and stock is shown only when the
    store reports it (the Platzi demo API does not, and it gives no currency, so USD is assumed).
-   **Admin authentication:** the current implementation uses one shared
    admin token rather than individual administrator accounts and
    role-based access.
-   **Embedding provider:** the configured embedding implementation is
    independent of the chat provider. Switching chat to Groq does not
    automatically switch embeddings away from Google.
-   **Live AI tests:** tests that call external model providers depend
    on credentials, quota, and provider availability.
-   **Deployment verification:** the Docker image build is not currently
    covered by a verified CI deployment pipeline.

## Contributing

Contributions and improvements are welcome.

1.  Create a branch for your change.
2.  Keep backend modules, frontend features, and shared components
    within their existing areas.
3.  Add or update tests for behaviour changes.
4.  Run the offline test suite and build the frontend before submitting
    a pull request.
5.  Document any new environment variables or setup requirements.

Please avoid committing `.env` files, API keys, generated databases,
local indexes, or other runtime secrets and data.

## License

This project is licensed under the [MIT
License](https://opensource.org/licenses/MIT).

------------------------------------------------------------------------

Built by [shreyanshtri26](https://github.com/shreyanshtri26).
