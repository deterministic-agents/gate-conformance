"""
Check18 - Model behaviour is baselined and monitored for drift (C19).

PARTIAL with tier branching.

Tier behaviour:
  sandbox        Not required. SKIP via applicable_tiers.
  bounded        drift_decision events emitting at configured cadence minimum.
                 Log-only response is acceptable.
  high_privilege response_action events must show tier_reduction or
                 emergency_stop is wired for at least one drift-detected
                 dimension. Log-only ALONE is a FAIL at high_privilege.

Baseline artefact signature verification stays manual.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check18(CheckRunner):
    check_id = "Check18"
    title = "Model behaviour is baselined and monitored for drift"
    control = "C19"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            cadence_hours = float(
                self.threshold("c19_drift_decision_cadence_hours", 24)
            )
            max_baseline_age_days = int(
                self.threshold("c19_baseline_max_age_days", 90)
            )

            # 1. At least one signed baseline exists, tied to a current ABOM, and
            # not older than max_baseline_age_days.
            stale_or_missing = self.adapter.scalar(
                f"""
                SELECT COUNT(*)
                FROM {self.table('gate_agent_state')} a
                LEFT JOIN {self.table('gate_abom')} m
                  ON a.agent_instance_id = m.agent_instance_id AND m.is_current = 1
                LEFT JOIN {self.table('gate_baselines')} b
                  ON m.current_baseline_hash = b.baseline_hash
                WHERE a.environment = :environment
                  AND a.tenant_id = :tenant_id
                  AND a.autonomy_tier = :tier
                  AND a.state = 'Run'
                  AND (
                    b.baseline_hash IS NULL
                    OR julianday(:now) - julianday(b.created_at) > :max_age
                  )
                """,
                {
                    "environment": environment,
                    "tenant_id": tenant_id,
                    "tier": tier,
                    "now": since_iso(0),
                    "max_age": max_baseline_age_days,
                },
            ) or 0

            # 2. At least one drift_decision event must exist in the window.
            #    Absence at bounded or high_privilege is a coverage failure.
            drift_event_count = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_drift_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # 3. drift_decision events emitting at cadence.
            cadence_gaps = self.adapter.scalar(
                f"""
                WITH ordered AS (
                  SELECT
                    agent_instance_id,
                    dimension,
                    time,
                    LAG(time) OVER (
                      PARTITION BY agent_instance_id, dimension
                      ORDER BY time
                    ) AS prev_time
                  FROM {self.table('gate_drift_decisions')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND time >= :since
                )
                SELECT COUNT(*) FROM ordered
                WHERE prev_time IS NOT NULL
                  AND (julianday(time) - julianday(prev_time)) * 24 > :cadence_hours
                """,
                {
                    "environment": environment,
                    "tenant_id": tenant_id,
                    "since": since,
                    "cadence_hours": cadence_hours,
                },
            ) or 0

            # 4. response_action events: at high_privilege, must include at
            # least one tier_reduction or emergency_stop for a drift_detected
            # decision (proves the response router is wired beyond log-only).
            enforced_responses = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_response_actions')} ra
                JOIN {self.table('gate_drift_decisions')} d
                  ON ra.drift_decision_id = d.event_id
                WHERE ra.environment = :environment
                  AND ra.tenant_id = :tenant_id
                  AND ra.time >= :since
                  AND ra.action IN ('tier_reduction', 'emergency_stop')
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            metrics = {
                "count_agents_without_active_signed_baseline_or_stale": int(stale_or_missing),
                "count_cadence_gaps_exceeding_threshold": int(cadence_gaps),
                "count_drift_decision_events": int(drift_event_count),
                "drift_cadence_threshold_hours": cadence_hours,
                "max_baseline_age_days": max_baseline_age_days,
                "count_enforced_response_actions": int(enforced_responses),
            }
            automated_finding = (
                f"Agents missing/stale baseline at tier {tier}: {stale_or_missing}. "
                f"Cadence gaps exceeding {cadence_hours:.0f}h: {cadence_gaps}. "
                f"Enforced response actions (tier_reduction/emergency_stop): {enforced_responses}."
            )

            # Tier branching.
            if stale_or_missing > 0 or cadence_gaps > 0 or drift_event_count == 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics=metrics,
                    manual_steps=_manual_steps(),
                    notes=(
                        "Required at this tier: signed baseline tied to current ABOM, "
                        "drift decisions emitted within cadence threshold."
                    ),
                )

            if tier == "high_privilege" and enforced_responses == 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics=metrics,
                    manual_steps=_manual_steps(),
                    notes=(
                        "High-privilege tier requires at least one tier_reduction or "
                        "emergency_stop response action to be observable. Log-only "
                        "alone is not sufficient."
                    ),
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics=metrics,
                manual_steps=_manual_steps(),
                notes=(
                    "Baseline currency, drift cadence, and tier-appropriate response "
                    "wiring all observable. Baseline signature verification still required for full PASS."
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
            "step": "Verify the active baseline signature",
            "expected_artifact": (
                "Baseline file signature verification: signing_key_id, signature, "
                "computed baseline_hash, comparison against the hash recorded in "
                "drift_decision events. Expected: all match. Corpus descriptor must "
                "be documented in the baseline artifact."
            ),
            "rationale": (
                "Hash presence is necessary but not sufficient. The signature proves "
                "the baseline was approved, not just produced."
            ),
        },
        {
            "step": "Submit the re-baselining log",
            "expected_artifact": (
                "Log showing every re-baselining event with approver identity, "
                "rationale, and the ABOM-version transition that triggered it. "
                "Non-ABOM-triggered re-baselining must carry an exception id."
            ),
            "rationale": (
                "Silent re-baselining suppresses real drift signals. The approval log "
                "is the auditable defence against that anti-pattern."
            ),
        },
    ]
