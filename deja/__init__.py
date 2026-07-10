"""Déjà — the recall engine (powered by Legibright).

Phase 2 ships the retrieval primitive only: `recall(query) -> list[Hit]`. No Block Kit,
no LLM query-generation, no MCP — those are Phase 3/4/5.
"""
from deja.models import Hit
from deja.recall import recall

__all__ = ["Hit", "recall"]
