"""
Evidence store adapter interface.

Adapters translate the runner's SQL queries to the concrete query
dialect of the operator's evidence store. The runner uses only the two
methods on this interface; everything else lives behind it.

Add a new backend by subclassing EvidenceAdapter and registering it
under a name in adapters.factory.ADAPTERS.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EvidenceAdapter(ABC):
    """Interface every evidence store adapter must implement."""

    @abstractmethod
    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a parameterised query and return rows as a list of dicts.

        Parameter binding is named (e.g. ":tenant_id" in the SQL). Adapters
        translate to the backend's binding style.
        """

    @abstractmethod
    def scalar(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """Execute a query and return the first column of the first row, or None."""

    def close(self) -> None:
        """Release any resources held by the adapter. Default is a no-op."""
        return None
