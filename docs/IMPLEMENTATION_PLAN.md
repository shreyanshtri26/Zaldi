# Zaldi agentic-commerce plan

Adapts the generic 13-step pipeline to the existing stack (Flask, SQLite, FAISS, Gemini/Groq). Every model-dependent piece
has a deterministic path so it can be tested offline; the live LLM only writes the final wording.

Pipeline for one chat message: `guardrails.in -> (vision) -> router -> extract -> personalise -> hybrid search / cart / checkout -> LLM wording -> guardrails.out`

| Phase | Step | Module | Notes |
|---|---|---|---|
| 1 Foundation | 1 Stack + config | `zaldi/config.py` | `EMBEDDING_PROVIDER` (google/local), storefront + signing settings |
| | 2 Vector DB | `zaldi/search/index.py` | FAISS product index, rebuilt after any product write |
| | 3 Ingestion | `zaldi/search/ingest.py`, `python -m zaldi ingest` | text + metadata per product |
| 2 Routing | 4 Semantic router | `zaldi/ai/router.py` | routes: products, cart, checkout, chitchat |
| | 5 Extraction (NER) | `zaldi/search/extract.py` | query -> structured `Filters` (category, colour, size, budget, brand, gender, material) |
| | 6 Vision | `zaldi/ai/vision.py` | image upload -> descriptive tags -> discovery |
| 3 Discovery | 7 Hybrid search | `zaldi/search/hybrid.py` | SQL filters + FAISS + lexical, fused with RRF |
| | 8 Personalisation | `zaldi/services/preferences.py` | persistent per-session budget/brand/size/gender merged into filters |
| 4 Cart + checkout | 9 Cart pricing | `zaldi/services/cart.py` | stock checks, subtotal, shipping, discount, total |
| | 10 Browser automation | `zaldi/checkout/automation.py` + `store_sim` | Playwright drives a multi-step checkout |
| | 11 Handshake | `zaldi/checkout/handshake.py` | halts before payment, signed one-time token, user must confirm |
| 5 Safety + deploy | 12 Guardrails | `zaldi/ai/guardrails.py` | PII redaction, prompt-injection block, output scrub |
| | 13 Deploy | `Dockerfile`, `docker-compose.yml` | multi-stage (frontend build + gunicorn/waitress) |

Testing: unit tests per module, API tests per endpoint, a Playwright end-to-end test of the checkout, a full-pipeline test with
fake LLM/embeddings, then a live run against the real server.
