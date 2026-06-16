"""
Check01 - No tool execution without policy decision record (C05).

AUTOMATED. Antijoin: tool requests whose request_hash does not match
any policy_decisions.request_hash within the assessment window. Zero
rows is PASS.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check01(CheckRunner):
    check_id = "Check01"
    title = "No tool execution without policy decision record"
    control = "C05"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            sql = f"""
                SELECT COUNT(*) AS missing
                FROM {self.table('gate_tool_requests')} t
                LEFT JOIN {self.table('gate_policy_decisions')} p
                  ON t.request_hash = p.request_hash
                WHERE p.decision_id IS NULL
                  AND t.environment = :environment
                  AND t.tenant_id = :tenant_id
                  AND t.time >= :since
            """
            missing = self.adapter.scalar(
                sql,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            status = STATUS_PASS if missing == 0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_tool_calls_without_policy_decision": int(missing),
                    "assessment_window_days": window_days,
                },
                notes="Zero rows = PASS." if status == STATUS_PASS else (
                    f"{missing} tool call(s) lack a correlated policy decision in the last {window_days} days."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
