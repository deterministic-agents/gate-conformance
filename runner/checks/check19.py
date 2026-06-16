"""
Check19 - Adversarial and drift events are emitted as distinct types (C19 + C16).

PARTIAL.

Automatable portion:
  - Both gate.assurance.adversarial_outcome (C16) and
    gate.assurance.drift_decision (C19) must be observable as distinct
    event types in the assessment window.
  - No row may carry both event_type values simultaneously (a schema
    violation that would defeat the architectural separation).
  - Adversarial events stored in the C19 table or drift events stored
    in the C16 table indicate crossover and fail the check.

Manual portion: runbook separation. The drift response runbook and the
adversarial response runbook must be separate documents with separate
review histories. The runner cannot read runbook files outside the
evidence store.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check19(CheckRunner):
    check_id = "Check19"
    title = "Adversarial and drift events are emitted as distinct ledger event types"
    control = "C19/C16"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            # Both event types must exist in the assessment window.
            drift_count = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_drift_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type = 'gate.assurance.drift_decision'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            adversarial_count = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_adversarial_outcomes')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND event_type = 'gate.assurance.adversarial_outcome'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # Crossover 1: drift_decision event_type appearing in the
            # adversarial table.
            crossover_drift_in_adv = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_adversarial_outcomes')}
                WHERE event_type = 'gate.assurance.drift_decision'
                  AND environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            # Crossover 2: adversarial_outcome event_type appearing in the
            # drift table.
            crossover_adv_in_drift = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_drift_decisions')}
                WHERE event_type = 'gate.assurance.adversarial_outcome'
                  AND environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            # Schema-level violation: any row carrying both event_type values
            # simultaneously (a single event tagged as both).
            both_at_once = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM (
                  SELECT event_type FROM {self.table('gate_drift_decisions')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND time >= :since
                  UNION ALL
                  SELECT event_type FROM {self.table('gate_adversarial_outcomes')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND time >= :since
                ) all_events
                WHERE event_type LIKE '%adversarial_outcome%drift_decision%'
                   OR event_type LIKE '%drift_decision%adversarial_outcome%'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            crossover_total = (
                int(crossover_drift_in_adv)
                + int(crossover_adv_in_drift)
                + int(both_at_once)
            )

            metrics = {
                "count_drift_decision_events": int(drift_count),
                "count_adversarial_outcome_events": int(adversarial_count),
                "count_crossover_drift_in_adversarial_table": int(crossover_drift_in_adv),
                "count_crossover_adversarial_in_drift_table": int(crossover_adv_in_drift),
                "count_event_type_double_tag": int(both_at_once),
                "count_crossover_total": crossover_total,
            }
            automated_finding = (
                f"drift_decision events: {drift_count}. "
                f"adversarial_outcome events: {adversarial_count}. "
                f"Crossover total: {crossover_total} "
                f"(drift-in-adv={crossover_drift_in_adv}, "
                f"adv-in-drift={crossover_adv_in_drift}, "
                f"double_tag={both_at_once})."
            )

            if drift_count == 0 or adversarial_count == 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics=metrics,
                    manual_steps=_manual_steps(),
                    notes=(
                        "Both event types must be observable. C19 detects drift; C16 "
                        "detects attacks. The absence of either indicates a coverage gap, "
                        "not just a quiet window."
                    ),
                )
            if crossover_total > 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics=metrics,
                    manual_steps=_manual_steps(),
                    notes=(
                        "Crossover between C19 and C16 event types detected. The two "
                        "ledger streams MUST be disjoint."
                    ),
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics=metrics,
                manual_steps=_manual_steps(),
                notes=(
                    "Event-type distinctness verified. Runbook separation review "
                    "required for full PASS."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )


def _manual_steps() -> list[dict[str, str]]:
    return [
        {
            "step": "Submit the C19 drift-response runbook and the C16 adversarial-response runbook",
            "expected_artifact": (
                "Both runbooks as separate documents (separate file URIs or git refs). "
                "Each must show its own review history. The C19 runbook MUST NOT begin "
                "from an assumption of adversarial cause; the C16 runbook MUST NOT begin "
                "from an assumption of drift cause."
            ),
            "rationale": (
                "A merged or shared runbook defeats the architectural separation that "
                "the distinct event types are designed to enforce. The runner can "
                "verify type distinctness in the ledger but cannot read the runbook "
                "documents themselves."
            ),
        },
        {
            "step": "Submit the runbook sign-off log",
            "expected_artifact": (
                "Sign-off log showing both runbooks were reviewed and updated when C19 "
                "was introduced in v1.3; reviewer identities and timestamps recorded."
            ),
            "rationale": (
                "C19 is a v1.3 addition. Operators inheriting a v1.2.8 runbook set must "
                "explicitly demonstrate that the C16 runbook was reviewed for separation "
                "from the new C19 runbook."
            ),
        },
    ]
