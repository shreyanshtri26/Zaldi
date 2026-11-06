"""What one chat cost: tokens, estimated dollars and wall-clock time. Prices are estimates (USD per 1M tokens), editable here."""
PRICES = {  # model-name prefix -> (input, output) USD per 1M tokens
    "gemini-3.5-flash": (0.30, 2.50), "gemini-2.5-flash-lite": (0.10, 0.40), "gemini": (0.30, 2.50),
    "openai/gpt-oss-120b": (0.15, 0.60), "openai/gpt-oss-20b": (0.075, 0.30), "llama": (0.20, 0.20),
}


def cost_usd(model: str | None, tokens_in: int, tokens_out: int) -> float:
    """Longest matching prefix wins; an unknown model costs 0 rather than a made-up number."""
    match = max((k for k in PRICES if (model or "").startswith(k)), key=len, default=None)
    if match is None:
        return 0.0
    price_in, price_out = PRICES[match]
    return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 6)


class Usage:
    """Adds up token counts across the model calls of one answer."""

    def __init__(self, model: str | None = None) -> None:
        self.model, self.tokens_in, self.tokens_out, self.calls = model, 0, 0, 0

    def add(self, message) -> None:
        meta = getattr(message, "usage_metadata", None) or {}
        self.tokens_in += int(meta.get("input_tokens") or 0)
        self.tokens_out += int(meta.get("output_tokens") or 0)
        self.calls += 1

    def as_dict(self) -> dict:
        return {"model": self.model, "input_tokens": self.tokens_in, "output_tokens": self.tokens_out, "llm_calls": self.calls,
                "cost_usd": cost_usd(self.model, self.tokens_in, self.tokens_out)}


def model_name(llm) -> str | None:
    return getattr(llm, "model_name", None) or getattr(llm, "model", None)
