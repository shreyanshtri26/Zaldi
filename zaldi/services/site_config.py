"""Storefront text that staff can change from the CMS. Defaults reproduce the original UI."""
import re

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
    "color_navy": ("#19335A", 7),
    "color_sky": ("#8FC8EB", 7),
    "color_blue": ("#4675C0", 7),
    "color_slate": ("#697A98", 7),
    "color_silver": ("#B8BFD6", 7),
    "font_family": ("default", 10),
    "font_size": ("14", 2),
    "cards_align": ("center", 6),
    "cards_position": ("below", 5),
    "bar_position": ("center", 6),
    "bar_width": ("normal", 6),
    "bar_shape": ("pill", 7),
    "photo_button": ("show", 4),
}

_CHOICES = {"font_family": {"default", "serif", "system", "mono"}, "cards_align": {"left", "center", "right"},
            "cards_position": {"above", "below"}, "bar_position": {"center", "bottom", "top"},
            "bar_width": {"narrow", "normal", "wide"}, "bar_shape": {"pill", "rounded", "square"},
            "photo_button": {"show", "hide"}}


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
        value = value.strip()
        if value and key.startswith("color_") and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValidationError(f"{key} must look like #8FC8EB")
        if value and key == "font_size" and not (value.isdigit() and 12 <= int(value) <= 20):
            raise ValidationError("font_size must be 12 to 20")
        if value and key in _CHOICES and value not in _CHOICES[key]:
            raise ValidationError(f"{key} must be one of: {', '.join(sorted(_CHOICES[key]))}")
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
