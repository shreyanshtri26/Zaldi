"""AI settings a store owner controls from the dashboard: provider (Gemini or Groq), each provider's API key, and the model.
Keys are write-only, encrypted, per store, and really used by that store's model and embedding calls."""
import langchain_google_genai
import langchain_groq
import pytest

from tests.fakes import FakeHttp
from tests.helpers import ADMIN_HEADERS
from zaldi import config, stores
from zaldi.ai import models
from zaldi.db import connect, init_db
from zaldi.services import accounts, ai_key, chat_service

GEMINI = "AIzaSyD" + "x" * 32  # 39 characters, the shape of a real Gemini key
GEMINI_2 = "AIzaSyD" + "y" * 32
GROQ = "gsk_" + "a" * 52
GROQ_2 = "gsk_" + "b" * 52
PASSWORD = "correct horse battery"
GOOGLE_MODELS = "https://generativelanguage.googleapis.com/v1beta/models"
GROQ_MODELS = "https://api.groq.com/openai/v1/models"


@pytest.fixture(autouse=True)
def env(temp_db, monkeypatch):
    init_db()
    monkeypatch.setattr(config, "GOOGLE_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(config, "LLM_PROVIDER", "google")
    monkeypatch.setattr(config, "LLM_MODEL", "gemini-3.5-flash")
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    ai_key._cache.clear()
    ai_key._models_cache.clear()
    chat_service.get_router.cache_clear()


def put(client, key, provider="google", headers=ADMIN_HEADERS):
    return client.put("/api/admin/ai-key", json={"provider": provider, "api_key": key}, headers=headers)


def status(client, provider="google", headers=ADMIN_HEADERS):
    return client.get("/api/admin/ai-key", headers=headers).get_json()["providers"][provider]


# --- keys ---------------------------------------------------------------------------------------------------------------------------------
def test_status_says_which_key_is_in_use_for_each_provider_and_never_what_it_is(client, monkeypatch):
    assert status(client)["source"] == status(client, "groq")["source"] == "none"
    monkeypatch.setattr(config, "GOOGLE_API_KEY", GEMINI_2)
    assert status(client)["source"] == "server" and status(client, "groq")["source"] == "none"
    for key, provider in ((GEMINI, "google"), (GROQ, "groq")):
        saved = put(client, key, provider)
        info = saved.get_json()["providers"][provider]
        assert saved.status_code == 200 and info["source"] == "store" and info["own_key_set"] and info["own_key_hint"] == "…" + key[-4:]
        assert key not in saved.get_data(as_text=True) and key not in client.get("/api/admin/ai-key", headers=ADMIN_HEADERS).get_data(as_text=True)
    assert GEMINI_2 not in client.get("/api/admin/ai-key", headers=ADMIN_HEADERS).get_data(as_text=True)  # the server's key stays hidden too


def test_saved_keys_are_encrypted_in_the_database(client):
    put(client, GEMINI)
    put(client, GROQ, "groq")
    with connect() as conn:
        stored = " ".join(r["value"] for r in conn.execute("SELECT value FROM settings WHERE key LIKE 'ai.%_api_key'"))
    assert GEMINI not in stored and GROQ not in stored and "xxxxxxxx" not in stored and "aaaaaaaa" not in stored
    assert ai_key.own_key("google") == GEMINI and ai_key.own_key("groq") == GROQ


def test_no_other_endpoint_leaks_a_saved_key(client):
    put(client, GEMINI)
    put(client, GROQ, "groq")
    for path in ("/api/admin/settings", "/api/admin/store", "/api/site-config", "/api/admin/stats", "/api/admin/ai-models", "/api/admin/ai-models?provider=groq"):
        body = client.get(path, headers=ADMIN_HEADERS).get_data(as_text=True)
        assert GEMINI not in body and GROQ not in body, path


@pytest.mark.parametrize("provider, bad", [
    ("google", ""), ("google", "   "), ("google", "hello"), ("google", GROQ), ("google", "AIza"), ("google", "AIza short key"),
    ("google", "AIza" + "x" * 200), ("google", GEMINI + " ; DROP"), ("groq", GEMINI), ("groq", "gsk_"), ("groq", "gsk_ spaced out"), ("groq", "gsk_" + "a" * 300),
])
def test_something_that_is_not_that_providers_key_is_refused(client, provider, bad):
    assert put(client, bad, provider).status_code == 400
    assert status(client, provider)["own_key_set"] is False


def test_an_unknown_provider_is_refused(client):
    assert put(client, GEMINI, "openai").status_code == 400
    assert client.put("/api/admin/ai-provider", json={"provider": "openai"}, headers=ADMIN_HEADERS).status_code == 400


def test_removing_a_key_returns_the_store_to_the_servers_key(client, monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", GROQ_2)
    put(client, GROQ, "groq")
    assert client.delete("/api/admin/ai-key?provider=groq", headers=ADMIN_HEADERS).get_json()["providers"]["groq"]["source"] == "server"
    assert ai_key.key_for("groq") == GROQ_2


def test_each_store_has_its_own_keys_and_only_its_owner_can_change_them(client):
    for slug in ("alpha", "beta"):
        client.post("/api/admin/stores", json={"slug": slug, "name": slug}, headers=ADMIN_HEADERS)
    accounts.create_account("a@alpha.test", PASSWORD, "alpha")
    accounts.create_account("v@alpha.test", PASSWORD, "alpha", "viewer")
    owner = {"X-Admin-Token": accounts.issue_token(accounts.authenticate("a@alpha.test", PASSWORD)), "X-Store": "alpha"}
    viewer = {"X-Admin-Token": accounts.issue_token(accounts.authenticate("v@alpha.test", PASSWORD)), "X-Store": "alpha"}
    assert put(client, GEMINI, headers=owner).status_code == 200
    assert status(client, headers={**ADMIN_HEADERS, "X-Store": "beta"})["own_key_set"] is False and status(client)["own_key_set"] is False
    assert put(client, GEMINI_2, headers=viewer).status_code == 403 and status(client, headers=viewer)["own_key_set"] is True
    assert put(client, GEMINI_2, headers={**owner, "X-Store": "beta"}).status_code == 403
    assert client.delete("/api/admin/ai-key", headers={**owner, "X-Store": "beta"}).status_code == 403
    with stores.use("alpha"):
        assert ai_key.own_key() == GEMINI
    with stores.use("beta"):
        assert ai_key.own_key() is None


def test_a_key_that_cannot_be_decrypted_falls_back_to_the_server_key_without_crashing(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", GEMINI_2)
    ai_key.set_key(GEMINI)
    ai_key._cache.clear()
    monkeypatch.setattr(config, "SECRET_KEY", "a-different-secret")
    assert ai_key.own_key() is None and ai_key.key_for("google") == GEMINI_2


# --- which provider -----------------------------------------------------------------------------------------------------------------------
def test_the_provider_follows_the_keys_the_store_has_unless_the_owner_picks_one(client):
    assert client.get("/api/admin/ai-key", headers=ADMIN_HEADERS).get_json()["provider"] == "google"  # the server's default
    put(client, GROQ, "groq")
    assert client.get("/api/admin/ai-key", headers=ADMIN_HEADERS).get_json()["provider"] == "groq"  # the only key this store brought
    put(client, GEMINI)
    both = client.get("/api/admin/ai-key", headers=ADMIN_HEADERS).get_json()
    assert both["provider"] == "google" and both["provider_is_default"] is True  # two keys: the server's default decides
    picked = client.put("/api/admin/ai-provider", json={"provider": "groq"}, headers=ADMIN_HEADERS).get_json()
    assert picked["provider"] == "groq" and picked["provider_is_default"] is False
    assert client.delete("/api/admin/ai-provider", headers=ADMIN_HEADERS).get_json()["provider"] == "google"


class FakeChat:
    made: list[dict] = []

    def __init__(self, **kwargs):
        FakeChat.made.append(kwargs)


@pytest.fixture
def chat_classes(monkeypatch):
    FakeChat.made.clear()
    monkeypatch.setattr(langchain_google_genai, "ChatGoogleGenerativeAI", type("G", (FakeChat,), {}))
    monkeypatch.setattr(langchain_groq, "ChatGroq", type("Q", (FakeChat,), {}))
    return FakeChat.made


def test_the_chat_model_runs_on_the_stores_own_key_and_provider(chat_classes, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", GEMINI_2)
    models.get_llm()
    assert chat_classes[-1]["google_api_key"] == GEMINI_2 and chat_classes[-1]["model"] == "gemini-3.5-flash"  # no key of its own: the server's
    ai_key.set_key(GEMINI)
    models.get_llm()
    assert chat_classes[-1]["google_api_key"] == GEMINI
    ai_key.set_key(GROQ, "groq")
    ai_key.set_provider("groq")
    models.get_llm()
    assert chat_classes[-1]["api_key"] == GROQ and chat_classes[-1]["model"] == "openai/gpt-oss-120b"  # Groq's default, not a Gemini model name


def test_a_provider_or_model_named_explicitly_is_used_as_given_with_that_providers_key(chat_classes):
    ai_key.set_key(GEMINI)
    ai_key.set_key(GROQ, "groq")
    models.get_llm("groq", "openai/gpt-oss-20b")
    assert chat_classes[-1]["api_key"] == GROQ and chat_classes[-1]["model"] == "openai/gpt-oss-20b"
    models.get_llm("google", "gemini-2.5-flash")
    assert chat_classes[-1]["google_api_key"] == GEMINI and chat_classes[-1]["model"] == "gemini-2.5-flash"


def test_a_store_on_gemini_is_not_forced_onto_a_groq_model_name_when_the_server_runs_groq(chat_classes, monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/gpt-oss-120b")
    ai_key.set_key(GEMINI)
    models.get_llm()
    assert chat_classes[-1]["google_api_key"] == GEMINI and chat_classes[-1]["model"] == "gemini-3.5-flash"


# --- embeddings and the router ------------------------------------------------------------------------------------------------------
def test_a_stores_gemini_key_switches_that_store_to_real_embeddings_unless_the_server_pins_them(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "local")
    assert models.embedding_provider() == "local" and models.embedding_id() == "local"
    ai_key.set_key(GROQ, "groq")
    assert models.embedding_provider() == "local"  # Groq has no embeddings
    ai_key.set_key(GEMINI)
    assert models.embedding_provider() == "google" and models.embedding_id().startswith("google:")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    assert models.embedding_provider() == "local"


def test_the_intent_router_is_built_once_per_embedding_space(monkeypatch):
    built = []

    class Router:
        def __init__(self):
            built.append(models.embedding_id())

    monkeypatch.setattr(chat_service, "SemanticRouter", Router)
    monkeypatch.setattr(config, "EMBEDDING_PROVIDER", "local")
    first = chat_service.get_router()
    assert chat_service.get_router() is first and built == ["local"]
    ai_key.set_key(GEMINI)
    assert chat_service.get_router() is not first and len(built) == 2 and built[1].startswith("google:")


# --- the test button ----------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("provider, key, failure, state", [
    ("google", GEMINI, "429 RESOURCE_EXHAUSTED quota exceeded", "quota"), ("google", GEMINI, "400 API key not valid. Please pass a valid API key.", "invalid"),
    ("google", GEMINI, "403 PERMISSION_DENIED", "invalid"), ("google", GEMINI, "connection reset by peer", "error"),
    ("groq", GROQ, "Error code: 429 - rate_limit_exceeded", "quota"), ("groq", GROQ, "Error code: 401 - invalid_api_key", "invalid"),
])
def test_the_test_button_explains_what_went_wrong_in_plain_words(client, monkeypatch, provider, key, failure, state):
    ai_key.set_key(key, provider)

    class Down:
        def invoke(self, prompt):
            raise RuntimeError(f"{failure} (key {key})")

    monkeypatch.setattr(models, "get_llm", lambda *a, **k: Down())
    result = client.post("/api/admin/ai-key/test", json={"provider": provider}, headers=ADMIN_HEADERS).get_json()
    assert result["ok"] is False and result["state"] == state and key not in str(result) and result["message"]


def test_the_test_button_passes_a_working_key_and_needs_some_key(client, monkeypatch):
    assert client.post("/api/admin/ai-key/test", headers=ADMIN_HEADERS).get_json()["state"] == "none"
    ai_key.set_key(GROQ, "groq")

    class Up:
        def invoke(self, prompt):
            return "ok"

    monkeypatch.setattr(models, "get_llm", lambda *a, **k: Up())
    result = client.post("/api/admin/ai-key/test", json={"provider": "groq"}, headers=ADMIN_HEADERS).get_json()
    assert (result["ok"], result["state"]) == (True, "working") and "openai/gpt-oss-120b" in result["message"]


# --- the model dropdown -------------------------------------------------------------------------------------------------------------------
GOOGLE_LIST = {"models": [
    {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
    {"name": "models/gemini-3.5-pro", "displayName": "Gemini 3.5 Pro", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash", "displayName": "Gemini 3.5 Flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-lite", "displayName": "Gemini 3.5 Flash-Lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-embedding-001", "displayName": "Embedding", "supportedGenerationMethods": ["embedContent"]},
    {"name": "models/gemini-3.5-flash-preview-tts", "displayName": "TTS", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash-image", "displayName": "Image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-bison-001", "displayName": "Old", "supportedGenerationMethods": ["generateText"]},
]}
GROQ_LIST = {"data": [
    {"id": "llama-3.3-70b-versatile", "active": True, "created": 1733447754},
    {"id": "openai/gpt-oss-120b", "active": True, "created": 1754408224},
    {"id": "whisper-large-v3", "active": True, "created": 1693721698},
    {"id": "meta-llama/llama-guard-4-12b", "active": True, "created": 1746743847},
    {"id": "playai-tts", "active": True, "created": 1740682771},
    {"id": "retired-model", "active": False, "created": 1700000000},
    {"id": "openai/gpt-oss-20b", "active": True, "created": 1754407957},
]}


@pytest.fixture
def providers(monkeypatch):
    http = FakeHttp({GOOGLE_MODELS: GOOGLE_LIST, GROQ_MODELS: GROQ_LIST})
    monkeypatch.setattr(ai_key, "requests", http)
    return http


def models_of(client, provider="google"):
    return client.get(f"/api/admin/ai-models?provider={provider}", headers=ADMIN_HEADERS).get_json()


def test_the_gemini_dropdown_lists_the_chat_models_google_offers_newest_first(client, providers):
    put(client, GEMINI)
    out = models_of(client)
    assert out["live"] is True
    assert [m["id"] for m in out["models"]] == ["gemini-3.5-pro", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]  # no embedding, speech, image or old models
    assert out["selected"] == out["default"] == "gemini-3.5-flash" and out["is_default"] is True
    call = providers.calls[0]
    assert call[2]["headers"]["x-goog-api-key"] == GEMINI and GEMINI not in call[1]  # the key travels in a header, not in the address


def test_the_groq_dropdown_lists_active_chat_models_newest_first(client, providers):
    put(client, GROQ, "groq")
    out = models_of(client, "groq")
    assert out["live"] is True and [m["id"] for m in out["models"]] == ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
    assert providers.calls[0][2]["headers"]["Authorization"] == f"Bearer {GROQ}" and GROQ not in providers.calls[0][1]


def test_the_list_is_remembered_and_falls_back_to_a_built_in_one_when_the_provider_cannot_be_asked(client, providers):
    put(client, GEMINI)
    models_of(client)
    models_of(client)
    assert len(providers.calls) == 1
    providers.routes = {GOOGLE_MODELS: ("down", 500)}
    ai_key._models_cache.clear()
    out = models_of(client)
    assert out["live"] is False and [m["id"] for m in out["models"]] == list(ai_key.PROVIDERS["google"]["fallback_models"])
    client.delete("/api/admin/ai-key", headers=ADMIN_HEADERS)
    assert models_of(client)["live"] is False  # no key at all: nobody to ask
    assert models_of(client, "groq")["live"] is False


def test_a_store_picks_a_model_per_provider_and_can_go_back_to_the_default(client, providers):
    put(client, GEMINI)
    put(client, GROQ, "groq")
    done = client.put("/api/admin/ai-model", json={"provider": "google", "model": "gemini-3.5-pro"}, headers=ADMIN_HEADERS).get_json()["providers"]
    assert done["google"]["model"] == "gemini-3.5-pro" and done["google"]["model_is_default"] is False and done["groq"]["model_is_default"] is True
    client.put("/api/admin/ai-model", json={"provider": "groq", "model": "openai/gpt-oss-20b"}, headers=ADMIN_HEADERS)
    assert models_of(client, "groq")["selected"] == "openai/gpt-oss-20b"
    back = client.delete("/api/admin/ai-model?provider=google", headers=ADMIN_HEADERS).get_json()["providers"]
    assert back["google"]["model"] == "gemini-3.5-flash" and back["google"]["model_is_default"] and back["groq"]["model"] == "openai/gpt-oss-20b"


@pytest.mark.parametrize("provider, bad", [
    ("google", ""), ("google", "gpt-4o"), ("google", "gemini-3.5-pro; DROP TABLE settings"), ("google", "gemini-" + "x" * 90), ("google", "gemini-9.9-imaginary"),
    ("groq", ""), ("groq", "whisper-large-v3"), ("groq", "not a model"), ("groq", "gemini-3.5-pro"),
])
def test_only_a_model_the_provider_lists_for_the_key_can_be_picked(client, providers, provider, bad):
    put(client, GEMINI if provider == "google" else GROQ, provider)
    assert client.put("/api/admin/ai-model", json={"provider": provider, "model": bad}, headers=ADMIN_HEADERS).status_code == 400
    assert status(client, provider)["model_is_default"] is True


def test_the_chosen_model_is_what_the_chat_model_uses_but_an_explicit_model_still_wins(chat_classes, providers, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", GEMINI_2)  # the server's key, none of the store's own
    ai_key.set_model("gemini-3.5-pro")
    models.get_llm()
    assert chat_classes[-1]["model"] == "gemini-3.5-pro" and chat_classes[-1]["google_api_key"] == GEMINI_2
    models.get_llm("google", "gemini-2.5-flash")  # the cheap-model setting names its model explicitly
    assert chat_classes[-1]["model"] == "gemini-2.5-flash"
    ai_key.set_key(GEMINI)
    models.get_llm()
    assert chat_classes[-1]["model"] == "gemini-3.5-pro" and chat_classes[-1]["google_api_key"] == GEMINI


def test_models_are_picked_per_store_and_a_viewer_cannot_change_them(client, providers):
    for slug in ("alpha", "beta"):
        client.post("/api/admin/stores", json={"slug": slug, "name": slug}, headers=ADMIN_HEADERS)
    accounts.create_account("v@alpha.test", PASSWORD, "alpha", "viewer")
    viewer = {"X-Admin-Token": accounts.issue_token(accounts.authenticate("v@alpha.test", PASSWORD)), "X-Store": "alpha"}
    alpha = {**ADMIN_HEADERS, "X-Store": "alpha"}
    put(client, GEMINI, headers=alpha)
    assert client.put("/api/admin/ai-model", json={"model": "gemini-3.5-pro"}, headers=alpha).status_code == 200
    assert client.put("/api/admin/ai-model", json={"model": "gemini-2.5-flash"}, headers=viewer).status_code == 403
    assert status(client, headers={**ADMIN_HEADERS, "X-Store": "beta"})["model_is_default"] is True


def test_photo_search_uses_gemini_even_when_the_store_chats_on_groq(monkeypatch):
    from zaldi.ai import vision

    png = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10]) + b"0" * 20  # a PNG signature is all the validator checks
    asked = []

    class Reply:
        content = "red silk saree, gold border"

    class Model:
        def invoke(self, messages):
            return Reply()

    monkeypatch.setattr(models, "get_llm", lambda provider=None, model=None: asked.append(provider) or Model())
    ai_key.set_key(GROQ, "groq")
    ai_key.set_key(GEMINI)
    ai_key.set_provider("groq")
    vision.describe_image(png, "image/png")
    assert asked == ["google"]
    ai_key.clear_key("google")  # no Gemini key at all: fall back to whatever the store runs on
    asked.clear()
    vision.describe_image(png, "image/png")
    assert asked == [None]
