"""
Helpers shared by every check.

We deliberately do not import the BigQuery client here. Every check
talks to self.adapter only, and the adapter knows how to translate
"gate_<table>" to fully-qualified BigQuery names. Date arithmetic is
done in Python so the SQL stays portable across sqlite and BigQuery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def since_iso(days: int) -> str:
    """Return ISO 8601 timestamp for now - days, UTC."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def pct(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 100.0
    return round((numerator / denominator) * 100.0, 2)
