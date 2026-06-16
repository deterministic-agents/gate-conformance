"""
Check04 - Schema validation for tool inputs (C05).

AUTOMATED. Every tool request must reference a known tool_schema_hash
AND schema validation rejects are observable for malformed payloads.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check04(CheckRunner):
    check_id = "Check04"
    title = "Schema validation for tool inputs"
    control = "C05"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            # 1. No tool request without a tool_schema_hash.
            missing_hash = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_tool_requests')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND (tool_schema_hash IS NULL OR tool_schema_hash = '')
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # 2. Schema rejects are present (CI / runtime negative tests
            # emit policy_decisions with reason = schema_validation_failed).
            rejects = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_policy_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND decision = 'deny'
                  AND reason = 'schema_validation_failed'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            status = STATUS_PASS if missing_hash == 0 and rejects > 0 else STATUS_FAIL
            note = []
            if missing_hash > 0:
                note.append(f"{missing_hash} tool request(s) lack tool_schema_hash.")
            if rejects == 0:
                note.append(
                    "No schema-validation reject events observed; expected at least one "
                    "from CI negative tests in the assessment window."
                )
            if not note:
                note.append("All requests carry tool_schema_hash; schema rejects observed.")

            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_requests_missing_tool_schema_hash": int(missing_hash),
                    "count_schema_validation_rejects": int(rejects),
                },
                notes=" ".join(note),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
