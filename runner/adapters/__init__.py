"""
Adapter factory and registry.

Register new backends by name in ADAPTERS. Each entry is a callable
that takes the evidence_store config block and returns an EvidenceAdapter.
"""
from __future__ import annotations

from typing import Any, Callable

from .base import EvidenceAdapter
from .sql import SqliteAdapter
from .bigquery import BigQueryAdapter


ADAPTERS: dict[str, Callable[[dict[str, Any]], EvidenceAdapter]] = {
    "sqlite": SqliteAdapter.from_config,
    "bigquery": BigQueryAdapter.from_config,
}


def build_adapter(evidence_store: dict[str, Any]) -> EvidenceAdapter:
    """Construct an adapter from a config block. Raises on unknown type."""
    backend = evidence_store.get("type")
    if not backend:
        raise ValueError("evidence_store.type is required")
    if backend not in ADAPTERS:
        raise ValueError(
            f"Unknown evidence store type {backend!r}; "
            f"available: {sorted(ADAPTERS)}"
        )
    return ADAPTERS[backend](evidence_store)


__all__ = ["EvidenceAdapter", "SqliteAdapter", "BigQueryAdapter", "build_adapter"]
