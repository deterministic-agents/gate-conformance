"""
Check03 - Verified workload identity on every privileged request (C01).

AUTOMATED. Coverage query on gate_tool_requests.identity_verified.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check03(CheckRunner):
    check_id = "Check03"
    title = "Verified workload identity on every privileged request"
    control = "C01"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            min_pct = float(self.threshold("min_attestation_coverage_pct", 100))
            sql = f"""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE WHEN identity_verified = 1 OR identity_verified = TRUE THEN 1 ELSE 0 END) AS verified
                FROM {self.table('gate_tool_requests')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
            """
            row = self.adapter.query(
                sql,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("total") or 0)
            verified = int(row.get("verified") or 0)
            coverage = pct(verified, total)
            status = STATUS_PASS if coverage >= min_pct else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_tool_requests_total": total,
                    "count_tool_requests_with_verified_identity": verified,
                    "verified_identity_coverage_pct": coverage,
                    "threshold_min_pct": min_pct,
                },
                notes=(
                    f"Identity-verified coverage: {coverage}% (threshold {min_pct}%)."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
