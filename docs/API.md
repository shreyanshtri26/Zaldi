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
| POST | `/admin/account-login` | `{email, password}` | `{token, email, store, role}`, or `{needs_two_step: true, challenge}` when the account has two-step sign-in on |
| POST | `/admin/account-login/two-step` | `{challenge, code}` | `{token, email, store, role}`. The code is 6 digits from the app, or a recovery code; each works once. The challenge lasts 5 minutes |
| POST | `/admin/forgot-password` | `{email}` | `{ok, email_enabled}`. Always the same answer; an email is sent only if the account exists and the server can send email |
| POST | `/admin/password-reset` | `{token, new}` | `{ok, email}`. The token comes from a reset link; it works once, for one hour |
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
| PUT | `/admin/account/password` | `{current, new}`: change your own password. Returns `{ok, token}`: a fresh token, because every other session of the account ends |
| GET | `/admin/account/two-step` | `{enabled, recovery_codes_left}` |
| POST | `/admin/account/two-step/setup` | `{password}`: returns `{secret, uri}` (not active yet) |
| POST | `/admin/account/two-step/enable` | `{code}`: turns it on, returns `{recovery_codes: [8 codes]}` once |
| POST | `/admin/account/two-step/disable` | `{password, code}`: turns it off; returns a fresh token |

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
| PUT | `/admin/stores/<id>` | `{status: draft\|live}` | Change status |
| DELETE | `/admin/stores/<id>` | `{confirm: "<id>"}` | Delete the store and all its data. The id must be repeated in `confirm` |
| GET/POST | `/admin/stores/<id>/accounts` | `{email, password, role}` | List (with `role` and `two_step`) or create owner/viewer accounts |
| PUT | `/admin/stores/<id>/accounts/<email>` | `{role}` | Change a role; the account's sessions end |
| DELETE | `/admin/stores/<id>/accounts/<email>` | | Delete an account; its sessions end |
| POST | `/admin/stores/<id>/accounts/<email>/reset-link` | | `{link, expires_in}`: a one-hour, single-use password reset link to give to the person |
| POST | `/admin/stores/<id>/accounts/<email>/two-step/disable` | | Turn two-step off for an account (a lost phone) |
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
