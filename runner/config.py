"""
Configuration loading and validation.

The runner accepts a YAML config file. Required and optional keys are
declared here; we fail fast with clear messages rather than letting
checks discover missing keys at query time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# Defaults applied when the operator does not override.
DEFAULT_THRESHOLDS: dict[str, Any] = {
    # v1.0 thresholds
    "min_replay_success_rate_pct": 95,
    "max_hitl_review_hours": 24,
    "max_breaker_containment_seconds": 30,
    "min_attestation_coverage_pct": 100,
    "min_signature_coverage_pct": 100,
    # v1.3 thresholds
    "c17_remediation_ttl_hours": 72,
    "c17_classifier_coverage_pct": 100,
    "c18_quality_decision_coverage_pct": 100,
    "c19_drift_decision_cadence_hours": 24,
    "c19_baseline_max_age_days": 90,
}


@dataclass
class Config:
    """Loaded conformance runner configuration."""

    evidence_store: dict[str, Any]
    tenant_id: str
    environment: str
    autonomy_tier: str
    thresholds: dict[str, Any] = field(default_factory=dict)
    table_name_overrides: dict[str, str] = field(default_factory=dict)
    assessment_window_days: int = 30

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        raw = yaml.safe_load(p.read_text()) or {}
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        _required(raw, "evidence_store")
        _required(raw, "tenant_id")
        _required(raw, "environment")
        _required(raw, "autonomy_tier")
        if raw["autonomy_tier"] not in ("sandbox", "bounded", "high_privilege"):
            raise ValueError(
                "autonomy_tier must be one of: sandbox, bounded, high_privilege"
            )
        if raw["environment"] not in ("dev", "test", "prod"):
            raise ValueError("environment must be one of: dev, test, prod")
        if not isinstance(raw["evidence_store"], dict):
            raise ValueError("evidence_store must be a mapping")
        if "type" not in raw["evidence_store"]:
            raise ValueError("evidence_store.type is required")

        thresholds = dict(DEFAULT_THRESHOLDS)
        thresholds.update(raw.get("thresholds", {}) or {})

        return cls(
            evidence_store=raw["evidence_store"],
            tenant_id=raw["tenant_id"],
            environment=raw["environment"],
            autonomy_tier=raw["autonomy_tier"],
            thresholds=thresholds,
            table_name_overrides=raw.get("table_name_overrides", {}) or {},
            assessment_window_days=int(raw.get("assessment_window_days", 30)),
        )

    def as_check_config(self) -> dict[str, Any]:
        """The slice of config that gets passed to each CheckRunner."""
        return {
            "thresholds": self.thresholds,
            "table_name_overrides": self.table_name_overrides,
            "assessment_window_days": self.assessment_window_days,
        }


def _required(raw: dict[str, Any], key: str) -> None:
    if key not in raw or raw[key] in (None, ""):
        raise ValueError(f"Config missing required key: {key}")
