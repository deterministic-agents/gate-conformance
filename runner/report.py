"""
Conformance report writer.

The runner builds a Report from the list of CheckResults and writes it
in the format the operator requested (yaml or json). The report shape
mirrors conformance_report_template.yaml v1.1 so downstream auditors
can consume it the same way as a manual self-assessment.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .checks.base import (
    CheckResult,
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_PARTIAL,
    STATUS_ERROR,
    STATUS_SKIP,
)
from .config import Config


@dataclass
class Report:
    """Conformance report. Serialised as YAML by default."""

    generated_at: str
    generated_by: str
    runner_version: str
    gate_version: str
    gate_conformance_version: str
    report_version: str
    environment: str
    autonomy_tier: str
    tenant_id: str
    assessment_window_days: int

    checks: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_results(
        cls,
        results: list[CheckResult],
        config: Config,
        generated_by: str,
        runner_version: str,
        gate_version: str,
        gate_conformance_version: str,
    ) -> "Report":
        report = cls(
            generated_at=_now_iso(),
            generated_by=generated_by,
            runner_version=runner_version,
            gate_version=gate_version,
            gate_conformance_version=gate_conformance_version,
            report_version="1.1",
            environment=config.environment,
            autonomy_tier=config.autonomy_tier,
            tenant_id=config.tenant_id,
            assessment_window_days=config.assessment_window_days,
            checks=[r.to_dict() for r in results],
            metrics=_aggregate_metrics(results),
            summary=_summary(results),
        )
        return report

    def to_yaml(self) -> str:
        return yaml.safe_dump(asdict(self), sort_keys=False)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def write(self, path: str | Path, output_format: str = "yaml") -> Path:
        if output_format == "yaml":
            data = self.to_yaml()
        elif output_format == "json":
            data = self.to_json()
        else:
            raise ValueError(
                f"output_format must be 'yaml' or 'json'; got {output_format!r}"
            )
        p = Path(path)
        p.write_text(data)
        return p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aggregate_metrics(results: list[CheckResult]) -> dict[str, Any]:
    """Roll up per-check metrics into the report-level metrics block."""
    out: dict[str, Any] = {}
    for r in results:
        for k, v in (r.metrics or {}).items():
            # Only int/float aggregates roll up; everything else stays per-check.
            if isinstance(v, (int, float)) and k.startswith("count_"):
                out[k] = out.get(k, 0) + v
    return out


def _summary(results: list[CheckResult]) -> dict[str, Any]:
    counts = {
        STATUS_PASS: 0,
        STATUS_FAIL: 0,
        STATUS_PARTIAL: 0,
        STATUS_ERROR: 0,
        STATUS_SKIP: 0,
    }
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    must_pass_failing = counts[STATUS_FAIL] + counts[STATUS_ERROR]
    if must_pass_failing == 0 and counts[STATUS_PARTIAL] == 0:
        overall = "CONFORMANT"
    elif must_pass_failing == 0:
        overall = "PARTIAL"
    else:
        overall = "NON_CONFORMANT"

    return {
        "overall_status": overall,
        "counts": counts,
        "must_pass_checks_passing": counts[STATUS_PASS],
        "must_pass_checks_failing": must_pass_failing,
        "open_partial_checks": counts[STATUS_PARTIAL],
        "attestation": (
            "This report was produced by the gate-conformance runner against the "
            "operator's evidence store. PARTIAL results indicate the runner ran the "
            "automatable portion and lists the remaining manual evidence required. "
            "It does not constitute a formal audit or compliance certification."
        ),
    }
