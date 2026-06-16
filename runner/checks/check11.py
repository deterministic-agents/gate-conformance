"""
Check11 - Poisoning detection and quarantine path exists (C03/memory).

PARTIAL.

Automatable portion: at least one quarantine event observed in the
assessment window; quarantined items are not returned by subsequent
retrievals.

Manual portion: a controlled poisoning test - inject a known poisoned
document, confirm it is detected, quarantined, and never returned. The
runner cannot inject documents into the customer's memory store.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check11(CheckRunner):
    check_id = "Check11"
    title = "Poisoning detection and quarantine path exists"
    control = "C03"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            quarantines = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_memory_quarantine')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # Quarantined items must NOT appear in any subsequent retrieval response.
            # Reuse of a quarantined item_id in gate_memory_responses is a failure.
            leaks = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_memory_responses')} mr
                JOIN {self.table('gate_memory_quarantine')} mq
                  ON mr.item_id = mq.item_id
                WHERE mr.environment = :environment
                  AND mr.tenant_id = :tenant_id
                  AND mr.time >= mq.time
                  AND mr.time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            automated_finding = (
                f"Quarantine events in last {window_days}d: {quarantines}. "
                f"Quarantined items returned in subsequent retrievals: {leaks}."
            )

            if leaks > 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics={
                        "count_quarantine_events": int(quarantines),
                        "count_quarantine_leaks": int(leaks),
                    },
                    manual_steps=_manual_steps(),
                    notes="Quarantined items reached the model in subsequent retrievals.",
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics={
                    "count_quarantine_events": int(quarantines),
                    "count_quarantine_leaks": int(leaks),
                },
                manual_steps=_manual_steps(),
                notes=(
                    "Quarantine pipeline observable from production data. "
                    "Controlled poisoning test required for full PASS."
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
            "step": "Run a controlled poisoning test in a non-prod environment",
            "expected_artifact": (
                "Test record showing: poisoned_item_id, ingestion_time, "
                "quarantine_event_id, quarantine_reason, post-quarantine retrieval "
                "attempt(s) showing the item is no longer returned."
            ),
            "rationale": (
                "Production traffic does not exercise the detection path "
                "deterministically. A controlled test proves the pipeline catches "
                "a known poisoning pattern."
            ),
        },
        {
            "step": "Confirm quarantine notifications reach the security on-call",
            "expected_artifact": (
                "Alert routing record (PagerDuty / OpsGenie / equivalent) showing "
                "the quarantine event paged the relevant team."
            ),
            "rationale": (
                "Detection without notification fails the operational requirement. "
                "Silent quarantine is detection theatre."
            ),
        },
    ]
