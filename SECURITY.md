# Security

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private vulnerability reporting on this repository
(Security tab -> "Report a vulnerability"), or contact the maintainer, [shreyanshtri26](https://github.com/shreyanshtri26), privately.
Include what you found, how to reproduce it, and what you think the impact is. You will get an answer as soon as the maintainer can; please
allow a reasonable time to fix before disclosing.

Supported version: the `main` branch.

## What Zaldi protects, and how

| Risk | Defence |
|---|---|
| A shopper's personal data reaching a model or a log | Phone, email, Aadhaar, PAN, card and UPI patterns are removed before any model call and from logs; replies are scrubbed too |
| Prompt injection from a shopper | Pattern-based refusal before the model runs |
| Prompt injection hidden in store data (descriptions, reviews, policies) | Tool results are scanned and instruction-like text is replaced with a notice before the model reads it |
| The model being talked into an action | Limits are in code: only products the shopper was shown can be added, quantities are bounded, no tool takes a session id, returns and checkout need the shopper's own confirmation (a signed, expiring, single-use token bound to the session) |
| One shopper reaching another's data | The session is bound on the server and never visible to the model |
| One shop reaching another's data | A separate database folder or schema per shop, selected by context, not by a filter that could be forgotten |
| Stolen or guessed admin access | Hashed owner passwords (scrypt), signed 12-hour tokens tied to one store and role, rate-limited sign-in, one vague "wrong email or password" answer; the server admin must give the current password to change it |
| Admin credentials locking the owner out | The environment `ADMIN_TOKEN` always works as a recovery key |
| Secrets leaking through the portal or API | Keys are write-only: only "set" and the last four characters are ever returned. AI keys are encrypted at rest (Fernet derived from `SECRET_KEY`); the saved database address is encrypted in `bootstrap.json` |
| The portal being used to reach the server's own network (SSRF) | Store and feed addresses must be public http(s) links; private, loopback and link-local addresses are refused; so are private database hosts |
| Another site framing the assistant | A per-store `frame-ancestors` header allows only the websites the owner listed |
| A hostile website talking to the widget | The widget accepts messages only from its own frame and posts only to the Zaldi host |
| Malicious uploads | Photos are checked by content (JPEG/PNG/WebP, size-limited), never SVG, with random names |
| Cost abuse | Per-visitor rate limits, a daily agent-run cap, retries with backoff |

## Things to do when you deploy

-   Use HTTPS. Set long random `ADMIN_TOKEN` and `SECRET_KEY`, and **do not change `SECRET_KEY` afterwards** (saved keys would become unreadable).
-   Prefer environment variables for server-wide secrets; the portal stores per-store keys encrypted, not in clear text.
-   Keep `ALLOW_SIGNUP` and `ALLOW_PRIVATE_STORE_URLS` off unless you need them.
-   Have each shop list its allowed websites.
-   Back up `DATA_DIR` or your Postgres, together with `SECRET_KEY`.

## Known limits

-   There is no password reset or two-step sign-in for owner accounts yet.
-   The server admin credential is a shared secret, not a per-person account.
-   Injection detection is pattern-based: it is transparent and testable, not a substitute for least privilege, which is why the dangerous
    actions are limited in code as well.
-   Amazon and Flipkart connectors have only been tested against recorded responses.
-   The attack lists in the evaluation suite were written together with the rules (see [docs/EVALUATION.md](docs/EVALUATION.md)).
