"""Prompt A/B test. Fill the CMS prompt "Experiment: variant B" and half of the shoppers (by session) get it instead of the
main prompt; every chat records its variant, so the metrics page can compare thumbs-up rates. Empty means no experiment."""
import hashlib

from zaldi.ai.prompts import get_prompt


def pick(session_id: str) -> tuple[str, str]:
    """``(variant, prompt name)`` for this shopper. The same session always gets the same variant."""
    if not get_prompt("agent_system_b").strip():
        return "A", "agent_system"
    bucket = int(hashlib.sha256(session_id.encode()).hexdigest(), 16) % 2
    return ("B", "agent_system_b") if bucket else ("A", "agent_system")
