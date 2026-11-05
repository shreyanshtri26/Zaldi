"""Admin operations on the assistant's editable prompts."""
from zaldi.ai.prompts import DEFAULT_PROMPTS, PROMPT_LABELS
from zaldi.db import override_repo
from zaldi.errors import ValidationError

MAX_LENGTH = 4000


def _check_name(name: str) -> None:
    if name not in DEFAULT_PROMPTS:
        raise ValidationError(f"unknown prompt: {name}")


def _validate(name: str, content: str) -> None:
    if not content.strip():
        raise ValidationError("prompt cannot be empty")
    if len(content) > MAX_LENGTH:
        raise ValidationError(f"prompt must be at most {MAX_LENGTH} characters")
    if name == "chitchat":  # a LangChain template: the only variable allowed is {input}
        if "{input}" not in content:
            raise ValidationError("the chat prompt must contain {input}, where the customer's message goes")
        if "{" in content.replace("{input}", "") or "}" in content.replace("{input}", ""):
            raise ValidationError("the chat prompt may not contain other { } braces")


def _describe(name: str, overrides: dict) -> dict:
    return {
        "name": name,
        "label": PROMPT_LABELS[name],
        "content": overrides.get(name, DEFAULT_PROMPTS[name]),
        "default": DEFAULT_PROMPTS[name],
        "is_custom": name in overrides,
    }


def list_prompts() -> list[dict]:
    overrides = override_repo.get_overrides("prompts")
    return [_describe(name, overrides) for name in DEFAULT_PROMPTS]


def update_prompt(name: str, content: str) -> dict:
    _check_name(name)
    if not isinstance(content, str):
        raise ValidationError("content must be text")
    _validate(name, content)
    if content == DEFAULT_PROMPTS[name]:
        override_repo.delete_override("prompts", name)
    else:
        override_repo.set_override("prompts", name, content)
    return _describe(name, override_repo.get_overrides("prompts"))


def reset_prompt(name: str) -> dict:
    _check_name(name)
    override_repo.delete_override("prompts", name)
    return _describe(name, override_repo.get_overrides("prompts"))
