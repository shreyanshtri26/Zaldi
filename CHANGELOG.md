# Changelog

All notable changes to Zaldi. The project follows the spirit of [Keep a Changelog](https://keepachangelog.com); there are no tagged
releases yet, so changes are grouped by theme, newest first.

## Unreleased

### Added
-   **Stores page in the portal (server admin):** create, delete (typing the id) and set draft/live; manage each store's accounts: add,
    change role, delete, make a one-time **reset link**, turn off two-step.
-   **Password reset:** signed, single-use, one-hour links; owners can ask for one by email when `SMTP_*` is set, otherwise the server admin
    makes one. Sessions end when a password is reset or changed.
-   **Two-step sign-in** for owner and viewer accounts (authenticator-app codes, one-time recovery codes, replay protection) and a lock after
    five wrong attempts in ten minutes.
-   **AI settings per store (Admin -> Content -> AI model):** choose Gemini or Groq, use your own API key (encrypted, write-only, with a
    Test key button) and pick the model from a dropdown fed by the provider's own current model list. Photo search keeps using Gemini.
-   **Server settings (Admin -> Server, server admin only):** set the admin password from the portal (the environment `ADMIN_TOKEN` stays
    as a recovery key); test a Postgres address, copy this server's data into it (with an explicit, typed *replace*), save it for the next
    restart, and restart the server.
-   **Account password change** for store owners and viewers.
-   **`python -m zaldi migrate [--replace]`:** copy SQLite data into Postgres (all stores, ids kept).
-   **Live tool steps in the chat page:** answers stream, and the waiting box lists each step as it finishes.
-   **Postgres on Neon** with pgvector search, one schema per store, pooled connections; the whole test suite runs on it
    (`ZALDI_TEST_DATABASE_URL`).
-   **Embed on any website:** widget with a store id, allowed websites per store (`frame-ancestors`), page context for the agent, and
    `add-to-cart`/`ready` events to the host page.
-   **Connectors:** product feed, custom API (field mapping), product page links, Amazon (Creators API) and Flipkart (Affiliate API), a shared
    contract test, capability levels, the Test checklist, and a script to check marketplaces with real keys.
-   **Several stores per server** with owner and viewer accounts and an opt-in "Create a store" sign-up.
-   **Quality loop:** evaluation suites (search, attacks, live agent), answer self-check, parallel read-only tools, model routing and
    retries, orders and returns with confirmation, audit log, metrics, thumbs feedback, prompt A/B experiment, streaming endpoint.
-   Documentation set under `docs/`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`.

### Changed
-   The README is rewritten around the product and architecture; detail moved into `docs/`.
-   The agent's first live evaluation: tool choice 100% and faithfulness 100% on 30 cases (`openai/gpt-oss-120b`); see
    [docs/EVALUATION.md](docs/EVALUATION.md) for the caveats.

### Fixed
-   Saving partial evaluation results no longer erases the other suites' results.
-   The model dropdown now shows the saved choice after it is changed.

## Earlier work

-   Black x Electric Lime design system, 3D orb with WebGL smoke, Lenis smooth scrolling.
-   Tool-using agent with store connectors (built-in, WooCommerce, Shopify, Platzi demo), `ask_shopper`, preference memory, checkout details prompt.
-   Product photo upload and bulk import, home categories, product cards with a quantity stepper.
-   Admin CMS: products, policies, storefront content, quick actions, prompts, chats.
-   Hybrid product search (SQL filters, vectors, keywords, RRF), policy retrieval with section citations, guardrails, PII redaction.
-   Cart, coupons, and a Playwright checkout that stops for the shopper's confirmation.
