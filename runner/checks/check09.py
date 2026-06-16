"""
Check09 - High-impact actions require non-repudiation (C12).

AUTOMATED. Every high-impact tool invocation (irreversible_write,
financial, infrastructure categories) must have a signature_ref and a
non-null signing_key_id in the policy_decisions row.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check09(CheckRunner):
    check_id = "Check09"
    title = "High-impact actions require non-repudiation"
    control = "C12"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            min_pct = float(self.threshold("min_signature_coverage_pct", 100))
            row = self.adapter.query(
                f"""
                SELECT
                  COUNT(*) AS total_high_impact,
                  SUM(CASE
                    WHEN signature_ref IS NOT NULL AND signing_key_id IS NOT NULL
                    THEN 1 ELSE 0 END) AS signed
                FROM {self.table('gate_policy_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND tool_category IN ('irreversible_write', 'financial', 'infrastructure')
                  AND decision = 'allow'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("total_high_impact") or 0)
            signed = int(row.get("signed") or 0)
            coverage = pct(signed, total)
            status = STATUS_PASS if coverage >= min_pct else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_high_impact_allows": total,
                    "count_high_impact_signed": signed,
                    "signature_coverage_pct": coverage,
                    "threshold_min_pct": min_pct,
                },
                notes=(
                    f"Signature coverage on high-impact actions: {coverage}% "
                    f"(threshold {min_pct}%)."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
