"""
Check12 - Semantic observability correlates to evidence (C13).

AUTOMATED. Every semantic trace event must correlate via run_id (or
trace_id) to at least one policy_decision and one ledger_event in the
same run.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check12(CheckRunner):
    check_id = "Check12"
    title = "Semantic observability correlates to evidence"
    control = "C13"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            row = self.adapter.query(
                f"""
                SELECT
                  COUNT(*) AS total_semantic,
                  SUM(CASE WHEN pd_count > 0 AND le_count > 0 THEN 1 ELSE 0 END) AS correlated
                FROM (
                  SELECT
                    s.run_id,
                    (SELECT COUNT(*) FROM {self.table('gate_policy_decisions')} p
                       WHERE p.run_id = s.run_id) AS pd_count,
                    (SELECT COUNT(*) FROM {self.table('gate_ledger_events')} l
                       WHERE l.run_id = s.run_id) AS le_count
                  FROM {self.table('gate_semantic_traces')} s
                  WHERE s.environment = :environment
                    AND s.tenant_id = :tenant_id
                    AND s.time >= :since
                  GROUP BY s.run_id
                ) joined
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("total_semantic") or 0)
            correlated = int(row.get("correlated") or 0)
            coverage = pct(correlated, total)
            status = STATUS_PASS if coverage == 100.0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_semantic_runs": total,
                    "count_semantic_runs_correlated": correlated,
                    "correlation_coverage_pct": coverage,
                },
                notes=(
                    f"Semantic-to-evidence correlation coverage: {coverage}%. "
                    f"Uncorrelated runs: {total - correlated}."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
