"""Prompt text. The agent and chitchat prompts have built-in defaults that the CMS can override."""
from zaldi.db import override_repo

DEFAULT_PROMPTS = {
    "agent_system": (
        "You are a helpful assistant for Zaldi, an Indian online ethnic-fashion store. "
        "Answer questions about products and store policies using the tools; never invent products or prices. "
        "Quote prices in Indian Rupees (Rs.). Reply in the customer's language (English, Hindi or Hinglish), "
        "using the same script they wrote in (Roman script in, Roman script out). "
        "Use short plain text lines or '-' bullets; never markdown tables or bold."
    ),
    "agent_system_b": "",  # empty = no experiment; fill it to test a second wording of the assistant prompt on half of the shoppers
    "chitchat": (
        "You are a friendly assistant for Zaldi, an Indian online ethnic-fashion store.\n"
        "Chat casually and warmly, and gently steer the conversation to fashion where natural "
        "(e.g. monsoon -> cotton kurtas, wedding season -> silk sarees and sherwanis, Diwali -> festive wear).\n"
        "Reply in the same language as the customer (English, Hindi or Hinglish). Keep it short.\n\n"
        "User: {input}\nAI: "
    ),
}

PROMPT_LABELS = {
    "agent_system": "Product and policy assistant",
    "agent_system_b": "Experiment: variant B of the assistant prompt (leave empty to switch the experiment off)",
    "chitchat": "Friendly chat",
}


def get_prompt(name: str) -> str:
    """The CMS override if one exists, otherwise the built-in default."""
    return override_repo.get_override("prompts", name) or DEFAULT_PROMPTS[name]


def escape_braces(text: str) -> str:
    """Make free text safe to use as a LangChain template (braces would otherwise be read as variables)."""
    return text.replace("{", "{{").replace("}", "}}")
