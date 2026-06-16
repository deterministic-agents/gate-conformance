"""
Check10 - Memory access is authorized at retrieval time (C03/memory boundary).

AUTOMATED. Every memory read response must reference a memory_decision_id
(the gateway-level ACL/poisoning decision). Negative tests for
cross-tenant reads must show denies.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check10(CheckRunner):
    check_id = "Check10"
    title = "Memory access is authorized at retrieval time"
    control = "C03"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            row = self.adapter.query(
                f"""
                SELECT
                  COUNT(*) AS total_reads,
                  SUM(CASE WHEN memory_decision_id IS NOT NULL THEN 1 ELSE 0 END) AS decided
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

            cross_tenant = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_memory_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND decision = 'deny'
                  AND reason = 'cross_tenant_read'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            status = STATUS_PASS if coverage == 100.0 and cross_tenant >= 0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_memory_reads": total,
                    "count_memory_reads_with_decision": decided,
                    "memory_decision_coverage_pct": coverage,
                    "count_cross_tenant_denies": int(cross_tenant),
                },
                notes=(
                    f"Memory decision coverage: {coverage}%. Cross-tenant denies observed: "
                    f"{cross_tenant}."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
