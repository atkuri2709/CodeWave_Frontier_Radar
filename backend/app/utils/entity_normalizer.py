"""Entity name normalization for consistent aggregation.

Maps common variations (casing, abbreviations, suffixes) of well-known
AI companies and labs to their canonical form so that heatmap / analytics
aggregate correctly.
"""

import re
from typing import List

ENTITY_MAP: dict[str, str] = {
    "openai": "OpenAI",
    "open ai": "OpenAI",
    "openai inc": "OpenAI",
    "anthropic": "Anthropic",
    "anthropic ai": "Anthropic",
    "deepmind": "DeepMind",
    "google deepmind": "DeepMind",
    "google brain": "DeepMind",
    "meta ai": "Meta",
    "meta": "Meta",
    "meta platforms": "Meta",
    "facebook ai": "Meta",
    "fair": "Meta",
    "huggingface": "HuggingFace",
    "hugging face": "HuggingFace",
    "hf": "HuggingFace",
    "mistral": "Mistral AI",
    "mistral ai": "Mistral AI",
    "mistralai": "Mistral AI",
    "cohere": "Cohere",
    "cohere ai": "Cohere",
    "google": "Google",
    "google ai": "Google",
    "microsoft": "Microsoft",
    "microsoft research": "Microsoft",
    "nvidia": "NVIDIA",
    "amazon": "Amazon",
    "aws": "Amazon",
    "amazon ai": "Amazon",
    "apple": "Apple",
    "apple ml": "Apple",
    "alibaba": "Alibaba",
    "qwen": "Alibaba",
    "baidu": "Baidu",
    "stability ai": "Stability AI",
    "stability": "Stability AI",
    "xai": "xAI",
    "x.ai": "xAI",
    "inflection": "Inflection AI",
    "inflection ai": "Inflection AI",
    "ai21": "AI21 Labs",
    "ai21 labs": "AI21 Labs",
}

_STRIP_SUFFIXES = re.compile(
    r"\s*(inc\.?|llc|ltd\.?|corp\.?|co\.?|plc|gmbh)\s*$", re.IGNORECASE
)


def normalize_entity(name: str) -> str:
    """Normalize an entity name to its canonical form.

    1. Strip whitespace and corporate suffixes
    2. Lowercase lookup against ENTITY_MAP
    3. Return canonical name or title-cased original
    """
    if not name:
        return name
    cleaned = name.strip()
    cleaned = _STRIP_SUFFIXES.sub("", cleaned).strip()
    key = cleaned.lower()
    if key in ENTITY_MAP:
        return ENTITY_MAP[key]
    return cleaned


def normalize_entities(entities: List[str]) -> List[str]:
    """Normalize a list of entity names, deduplicating after normalization."""
    seen: set[str] = set()
    result: list[str] = []
    for e in entities:
        norm = normalize_entity(e)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result
