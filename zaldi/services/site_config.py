"""Storefront text that staff can change from the CMS. Defaults reproduce the original UI."""
from zaldi.db import content_repo, override_repo
from zaldi.errors import ValidationError

# key -> (default value, max length)
SETTINGS = {
    "brand_name": ("Zaldi", 40),
    "tagline": ("Fashion assistant", 60),
    "welcome_heading": ("What are you looking for today?", 120),
    "welcome_subtitle": ("Ask about sarees, kurtas, sizes, delivery, returns or payments. "
                         "You can write in English, Hindi or Hinglish.", 300),
    "input_placeholder": ("Type your message…", 80),
}


def defaults() -> dict[str, str]:
    return {key: default for key, (default, _) in SETTINGS.items()}


def get_settings() -> dict[str, str]:
    """Defaults with any CMS overrides applied."""
    return defaults() | {k: v for k, v in override_repo.get_overrides("settings").items() if k in SETTINGS}


def update_settings(changes: dict) -> dict[str, str]:
    """Apply overrides. An empty value resets that setting to its default."""
    for key, value in changes.items():
        if key not in SETTINGS:
            raise ValidationError(f"unknown setting: {key}")
        if not isinstance(value, str):
            raise ValidationError(f"{key} must be text")
        if len(value.strip()) > SETTINGS[key][1]:
            raise ValidationError(f"{key} must be at most {SETTINGS[key][1]} characters")
    for key, value in changes.items():
        value = value.strip()
        if value:
            override_repo.set_override("settings", key, value)
        else:
            override_repo.delete_override("settings", key)
    return get_settings()


def get_site_config() -> dict:
    """Everything the storefront needs on load."""
    return {"settings": get_settings(), "quick_actions": content_repo.list_rows("quick_actions", only_active=True)}
