"""Expose canonical and legacy llama.cpp model IDs without changing providers.

llama.cpp preset routing returns canonical IDs and lists the original Ollama
model IDs as aliases. OpenWebUI indexes only each model's id field. Publishing
a separate alias entry preserves existing Ahsoka/Local Agent/C-Agent bindings
when the native router becomes the primary provider.
"""
from __future__ import annotations


def expand_llamacpp_model_aliases(models: list[dict]) -> list[dict]:
    """Return all canonical entries plus distinct, valid legacy aliases.

    Canonical model IDs take precedence over aliases, regardless of ordering.
    Each alias keeps its canonical model's status/capabilities and records the
    canonical origin, without changing that original entry or its metadata.
    """
    seen = {
        model.get("id")
        for model in models
        if isinstance(model, dict) and isinstance(model.get("id"), str)
    }
    result = list(models)
    for model in models:
        if not isinstance(model, dict):
            continue
        canonical = model.get("id")
        aliases = model.get("aliases", [])
        if not isinstance(canonical, str) or not canonical:
            continue
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str) or not alias or alias in seen:
                continue
            result.append({**model, "id": alias, "name": alias, "alias_of": canonical})
            seen.add(alias)
    return result
