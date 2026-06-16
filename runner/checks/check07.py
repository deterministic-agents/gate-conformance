"""
Check07 - Breakers stop side effects (C06).

PARTIAL.

Automatable portion: presence of breaker trigger and stop-activation
events in the assessment window.

Manual portion: containment-timing drill. The breaker must halt
side-effecting tools within the configured SLO (default 30 seconds).
Containment time is the wall-clock delta from breaker_event.time to the
last side-effecting tool call by the same agent. This is operationally
meaningful only when measured against a controlled drill (synthetic
runaway), not against the production stream.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check07(CheckRunner):
    check_id = "Check07"
    title = "Breakers stop side effects"
    control = "C06"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            triggers = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_breaker_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type = 'breaker.trigger'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            activations = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_breaker_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type = 'stop.activation'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            slo_seconds = float(self.threshold("max_breaker_containment_seconds", 30))
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=(
                    f"Breaker triggers in last {window_days}d: {triggers}. "
                    f"Stop activations: {activations}. "
                    f"Containment SLO: {slo_seconds:.0f}s (manual measurement required)."
                ),
                metrics={
                    "count_breaker_triggers": int(triggers),
                    "count_stop_activations": int(activations),
                    "containment_slo_seconds": slo_seconds,
                },
                manual_steps=[
                    {
                        "step": "Execute a breaker containment drill",
                        "expected_artifact": (
                            "Drill record showing: drill_id, scenario, start_time, "
                            "breaker_trigger_time, last_side_effecting_tool_call_time, "
                            f"containment_time_seconds, met_slo (boolean, against {slo_seconds:.0f}s)."
                        ),
                        "rationale": (
                            "Containment time cannot be measured from production traffic alone. "
                            "A controlled drill exercises the kill switch end-to-end (identity "
                            "revocation + policy deny + network cut) and yields the SLO measurement."
                        ),
                    },
                    {
                        "step": "Verify break-glass stop disables network egress, not only the UI",
                        "expected_artifact": (
                            "Post-drill evidence that the agent identity cannot complete a tool "
                            "call after stop activation: gateway deny events + cloud network policy version."
                        ),
                        "rationale": (
                            "Stopping the UI without revoking identity/network leaves the agent "
                            "able to continue side effects via cached credentials."
                        ),
                    },
                ],
                notes=(
                    "Automatable evidence collected. Drill artefacts required to compute "
                    "containment SLO compliance."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
