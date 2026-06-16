"""
Check13 - Policy bundle versioning and hash pinning (C05).

AUTOMATED. Every policy_decisions row must reference a policy_bundle_hash
present in the gate_policy_bundles registry. Unknown hashes = FAIL.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_AUTOMATED, STATUS_PASS, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check13(CheckRunner):
    check_id = "Check13"
    title = "Policy bundle versioning and hash pinning"
    control = "C05"
    classification = CLASS_AUTOMATED
    applicable_tiers = ["sandbox", "bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            unknown = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_policy_decisions')} p
                LEFT JOIN {self.table('gate_policy_bundles')} b
                  ON p.policy_bundle_hash = b.bundle_hash
                WHERE p.environment = :environment
                  AND p.tenant_id = :tenant_id
                  AND p.time >= :since
                  AND b.bundle_hash IS NULL
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0
            missing = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_policy_decisions')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND (policy_bundle_hash IS NULL OR policy_bundle_hash = '')
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            status = STATUS_PASS if unknown == 0 and missing == 0 else STATUS_FAIL
            return CheckResult(
                check_id=self.check_id,
                status=status,
                metrics={
                    "count_decisions_missing_bundle_hash": int(missing),
                    "count_decisions_with_unknown_bundle_hash": int(unknown),
                },
                notes=(
                    "All policy decisions reference a known signed bundle."
                    if status == STATUS_PASS
                    else f"missing={missing}, unknown={unknown}"
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
