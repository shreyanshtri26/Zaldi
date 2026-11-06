# API reference

Base path `/api`. JSON in and out. Errors are `{"error": "message"}` with a 4xx/5xx status; a 400 message is safe to show a person.

**Headers**

| Header | Used for |
|---|---|
| `X-Session-Id` | A UUID the browser creates. Required for shopper routes (chat, cart, preferences, checkout) |
| `X-Store` | The shop's id. Optional; no header means the default store. Unknown ids are refused |
| `X-Admin-Token` | Admin routes: an account's sign-in token, or the server admin's token/password |

## Shopper routes (public, per session)

| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/chat` | `{message, history?, page?}` or multipart `message` + `image` | `{response, type, products, steps, quick_replies?, cart?, action?, chat_id}` |
| POST | `/chat/stream` | `{message, history?, page?}` | Server-sent events: `step` (`{tool, summary, ok, ms}`) as each tool finishes, then `done` (same as `/chat`) or `error` |
| POST | `/feedback` | `{chat_id, rating: 1\|-1}` | `{ok: true}`. One rating per answer; the latest wins |
| GET | `/site-config` | | Storefront text and active quick actions |
| GET | `/categories` | | Categories of the connected store |
| GET | `/products`, `/products/<id>` | `q`, `category` | Products of the built-in store |
| GET | `/policies`, `/policies/<id>` | | Policies |
| GET | `/cart` | | The cart |
| POST | `/cart/items` | `{product_id, quantity}` | The cart |
| PUT/DELETE | `/cart/items/<id>` | `{quantity}` | The cart |
| POST | `/cart/coupon` | `{code}` | The cart |
| GET/PUT | `/preferences` | `{size, max_price, gender, brand}` | Saved preferences |
| POST | `/checkout/prepare` | `{address, method}` | A confirmation token and totals (nothing is ordered) |
| POST | `/checkout/confirm`, `/checkout/cancel` | `{token}` | The order, or its cancellation |
| GET | `/health` | | `{"status": "ok"}` |

## Sign-in (public)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/admin/account-login` | `{email, password}` | `{token, email, store, role}` |
| POST | `/signup` | `{email, password, store, name}` | `{account, token, store}`. Works only when `ALLOW_SIGNUP=1` |

## Store admin routes (`X-Admin-Token` and `X-Store`; owners change, viewers read)

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/login` | Check a token |
| GET | `/admin/stats` | Counts and recent chats |
| GET | `/admin/metrics?days=7` | Latency, tokens, cost, tool health, answer checks, feedback by prompt version |
| GET/PUT | `/admin/settings` | Storefront settings (including `embed_origins`) |
| GET | `/admin/prompts` | The assistant's prompts |
| PUT/DELETE | `/admin/prompts/<name>` | Edit or reset a prompt (`agent_system`, `agent_system_b`, `chitchat`) |
| GET/PUT/DELETE | `/admin/store` | The store connection (secrets write-only) |
| POST | `/admin/store/test` | The Test checklist: `{ok, store, level, found, sample, checks[]}` |
| GET | `/admin/embed` | `{store, host, allowed_origins, snippet, ready}` |
| POST/PUT/DELETE | `/products`, `/policies`, `/quick_actions` (`/<id>`) | Manage content |
| POST | `/admin/upload` | Upload a product photo |
| PUT | `/admin/account/password` | `{current, new}`: change your own account password |

### AI settings

| Method | Path | Body / query | Purpose |
|---|---|---|---|
| GET | `/admin/ai-key` | | `{provider, provider_is_default, providers: {google, groq}}`; each has `source` (`store`/`server`/`none`), `own_key_set`, `own_key_hint`, `model`, `model_is_default`, `default_model`. Never a key |
| PUT | `/admin/ai-key` | `{provider, api_key}` | Save the store's own key (format-checked, stored encrypted) |
| DELETE | `/admin/ai-key?provider=` | | Remove it |
| POST | `/admin/ai-key/test` | `{provider?}` | `{ok, state: working\|quota\|invalid\|error\|none, message}` |
| GET | `/admin/ai-models?provider=` | | `{live, models: [{id, label}], selected, default, is_default}`: the provider's current chat models, newest first |
| PUT/DELETE | `/admin/ai-model` | `{provider, model}` / `?provider=` | Pick or reset the model |
| PUT/DELETE | `/admin/ai-provider` | `{provider}` | Pick or reset the provider for chats |

### Agent Studio

`GET/POST /admin/agents`, `GET/DELETE /admin/agents/<id>`, `POST /admin/agents/<id>/test`, `POST /admin/agents/<id>/duplicate`,
`GET /admin/runs`, `GET/POST /admin/approvals`, `POST /admin/approvals/<id>/<action>`. A proposed policy change is only written after an
owner approves it.

## Server admin routes (the server admin only; owners get 403)

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET/POST | `/admin/stores` | `{slug, name}` | List or create stores |
| PUT/DELETE | `/admin/stores/<id>` | `{status: draft\|live}` | Change status or delete (drops the store's data) |
| GET/POST | `/admin/stores/<id>/accounts` | `{email, password, role}` | List or create owner/viewer accounts |
| GET | `/admin/server` | | `{admin_password: {source, environment_token_set, min_length}, database: {backend, host, database, schema, source, saved_in_portal, saved, restart_needed, environment_overrides}}` |
| PUT/DELETE | `/admin/server/password` | `{current, new}` / `{current}` | Set or remove the portal admin password (the current credential is required) |
| POST | `/admin/server/database/test` | `{url}` | `{ok, state, message, version, has_data, host, database}`; the address is never echoed |
| PUT/DELETE | `/admin/server/database` | `{url}` | Save (only if it connects) or remove the address used after a restart |
| POST | `/admin/server/database/copy` | `{url, replace?, confirm?}` | Copy this server's data into that database in a separate process. `replace` needs `confirm: "REPLACE"` |
| POST | `/admin/server/restart` | `{confirm: "RESTART"}` | `202`, then the server restarts |

## Other

-   `GET /uploads/<name>`: product photos.
-   `/store-sim/*`: the demo storefront the checkout automation drives.
-   Rate limits: chat and sign-in are limited per visitor per minute (`RATE_LIMIT_CHAT`, `RATE_LIMIT_LOGIN`).
