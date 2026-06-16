"""
Check06 - Deterministic replay reproduces an incident run (C10).

PARTIAL.

Automatable portion: confirm replay traces exist with completeness
metadata (model_id, prompt_bundle_hash, tool_schema_hash, snapshot URIs).

Manual portion: actually run the replay harness against a stored trace
and confirm the reproduced run yields identical request_hash/response_hash
pairs and equivalent side-effect outcomes. Replay execution is outside
the evidence store.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check06(CheckRunner):
    check_id = "Check06"
    title = "Deterministic replay reproduces an incident run"
    control = "C10"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            sql = f"""
                SELECT
                  COUNT(*) AS total,
                  SUM(CASE
                    WHEN model_id IS NOT NULL
                     AND prompt_bundle_hash IS NOT NULL
                     AND tool_schema_hash IS NOT NULL
                     AND snapshot_uri IS NOT NULL
                    THEN 1 ELSE 0 END) AS complete
                FROM {self.table('gate_replay_traces')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
            """
            row = self.adapter.query(
                sql,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("total") or 0)
            complete = int(row.get("complete") or 0)
            completeness = pct(complete, total)

            min_success = float(self.threshold("min_replay_success_rate_pct", 95))
            automated_finding = (
                f"Replay trace completeness over last {window_days}d: "
                f"{completeness}% ({complete}/{total}). "
                f"Threshold for replay-success rate: {min_success}%."
            )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL if total > 0 else STATUS_FAIL,
                automated_finding=automated_finding,
                metrics={
                    "count_replay_traces_total": total,
                    "count_replay_traces_complete": complete,
                    "replay_trace_completeness_pct": completeness,
                    "threshold_min_success_rate_pct": min_success,
                },
                manual_steps=[
                    {
                        "step": "Run the replay harness against a stored high-impact trace",
                        "expected_artifact": (
                            "Replay harness output showing identical request_hash/response_hash "
                            "pairs and equivalent side-effect outcomes vs the original run. "
                            "Replay must use recorded fixtures, not live IdP/policy/tool calls."
                        ),
                        "rationale": (
                            "C10 conformance requires demonstrated reproducibility, not just "
                            "trace completeness. The runner cannot exercise the harness."
                        ),
                    },
                    {
                        "step": "Submit replay-success-rate metric across the assessment window",
                        "expected_artifact": (
                            f"Replay success rate >= {min_success}% across the configured corpus "
                            "(or the production high-impact set if smaller)."
                        ),
                        "rationale": "Single successful replay is necessary but not sufficient.",
                    },
                ],
                notes=(
                    "Replay traces present and complete; manual replay execution still required."
                    if total > 0
                    else "No replay traces in window - failing the automated portion."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
