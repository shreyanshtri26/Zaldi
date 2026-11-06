"""Faithfulness check: every money amount in a reply must come from a tool result (or be a sum or difference of two of them).

Deterministic on purpose: it costs no model call, it is the same in CI as in production, and it is the exact check the eval
harness reports as "faithfulness". It guards amounts because a wrong price is the costliest thing a shop assistant can say.
"""
import json
import re

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
AMOUNT = re.compile(r"(?:rs\.?|inr|₹|\$|usd)\s*(\d[\d,]*(?:\.\d+)?)|(\d[\d,]*(?:\.\d+)?)\s*(?:rs\b|rupees|inr\b)", re.I)


def numbers_in(text: str) -> set[float]:
    out = set()
    for m in NUMBER.findall(text):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def note(known: set[float], tool_output) -> None:
    """Record every number a tool returned: those are the facts the reply is allowed to quote."""
    known |= numbers_in(json.dumps(tool_output, default=str))


def amounts_in(reply: str) -> list[float]:
    found = []
    for m in AMOUNT.finditer(reply):
        raw = (m.group(1) or m.group(2)).replace(",", "").rstrip(".")
        try:
            found.append(float(raw))
        except ValueError:
            pass
    return found


def unsupported(reply: str, known: set[float]) -> list[float]:
    """Amounts in ``reply`` that no tool returned. Pairwise sums and differences are allowed ("that saves Rs. 200")."""
    allowed = set(known)
    nums = sorted(known)[:60]  # bounded: a long catalogue result must not make this quadratic
    for a in nums:
        for b in nums:
            allowed.update((round(a + b, 2), round(abs(a - b), 2), round(a * 2, 2), round(a * 3, 2)))
    return [a for a in amounts_in(reply) if not any(abs(a - k) < 0.011 for k in allowed)]
