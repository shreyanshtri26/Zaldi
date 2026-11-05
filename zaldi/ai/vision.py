"""Multi-modal input: describe an uploaded outfit photo as search text for the discovery engine."""
import base64

from langchain_core.messages import HumanMessage

from zaldi.errors import ValidationError

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024
PROMPT = (
    "Describe the clothing or accessory in this photo for a catalogue search. Reply with one line of comma-separated "
    "tags only: garment type, colour(s), fabric, pattern, style or occasion, and who it suits. No sentences."
)


def validate_image(data: bytes, mime: str) -> None:
    if mime not in ALLOWED_TYPES:
        raise ValidationError("image must be a JPEG, PNG or WebP file")
    if not data or len(data) > MAX_BYTES:
        raise ValidationError("image must be between 1 byte and 5 MB")


def describe_image(data: bytes, mime: str, llm=None) -> str:
    """Return descriptive tags for the photo (raises ValidationError for unsupported files)."""
    validate_image(data, mime)
    if llm is None:
        from zaldi.ai.models import get_llm

        llm = get_llm()
    uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    reply = llm.invoke([HumanMessage(content=[{"type": "text", "text": PROMPT},
                                              {"type": "image_url", "image_url": {"url": uri}}])]).content
    if isinstance(reply, list):
        reply = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in reply)
    return " ".join(reply.split())[:300]
