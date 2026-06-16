"""
Check05 - Immutable, tamper-evident audit ledger (C11).

AUTOMATED. Verify the ledger hash chain is contiguous: every event's
prev_event_hash matches the previous event's event_hash within the same
chain (tenant_id + environment + sink_uri).
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check05(CheckRunner):
    check_id = "Check05"
    title = "Immutable, tamper-evident audit ledger"
    control = "C11"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            # Find any chain break: a row whose prev_event_hash does not
            # match the event_hash of the immediately preceding row in the
            # same (tenant, environment, sink_uri, chain order).
            sql = f"""
                WITH ordered AS (
                  SELECT
                    sink_uri,
                    sequence_number,
                    event_hash,
                    prev_event_hash,
                    LAG(event_hash) OVER (
                      PARTITION BY tenant_id, environment, sink_uri
                      ORDER BY sequence_number
                    ) AS expected_prev
                  FROM {self.table('gate_ledger_events')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND time >= :since
                )
                SELECT COUNT(*) AS broken
                FROM ordered
                WHERE expected_prev IS NOT NULL
                  AND prev_event_hash <> expected_prev
            """
            broken = self.adapter.scalar(
                sql,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            total = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_ledger_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            status = STATUS_PASS if broken == 0 and total > 0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_ledger_events": int(total),
                    "count_chain_breaks": int(broken),
                },
                notes=(
                    "Hash chain contiguous." if status == STATUS_PASS and total > 0 else (
                        "No ledger events in window." if total == 0
                        else f"Hash chain breaks detected: {broken}."
                    )
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
