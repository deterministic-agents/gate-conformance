"""
Check08 - Resource budgets are enforced, not just observed (C07).

AUTOMATED. There must be at least one enforcement event (throttle or
deny) for budget exhaustion in the assessment window. Pure budget-decrement
events are not enforcement.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check08(CheckRunner):
    check_id = "Check08"
    title = "Resource budgets are enforced, not just observed"
    control = "C07"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            enforced = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_budget_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type IN ('budget.throttle', 'budget.deny')
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            decrements = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_budget_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type = 'budget.decrement'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            status = STATUS_PASS if enforced > 0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_budget_enforcement_events": int(enforced),
                    "count_budget_decrement_events": int(decrements),
                },
                notes=(
                    f"Enforcement events: {enforced} (throttle/deny). Decrements only: {decrements}. "
                    + ("PASS." if enforced > 0 else "No enforcement events; observation without enforcement.")
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
