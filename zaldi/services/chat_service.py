"""Answer one customer message.

guardrails.in -> (vision) -> router -> [discovery | cart | checkout | chitchat] -> guardrails.out -> log

Discovery, cart and checkout are deterministic (extraction, hybrid search, pricing); the LLM only words the final reply,
and a plain-text fallback is used if it is unavailable. Personal data is redacted before anything reaches an LLM, and
the delivery address is never taken in chat (the UI collects it in a separate form).
"""
import logging
import re
from functools import lru_cache

from zaldi.ai import guardrails
from zaldi.ai.models import get_llm
from zaldi.ai.prompts import get_prompt
from zaldi.ai.router import Route, SemanticRouter
from zaldi.db import chat_log_repo
from zaldi.search.extract import extract_filters, merge_defaults
from zaldi.search.hybrid import search
from zaldi.services import cart, preferences
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
        lines = [f"- {p['product_name']} ({p['color']}, {p['brand']}) - {_money(p['price'])}" for p in products[:5]]
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


def _discover(query: str, session_id: str) -> dict:
    filters = merge_defaults(extract_filters(query), preferences.preference_filters(session_id))
    products, dropped = search(query, filters)
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


def _chitchat(query: str) -> dict:
    from zaldi.ai.chitchat import create_chitchat_chain

    return {"response": _as_text(create_chitchat_chain(get_llm()).invoke({"input": query}).content)}


def _checkout(session_id: str) -> dict:
    c = cart.get_cart(session_id)
    if not c["items"]:
        return {"response": "Your cart is empty. Tell me what you'd like and I'll add it first.", "cart": c}
    return {"response": "Happy to set that up.\n" + describe_cart(c) +
            "\nFor your safety I don't take addresses in chat: please fill in the secure delivery form below. "
            "I'll prepare the order and wait for your confirmation before anything is placed.",
            "cart": c, "action": "collect_address"}


def handle_query(query: str, session_id: str = "anonymous", image: tuple[bytes, str] | None = None) -> dict:
    """``image`` is ``(bytes, mime_type)`` for an uploaded photo."""
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

    route = Route.PRODUCTS if (image and tags) else get_router().guide(text)
    if route is Route.CHITCHAT and (POLICY_WORDS.search(text) or not extract_filters(text).is_empty()):
        route = Route.PRODUCTS  # a shopping entity or policy word beats a weak small-talk match
    if route is Route.CART:
        result = handle_cart_message(session_id, text)
    elif route is Route.CHECKOUT:
        result = _checkout(session_id)
    elif route is Route.PRODUCTS:
        result = _discover(text, session_id)
    else:
        result = _chitchat(text)

    secrets = [get_prompt("agent_system"), get_prompt("chitchat")]
    result["response"] = guardrails.scrub_output(result["response"], secrets)
    result.update(type=route.value, pii_redacted=pii, image_tags=tags or None)
    chat_log_repo.log_chat(text, result["response"], route.value)
    return result
