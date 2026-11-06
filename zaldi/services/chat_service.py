"""Answer one customer message.

guardrails.in -> (vision) -> router -> [discovery | cart | checkout | chitchat] -> guardrails.out -> log

Discovery, cart and checkout are deterministic (extraction, hybrid search, pricing); the LLM only words the final reply,
and a plain-text fallback is used if it is unavailable. Personal data is redacted before anything reaches an LLM, and
the delivery address is never taken in chat (the UI collects it in a separate form).
"""
import logging
import re
import time
from datetime import date
from functools import lru_cache

from zaldi import config
from zaldi.ai import guardrails
from zaldi.ai import resilience, routing
from zaldi.ai.models import get_fallback_llm, get_llm
from zaldi.ai.prompts import get_prompt
from zaldi.ai.router import Route, SemanticRouter
from zaldi import experiments
from zaldi.db import chat_log_repo
from zaldi.errors import ValidationError
from zaldi.search.extract import extract_filters, merge_defaults
from zaldi.search.hybrid import search
from zaldi.services import cart, preferences, returns
from zaldi.services.cart_chat import describe_cart, handle_cart_message

log = logging.getLogger(__name__)
POLICY_WORDS = re.compile(r"return|refund|exchange|ship|deliver|payment|pay\b|cod\b|upi|emi|gst|invoice|cancel|track|"
                          r"size guide|care|wash|coupon|discount|offer|warranty|policy|policies|pincode", re.I)
CARD_FIELDS = ("id", "product_name", "brand", "category", "color", "size", "material", "price", "stock_quantity",
               "image_url", "description")


@lru_cache(maxsize=1)
def get_router() -> SemanticRouter:
    return SemanticRouter()  # embeds (or loads cached) route samples once, on first chat


def _as_text(content) -> str:
    """Some Gemini models return a list of content blocks instead of a string."""
    if isinstance(content, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return content


def _money(n: int) -> str:
    return f"Rs. {n:,}"


def _fallback_reply(products: list[dict], dropped: list[str], policies: list[str], policy_question: bool = False) -> str:
    """Plain-text answer used when the LLM is unavailable. A policy question gets the policy text, not random products."""
    if policies and policy_question:
        return policies[0][:600]
    if products:
        lines = [f"- {p['product_name']} ({p['color']}, {p['brand']}) - {_money(p['price'])}" for p in products]  # the text lists exactly the cards shown below it
        note = f"\n(No exact match, so I relaxed: {', '.join(dropped)}.)" if dropped else ""
        return "Here is what I found:\n" + "\n".join(lines) + note
    if policies:
        return policies[0][:600]
    return "I couldn't find a match for that. Try a different colour, budget or category."


def _compose(query: str, products: list[dict], dropped: list[str], policies: list[str]) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    facts = "\n".join(f"- {p['product_name']} | {p['category']} | {p['color']} | {p['material']} | sizes {p['size']} | "
                      f"{_money(p['price'])} | {p['stock_quantity']} in stock | {p['brand']}" for p in products) or "(none found)"
    parts = [f"Customer message: {query}", f"Products found (shown to the customer as cards):\n{facts}"]
    if dropped:
        parts.append(f"No product matched every requirement, so these were relaxed: {', '.join(dropped)}. Say so honestly.")
    if policies:
        parts.append("Store policy excerpts:\n" + "\n---\n".join(policies))
    parts.append("Reply briefly using only the information above. Never invent products, prices or policies. "
                 "If nothing was found, say so and suggest how to widen the search.")
    reply = get_llm().invoke([SystemMessage(content=get_prompt("agent_system")), HumanMessage(content="\n\n".join(parts))])
    return _as_text(reply.content)


VAGUE = re.compile(r"\b(something|anything|suggest|recommend|gift|help me (find|choose|pick|shop)|what should i|show me (some|a few) options|i (need|want) (a |an |some )?(outfit|dress|clothes))\b", re.I)


def _ask_what_they_want(query: str, filters) -> dict | None:
    """A request with no category, colour, size or budget gives search nothing to work with: ask, with tappable categories."""
    if not filters.is_empty() or POLICY_WORDS.search(query) or not VAGUE.search(query):
        return None
    from zaldi.db import connect

    with connect() as conn:
        categories = [r["category"] for r in conn.execute("SELECT category FROM products GROUP BY category ORDER BY COUNT(*) DESC LIMIT 4")]
    if not categories:
        return None
    return {"response": "Happy to help you choose. What are you shopping for? You can also tell me your budget, colour or occasion.",
            "quick_replies": categories, "products": []}


def _discover(query: str, session_id: str) -> dict:
    asked = extract_filters(query)
    vague = _ask_what_they_want(query, asked)
    if vague:
        return vague
    policy_only = bool(POLICY_WORDS.search(query)) and asked.is_empty()  # "Is COD available?" names no product
    filters = merge_defaults(asked, preferences.preference_filters(session_id))
    products, dropped = ([], []) if policy_only else search(query, filters)
    cart.remember_results(session_id, [p["id"] for p in products])
    policies: list[str] = []
    if POLICY_WORDS.search(query) or not products:
        try:
            from zaldi.ai.tools.policy_search import search_policies

            policies = search_policies(query, k=3)
        except Exception:
            log.exception("policy search failed")
    try:
        text = _compose(query, products, dropped, policies)
    except Exception:
        log.exception("LLM unavailable; using plain reply")
        text = _fallback_reply(products, dropped, policies, bool(POLICY_WORDS.search(query)))
    return {"response": text, "products": [{k: p[k] for k in CARD_FIELDS} for p in products],
            "filters": filters.to_dict(), "relaxed": dropped}


SMALL_TALK_FALLBACK = ("Hi, I'm Zaldi. Ask me about sarees, kurtas, sizes, delivery, returns or payments, "
                       "and I'll help you find the right piece.")


def _chitchat(query: str) -> dict:
    from zaldi.ai.chitchat import create_chitchat_chain

    try:
        return {"response": _as_text(create_chitchat_chain(get_llm()).invoke({"input": query}).content)}
    except Exception:
        log.exception("LLM unavailable; using canned small-talk reply")
        return {"response": SMALL_TALK_FALLBACK}


DETAILS_PROMPT = ("To deliver it I need your full name, mobile number, address, city, state and PIN code, and whether you want "
                  "standard or express delivery. For your safety I don't take these in chat: please fill in the secure delivery form that has opened.")


def _checkout(session_id: str) -> dict:
    c = cart.get_cart(session_id)
    if not c["items"]:
        return {"response": "Your cart is empty. Tell me what you'd like and I'll add it first.", "cart": c}
    return {"response": "Happy to set that up.\n" + describe_cart(c) + "\n" + DETAILS_PROMPT +
            " I'll prepare the order and wait for your confirmation before anything is placed.",
            "cart": c, "action": "collect_address"}


# Messages that need more than one step (compare, then act). Everything else stays on the fast deterministic path.
MULTI_STEP = re.compile(r"\b(compare|comparison|cheaper|cheapest|costlier|costliest|versus|vs|difference between|which (one|is)|"
                        r"better|best (one|option)|and (then )?(add|buy|order)|then (add|buy|order)|also add|recommend|suggest)\b", re.I)


MAX_HISTORY = 6
_budget = {"day": None, "used": 0}


def _spend_agent_run() -> bool:
    """Count one agent run against today's cap (``AGENT_DAILY_RUNS``, per server process). False once the cap is reached."""
    today = date.today()
    if _budget["day"] != today:
        _budget.update(day=today, used=0)
    if config.AGENT_DAILY_RUNS and _budget["used"] >= config.AGENT_DAILY_RUNS:
        return False
    _budget["used"] += 1
    return True


def _clean_history(history) -> list[tuple[str, str]]:
    """The last few turns the browser sent, as (role, text). Untrusted: shape-checked, PII-redacted, injection-checked."""
    clean = []
    for turn in (history if isinstance(history, list) else [])[-MAX_HISTORY:]:
        if not isinstance(turn, dict) or turn.get("role") not in ("user", "assistant") or not isinstance(turn.get("text"), str):
            continue
        try:
            text, _ = guardrails.check_input(turn["text"][:400])
        except guardrails.Blocked:
            continue
        clean.append((turn["role"], text))
    return clean


def _price(card: dict) -> str:
    currency = card.get("currency", "INR")
    return f"Rs. {int(card['price']):,}" if currency == "INR" else f"${card['price']:,.2f}" if currency == "USD" else f"{card['price']} {currency}"


def _stars(p: dict) -> str:
    return f" · ★ {p['rating']:.1f}" + (f" ({p['rating_count']})" if p.get("rating_count") else "") if p.get("rating") else ""


def _insight(products: list[dict]) -> str:
    """A short comparison drawn from the results themselves: the lowest price and, where the store has ratings, the best rated."""
    if len(products) < 2:
        return ""
    cheapest = min(products, key=lambda p: p["price"])
    lines = [f"Lowest price: {cheapest['product_name']} ({_price(cheapest)})"]
    rated = [p for p in products if p.get("rating")]
    if rated:
        best = max(rated, key=lambda p: (p["rating"], p.get("rating_count") or 0))
        lines.append(f"Top rated: {best['product_name']} (★ {best['rating']:.1f})")
    return "\n\n" + "\n".join(lines)


def _followups(products: list[dict]) -> list[str]:
    """Tappable next steps for a result list, in the shopper's own terms: order what they are looking at."""
    if len(products) < 2:
        return []
    category = max({p["category"] for p in products if p.get("category")} or {""}, key=lambda c: sum(p["category"] == c for p in products))
    if not category:
        return []
    chips = [f"Cheapest {category}"]
    if any(p.get("rating") for p in products):
        chips.append(f"Top rated {category}")
    return chips


def _connected_store_fallback(text: str, session_id: str) -> dict:
    """The model is unavailable and the shopper is on a connected store: answer from that store's own search, as plain text.
    (The fixed pipeline would answer from this app's own catalogue, which is the wrong store.)"""
    from zaldi.connectors import get_connector

    products = get_connector().search_products(session_id, text)["products"]
    if not products:
        return {"response": "I couldn't find a match for that. Try a category name or a different word.", "products": [], "steps": []}
    lines = [f"- {p['product_name']} - {_price(p)}{_stars(p)}" for p in products]
    return {"response": "Here is what I found:\n" + "\n".join(lines) + _insight(products), "products": products, "steps": []}


def _try_agent(text: str, session_id: str, history: list[tuple[str, str]] | None = None, on_step=None) -> dict | None:
    """Run the tool-using agent; ``None`` means "use the normal pipeline" (disabled, model down, or an empty answer).

    Models are tried in order: a cheap one for simple messages (if configured), the main one, then the optional fallback.
    A rate limit or outage is retried with backoff first; a reply the self-check could not repair moves on to the next model."""
    if not config.AGENT_ENABLED:
        return None
    if not _spend_agent_run():
        return None
    try:
        from zaldi.agent.loop import run_agent
        from zaldi.connectors import get_connector

        variant, prompt_name = experiments.pick(session_id)
        failure, weak = None, None
        for llm in routing.candidates(text, get_llm, get_fallback_llm):
            try:
                result = resilience.retry(lambda: run_agent(text, session_id, get_connector(), llm, history=history,
                                                            on_step=on_step, prompt_name=prompt_name))
            except Exception as exc:
                failure = exc
                log.warning("agent model failed (%s); trying the next model if there is one", type(exc).__name__)
                continue
            result["variant"] = variant
            if not result["response"]:
                continue
            if result.get("checked") == "fallback":  # this model kept quoting amounts no tool returned: let a stronger one try
                weak = weak or result
                continue
            return result
        if weak:
            return weak
        raise failure or RuntimeError("no model available")
    except Exception:
        log.exception("agent failed; using the deterministic pipeline")
        return None


def handle_query(query: str, session_id: str = "anonymous", image: tuple[bytes, str] | None = None, history: list | None = None, on_step=None) -> dict:
    """``image`` is ``(bytes, mime_type)`` for an uploaded photo; ``history`` the last few ``{role, text}`` turns from the browser.
    ``on_step`` receives each agent tool step as it finishes (used by the streaming endpoint)."""
    started = time.perf_counter()
    try:
        safe, pii = guardrails.check_input(query or "")
    except guardrails.Blocked as blocked:
        chat_log_repo.log_chat("[blocked: prompt injection]", str(blocked), "blocked")
        return {"response": str(blocked), "type": "blocked"}

    tags = ""
    if image:
        from zaldi.ai.vision import describe_image

        try:
            tags, _ = guardrails.check_input(describe_image(*image))
        except guardrails.Blocked:
            tags = ""
    text = f"{safe} {tags}".strip()

    if (confirm := returns.CONFIRM.match(text)):  # the shopper's own tap on "Confirm return ...": matched by code, never by the model
        try:
            done = returns.confirm_return(session_id, confirm.group(1).lower())
            reply = f"Your return {done['return_id']} is confirmed. We will email pickup details."
        except ValidationError as exc:
            reply = f"I couldn't confirm that return: {exc}"
        chat_id = chat_log_repo.log_chat(text, reply, "return", meta={"latency_ms": round((time.perf_counter() - started) * 1000)})
        return {"response": reply, "type": "return", "chat_id": chat_id}

    route = Route.PRODUCTS if (image and tags) else get_router().guide(text)
    if route is Route.CHITCHAT and (POLICY_WORDS.search(text) or not extract_filters(text).is_empty()):
        route = Route.PRODUCTS  # a shopping entity or policy word beats a weak small-talk match
    label = None  # set when the agent, not a fixed route, handled the message
    from zaldi.connectors import get_connector

    external = get_connector().name != "local"  # the fixed pipeline only knows this app's own catalogue
    wants_agent = external or (MULTI_STEP.search(text) and route is not Route.CHITCHAT)
    agent_result = _try_agent(text, session_id, _clean_history(history), on_step) if wants_agent else None
    if agent_result is not None:
        result, label = agent_result, "agent"
    elif external:
        result, label = _connected_store_fallback(text, session_id), "products"
    elif route is Route.CART:
        result = handle_cart_message(session_id, text)
    elif route is Route.CHECKOUT:
        result = _checkout(session_id)
    elif route is Route.PRODUCTS:
        result = _discover(text, session_id)
    else:
        result = _chitchat(text)

    if "quick_replies" not in result and result.get("products"):
        result["quick_replies"] = _followups(result["products"])
        if not result["quick_replies"]:
            del result["quick_replies"]
    if result.get("action") == "collect_address" and "form" not in result["response"].lower():
        result["response"] = f"{result['response']}\n\n{DETAILS_PROMPT}"  # the agent path: never leave the shopper guessing what to fill in
    secrets = [get_prompt("agent_system"), get_prompt("chitchat")]
    result["response"] = guardrails.scrub_output(result["response"], secrets)
    result.update(type=label or route.value, pii_redacted=pii, image_tags=tags or None)
    usage = result.pop("usage", None) or {}
    meta = {"latency_ms": round((time.perf_counter() - started) * 1000), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
            "cost_usd": usage.get("cost_usd"), "model": usage.get("model"), "variant": result.pop("variant", None), "checked": result.pop("checked", None)}
    result["chat_id"] = chat_log_repo.log_chat(text, result["response"], label or route.value, result.get("steps"), meta)
    return result
