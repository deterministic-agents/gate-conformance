"""
Check17 - Memory retrievals pass quality gates before reaching the model (C18).

PARTIAL with tier branching.

Tier behaviour:
  sandbox        Quality-decision presence is enough; enforcement is not required.
  bounded        Freshness and confidence MUST be configured as 'deny' (enforce)
                 for at least one content class in the active quality bundle.
                 Provenance may stay flag-only.
  high_privilege All three (freshness, confidence, provenance) MUST be configured
                 as 'deny' for at least one content class in the active bundle.

The check looks at the quality bundle config (gate_quality_bundles) to
infer which gates are enforced, not just whether quality_decision events
exist. Bundle file signature verification stays manual.
"""
from __future__ import annotations

import json

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check17(CheckRunner):
    check_id = "Check17"
    title = "Memory retrievals pass quality gates before reaching the model"
    control = "C18"
    classification = CLASS_PARTIAL
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            min_pct = float(
                self.threshold("c18_quality_decision_coverage_pct", 100)
            )

            # 1. Coverage: every memory read has a quality_decision_id.
            row = self.adapter.query(
                f"""
                SELECT
                  COUNT(*) AS total_reads,
                  SUM(CASE WHEN quality_decision_id IS NOT NULL THEN 1 ELSE 0 END) AS decided
                FROM {self.table('gate_memory_responses')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND request_type = 'read'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("total_reads") or 0)
            decided = int(row.get("decided") or 0)
            coverage = pct(decided, total)

            # 2. Active quality bundle: which dimensions are enforced (action == deny)?
            bundles = self.adapter.query(
                f"""
                SELECT bundle_hash, action_matrix
                FROM {self.table('gate_quality_bundles')}
                WHERE tenant_id = :tenant_id
                  AND is_active = 1
                """,
                {"tenant_id": tenant_id},
            )
            enforced = _enforced_dimensions(bundles, tier)
            required = _required_dimensions(tier)
            missing_enforcement = sorted(required - enforced)

            automated_finding = (
                f"quality_decision_id coverage: {coverage}% ({decided}/{total}). "
                f"Active quality bundles: {len(bundles)}. "
                f"Enforced dimensions ({tier}): {sorted(enforced) or '<none>'}. "
                f"Required by tier: {sorted(required)}. "
                f"Missing enforcement: {missing_enforcement or '<none>'}."
            )

            metrics = {
                "count_memory_reads": total,
                "count_memory_reads_with_quality_decision": decided,
                "quality_decision_coverage_pct": coverage,
                "threshold_min_pct": min_pct,
                "enforced_dimensions": sorted(enforced),
                "required_dimensions": sorted(required),
                "missing_enforcement": missing_enforcement,
            }

            if coverage < min_pct or missing_enforcement:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics=metrics,
                    manual_steps=_manual_steps(),
                    notes=(
                        f"Tier {tier} requires enforcement on {sorted(required)}; "
                        f"missing {missing_enforcement or '<coverage>'}."
                    ),
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics=metrics,
                manual_steps=_manual_steps(),
                notes=(
                    "Coverage and enforcement configuration meet tier requirements. "
                    "Bundle signature verification still required for full PASS."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )


def _required_dimensions(tier: str) -> set[str]:
    if tier == "high_privilege":
        return {"freshness", "confidence", "provenance"}
    if tier == "bounded":
        return {"freshness", "confidence"}
    return set()


def _enforced_dimensions(bundles: list[dict], tier: str) -> set[str]:
    """
    Return the set of dimensions for which the active bundle has action='deny'
    in the given tier, for at least one content class. The action_matrix is
    stored as JSON-encoded text in the registry table.
    """
    enforced: set[str] = set()
    for b in bundles:
        raw = b.get("action_matrix")
        if not raw:
            continue
        try:
            matrix = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        tier_matrix = matrix.get(tier, {}) if isinstance(matrix, dict) else {}
        for class_matrix in tier_matrix.values():
            if not isinstance(class_matrix, dict):
                continue
            for dim in ("freshness", "confidence", "provenance"):
                if class_matrix.get(dim) == "deny":
                    enforced.add(dim)
    return enforced


def _manual_steps() -> list[dict[str, str]]:
    return [
        {
            "step": "Verify the active quality bundle signature",
            "expected_artifact": (
                "Bundle signature verification log: signer identity, signature_ref, "
                "computed bundle_hash, comparison against the hash recorded in "
                "quality_decision events. Expected: all match."
            ),
            "rationale": (
                "The runner reads the registry copy of the action_matrix. The signature "
                "verification requires reading the bundle file from object storage, "
                "which is outside the evidence store schema."
            ),
        },
        {
            "step": "Verify downstream consumers honour quality_flags",
            "expected_artifact": (
                "Prompt template export showing flagged content is surfaced as a "
                "structured field, and a C13 semantic trace sample showing the "
                "agent's reasoning category acknowledges the flag."
            ),
            "rationale": (
                "Flags that are stripped by the prompt template are inert. The "
                "downstream behaviour completes the gate."
            ),
        },
    ]
