"""Which model answers: a cheap one for simple messages, the strong one for hard ones, with escalation if the cheap one fails.

Set ``LLM_MODEL_CHEAP`` to turn it on. The strong model (``LLM_MODEL``) is always the next in line, then the optional fallback.
"""
import re

from zaldi import config

HARD = re.compile(r"\b(compare|comparison|versus|vs|difference|cheaper|costlier|better|which|recommend|suggest|return|exchange|order|and then|then)\b", re.I)


def is_hard(text: str) -> bool:
    return len(text.split()) > 25 or bool(HARD.search(text))


def candidates(text: str, get_llm, get_fallback_llm) -> list:
    """Models to try in order. The cheap one is skipped for hard messages. (The factories are passed in so callers can swap them.)"""
    chain = []
    if config.LLM_MODEL_CHEAP and config.LLM_MODEL_CHEAP != config.LLM_MODEL and not is_hard(text):
        chain.append(get_llm(config.LLM_PROVIDER, config.LLM_MODEL_CHEAP))
    chain.append(get_llm())
    chain.append(get_fallback_llm())
    return [m for m in chain if m is not None]
