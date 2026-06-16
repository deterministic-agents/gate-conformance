"""
Check16 - Unenrolled workloads are detected and remediated (C17).

PARTIAL with tier branching.

Tier behaviour:
  sandbox        Observe-only acceptable. If discovery events are
                 emitting and the classifier is signed, return PASS.
  bounded        Enforce mode required. Reconciliation delta must be
                 zero outside the active remediation TTL window AND a
                 termination drill record must exist (manual step).
  high_privilege Same as bounded, with stricter tagging policy.

Automated portion: reconciliation query, classifier signature presence,
remediation outcome shape. Manual portion: termination drill record.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check16(CheckRunner):
    check_id = "Check16"
    title = "Unenrolled workloads are detected and remediated"
    control = "C17"
    classification = CLASS_PARTIAL
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            remediation_ttl_hours = float(
                self.threshold("c17_remediation_ttl_hours", 72)
            )

            # 1. Discovery events emitting?
            disco = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_discovery_events')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # 2. Classifier bundle hashes referenced in discovery events match a
            # known signed bundle?
            unknown_classifier = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_discovery_events')} d
                LEFT JOIN {self.table('gate_classifier_bundles')} b
                  ON d.classifier_bundle_hash = b.bundle_hash
                WHERE d.environment = :environment
                  AND d.tenant_id = :tenant_id
                  AND d.time >= :since
                  AND b.bundle_hash IS NULL
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            # 3. Reconciliation: tool-stream identities not in C04 inventory and
            # not covered by an active exception, outside the remediation TTL.
            #
            # The query mirrors evidence_correlation.sql Check16 Query 1.
            cutoff_iso = since_iso(int(remediation_ttl_hours / 24) + 1)
            reconciliation_delta = self.adapter.scalar(
                f"""
                WITH recent AS (
                  SELECT DISTINCT agent_instance_id AS workload_identity, MIN(time) AS first_seen
                  FROM {self.table('gate_tool_requests')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND time >= :since
                  GROUP BY agent_instance_id
                ),
                active_exceptions AS (
                  SELECT candidate_hash, owner_identity, exception_ttl_expires_at
                  FROM {self.table('gate_remediation_outcomes')}
                  WHERE environment = :environment
                    AND tenant_id = :tenant_id
                    AND outcome = 'exception'
                    AND exception_ttl_expires_at > :now
                )
                SELECT COUNT(*) FROM recent r
                LEFT JOIN {self.table('gate_c04_inventory')} c04
                  ON r.workload_identity = c04.agent_instance_id
                LEFT JOIN active_exceptions ax
                  ON r.workload_identity = ax.owner_identity
                WHERE c04.agent_instance_id IS NULL
                  AND ax.owner_identity IS NULL
                  AND r.first_seen < :cutoff
                """,
                {
                    "environment": environment,
                    "tenant_id": tenant_id,
                    "since": since,
                    "cutoff": cutoff_iso,
                    "now": since_iso(0),
                },
            ) or 0

            # ---- Tier branching ----
            if tier == "sandbox":
                # Observe-only is acceptable. Discovery events emitting + signed
                # classifier bundle is enough.
                if disco > 0 and unknown_classifier == 0:
                    return CheckResult(
                        check_id=self.check_id,
                        status=STATUS_PASS,
                        metrics={
                            "count_discovery_events": int(disco),
                            "count_unknown_classifier_hashes": int(unknown_classifier),
                            "reconciliation_delta_outside_ttl": int(reconciliation_delta),
                        },
                        notes=(
                            "Sandbox tier: observe-only discovery acceptable. Discovery "
                            "events emitting, classifier bundle signed."
                        ),
                    )
                # Otherwise fail with a clear reason.
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    metrics={
                        "count_discovery_events": int(disco),
                        "count_unknown_classifier_hashes": int(unknown_classifier),
                    },
                    notes=(
                        "Sandbox tier: discovery missing or classifier bundle unsigned. "
                        "Observe-only requires both."
                    ),
                )

            # bounded and high_privilege: enforce mode required.
            # Reconciliation delta must be zero outside the TTL window.
            automated_finding = (
                f"Discovery events: {disco}. Unknown classifier bundle hashes: "
                f"{unknown_classifier}. Reconciliation delta outside the {remediation_ttl_hours:.0f}h "
                f"TTL window: {reconciliation_delta}."
            )
            if reconciliation_delta > 0 or unknown_classifier > 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics={
                        "count_discovery_events": int(disco),
                        "count_unknown_classifier_hashes": int(unknown_classifier),
                        "reconciliation_delta_outside_ttl": int(reconciliation_delta),
                        "remediation_ttl_hours": remediation_ttl_hours,
                    },
                    manual_steps=_manual_steps(tier),
                    notes=(
                        "Bounded/high-privilege tier requires zero reconciliation delta "
                        "and signed classifier bundle. Both must be satisfied."
                    ),
                )

            # Reconciliation clean; still PARTIAL because termination drill is
            # a manual artefact.
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics={
                    "count_discovery_events": int(disco),
                    "count_unknown_classifier_hashes": int(unknown_classifier),
                    "reconciliation_delta_outside_ttl": int(reconciliation_delta),
                    "remediation_ttl_hours": remediation_ttl_hours,
                },
                manual_steps=_manual_steps(tier),
                notes=(
                    "Enforce-mode evidence clean. Termination drill record required for full PASS."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )


def _manual_steps(tier: str) -> list[dict[str, str]]:
    steps = [
        {
            "step": "Submit a termination drill record",
            "expected_artifact": (
                "Drill record showing: synthetic candidate workload identity, "
                "time-to-revocation seconds, IdP revocation id, gateway deny rule version, "
                "network policy version. Drill must run end-to-end through all three "
                "termination layers."
            ),
            "rationale": (
                "Production traffic rarely exercises the termination path. The drill "
                "proves IdP + gateway + network egress can be cut on demand."
            ),
        },
    ]
    if tier == "high_privilege":
        steps.append(
            {
                "step": "Confirm untagged-asset policy is strict at high-privilege",
                "expected_artifact": (
                    "Policy export showing untagged cloud assets default to immediate "
                    "termination at high-privilege tier; any relaxed-posture exceptions "
                    "carry a TTL and approver identity."
                ),
                "rationale": (
                    "v1.3 untagged-asset policy is strict by default at high-privilege. "
                    "A relaxed posture without TTL is a known failure mode."
                ),
            }
        )
    return steps
