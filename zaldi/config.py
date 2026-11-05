"""Application settings: environment variables and filesystem paths (all relative to the repo root).

Other modules read these as ``config.NAME`` at call time (not ``from config import NAME``),
so tests can monkeypatch them.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Secrets -----------------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # required for CMS write endpoints

# --- Models ------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google")  # "google" | "groq"
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
# "google" (Gemini embeddings) or "local" (offline hashing embeddings: lexical only, no API, used when no key is set)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER") or ("google" if GOOGLE_API_KEY else "local")

# --- Commerce ----------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY") or ADMIN_TOKEN or "dev-only-secret"  # signs checkout handshake tokens
STOREFRONT_URL = os.getenv("STOREFRONT_URL", "")  # checkout site the browser automation drives; "" = this app's built-in simulator
BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "")  # "msedge"/"chrome" to use an installed browser instead of Playwright's
BROWSER_NO_SANDBOX = os.getenv("BROWSER_NO_SANDBOX") == "1"  # needed for Chromium as root inside Docker
HANDSHAKE_TTL = 900  # seconds a checkout confirmation stays valid

# --- Paths -------------------------------------------------------------------
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "zaldi.db"  # products, policies, chat logs (the CMS)
SEED_DIR = DATA_DIR / "seed"  # one-time seed data; the database is the source of truth afterwards
SEED_PRODUCTS_CSV = SEED_DIR / "products.csv"
SEED_POLICY_TXT = SEED_DIR / "policy.txt"
SEED_QUICK_ACTIONS_CSV = SEED_DIR / "quick_actions.csv"
POLICY_INDEX_DIR = DATA_DIR / "policy_index"  # FAISS index, rebuilt whenever policies change
PRODUCT_INDEX_DIR = DATA_DIR / "product_index"  # FAISS index of the catalogue, rebuilt when products change
ROUTER_CACHE_DIR = DATA_DIR / "router_cache"  # cached embeddings of the router samples
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
