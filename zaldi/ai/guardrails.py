"""Input/output guardrails around the LLM: strip personal data before it leaves the server, refuse prompt injection,
and scrub the model's reply. Pattern-based by design: transparent, fast and testable; not a substitute for least-privilege
tooling (the LLM here can only read the catalogue, it can never change a cart or order).
"""
import re

REFUSAL = "I can only help with shopping at Zaldi: products, sizes, delivery, returns and your cart. What are you looking for?"
MAX_INPUT_CHARS = 1000

_PATTERNS = [  # order matters: specific/long numbers first so they are not eaten by looser patterns
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("UPI", re.compile(r"\b[\w.-]{2,}@(?:ok\w+|ybl|paytm|upi|apl|axl|ibl|sbi|hdfcbank|icici|axisbank|oksbi)\b", re.I)),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
    ("AADHAAR", re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
]
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

_INJECTION = [re.compile(p, re.I) for p in (
    r"ignore (?:all |any |the )?(?:previous|prior|above|earlier|your)\b.*\b(?:instruction|prompt|rule)s?",
    r"disregard (?:all |any |the )?(?:previous|prior|above|your)?.*\b(?:instruction|prompt|rule)s?",
    r"forget (?:all |everything |your )?(?:previous |prior )?(?:instruction|rule|prompt)s?",
    r"forget (?:all |everything )(?:that )?(?:you (?:were|have been|are) (?:told|given)|i said|above)",
    r"(?:reveal|show|print|repeat|tell me|leak) (?:me )?(?:your |the )?(?:(?:system|hidden|initial|original|secret) ){1,2}(?:prompt|instruction|message)s?",
    r"what (?:is|are) your (?:system|initial) (?:prompt|instruction)s?",
    r"you are (?:now )?(?:dan|in developer mode|no longer|an? unrestricted)",
    r"\b(?:jailbreak|developer mode|do anything now)\b",
    r"pretend (?:that )?(?:you are|to be|you're) (?!a customer)",
    r"override (?:your |the )?(?:safety|rules|instructions|guardrails)",
    r"<\|?(?:im_start|system|endoftext)\|?>|\[/?inst\]|^\s*#{2,}\s*system\b",
    r"pichle (?:saare |sabhi )?(?:instructions?|niyam) (?:bhool|ignore)",
    r"(?:set|change|update) (?:the )?price (?:of|to)\b.*\b(?:0|zero|free)\b",
)]


# Text that arrives inside tool results (product descriptions, reviews, policy pages) is data, but a hostile store or seller
# can write instructions into it. These patterns are checked on top of the shopper-input ones above.
_DATA_INJECTION = [re.compile(p, re.I) for p in (
    r"\b(?:you must|you should now|you will now|from now on|new instructions?|updated instructions?|important:? (?:to )?(?:ai|assistant|model))\b",
    r"\b(?:assistant|ai|chatbot|model|bot)[,:]\s*(?:please \s*)?(?:ignore|disregard|add|call|send|reveal|tell|say|respond|put)\b",
    r"\bif you are an? (?:ai|assistant|model|bot|llm)\b",
    r"\b(?:call|use|run|invoke) (?:the )?[a-z_]+ (?:tool|function)\b",
    r"\b(?:add|put) (?:this|it|these|\d+ of these) (?:to|in|into) (?:the |your |their )?cart\b",
    r"\btell (?:every|each|all|the) (?:customers?|shoppers?|users?)\b",
    r"\bsystem prompt\b|^\s*(?:system|assistant)\s*:",
)]
NEUTRALIZED = "[text removed: it looked like instructions, not product information]"


def looks_like_instructions(text: str) -> bool:
    return is_prompt_injection(text) or any(p.search(text) for p in _DATA_INJECTION)


def neutralize(data):
    """Walk tool output and replace any string that reads like an instruction to the model. Numbers and ids are untouched."""
    if isinstance(data, str):
        return NEUTRALIZED if looks_like_instructions(data) else data
    if isinstance(data, list):
        return [neutralize(x) for x in data]
    if isinstance(data, dict):
        return {k: neutralize(v) for k, v in data.items()}
    return data


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace personal data with [KIND] placeholders. Returns (clean text, kinds found)."""
    found: list[str] = []

    def card(m: re.Match) -> str:
        # Any 13-19 digit run is treated as a card: a mistyped card number is just as sensitive as a valid one.
        if 13 <= len(re.sub(r"\D", "", m[0])) <= 19:
            found.append("CARD")
            return "[CARD]"
        return m[0]

    text = _CARD.sub(card, text)  # before phone/Aadhaar, whose digits it could contain
    for kind, pattern in _PATTERNS:
        def swap(m: re.Match, kind=kind) -> str:
            if kind == "EMAIL" and m[0].lower().endswith("@zaldi.in"):
                return m[0]  # the store's own support address is not personal data
            found.append(kind)
            return f"[{kind}]"

        text = pattern.sub(swap, text)
    return text, sorted(set(found))


def is_prompt_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION)


def check_input(text: str) -> tuple[str, list[str]]:
    """Return (text safe to send to an LLM, PII kinds removed); raise Blocked for injection attempts."""
    text = " ".join(text.split())[:MAX_INPUT_CHARS]
    if is_prompt_injection(text):
        raise Blocked(REFUSAL)
    return redact_pii(text)


def scrub_output(text: str, secrets: list[str] | None = None) -> str:
    """Final pass on a model reply: no personal data, and never echo the system prompt."""
    for secret in secrets or []:
        probe = " ".join(secret.split())[:60]
        if len(probe) > 20 and probe.lower() in " ".join(text.split()).lower():
            return REFUSAL
    return redact_pii(text)[0].strip()


class Blocked(Exception):
    """The message was refused by a guardrail; ``str(exc)`` is the customer-facing reply."""
