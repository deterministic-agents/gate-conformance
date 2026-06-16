"""
Check14 - HITL approvals are signed and enforced (HITL obligations).

PARTIAL.

Automatable portion: every tool call whose policy decision carried a
HITL obligation has a linked, signed HITL decision before execution.

Manual portion: signature verification against the signing key. The
runner can confirm signature presence but verifying the signature is
mathematically valid requires either the public key (likely in a
separate KMS) or a sign-off from an offline verifier.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso, pct


class Check14(CheckRunner):
    check_id = "Check14"
    title = "HITL approvals are signed and enforced"
    control = "HITL"
    classification = CLASS_PARTIAL
    applicable_tiers = ["high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            row = self.adapter.query(
                f"""
                SELECT
                  COUNT(*) AS hitl_required,
                  SUM(CASE
                    WHEN h.approval_id IS NOT NULL
                     AND h.signature_ref IS NOT NULL
                    THEN 1 ELSE 0 END) AS approved
                FROM {self.table('gate_policy_decisions')} p
                LEFT JOIN {self.table('gate_hitl_decisions')} h
                  ON p.decision_id = h.policy_decision_id
                WHERE p.environment = :environment
                  AND p.tenant_id = :tenant_id
                  AND p.time >= :since
                  AND p.obligations LIKE '%hitl%'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            )[0]
            total = int(row.get("hitl_required") or 0)
            approved = int(row.get("approved") or 0)
            coverage = pct(approved, total) if total else 100.0

            executed_without_approval = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_tool_responses')} tr
                JOIN {self.table('gate_policy_decisions')} p
                  ON tr.request_hash = p.request_hash
                LEFT JOIN {self.table('gate_hitl_decisions')} h
                  ON p.decision_id = h.policy_decision_id
                WHERE tr.environment = :environment
                  AND tr.tenant_id = :tenant_id
                  AND tr.time >= :since
                  AND p.obligations LIKE '%hitl%'
                  AND (h.approval_id IS NULL OR h.signature_ref IS NULL)
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            automated_finding = (
                f"HITL-required decisions in last {window_days}d: {total}. "
                f"Signed approvals present: {approved} ({coverage}%). "
                f"Tool executions despite missing/unsigned approval: {executed_without_approval}."
            )
            if executed_without_approval > 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics={
                        "count_hitl_required": total,
                        "count_hitl_signed_present": approved,
                        "hitl_signature_presence_pct": coverage,
                        "count_hitl_required_executed_without_approval": int(executed_without_approval),
                    },
                    manual_steps=_manual_steps(),
                    notes="Tool executed without a valid signed HITL approval.",
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics={
                    "count_hitl_required": total,
                    "count_hitl_signed_present": approved,
                    "hitl_signature_presence_pct": coverage,
                    "count_hitl_required_executed_without_approval": int(executed_without_approval),
                },
                manual_steps=_manual_steps(),
                notes=(
                    "HITL approval enforcement evidence present. "
                    "Cryptographic signature verification still required for full PASS."
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
            "step": "Verify HITL approval signatures against the signing key",
            "expected_artifact": (
                "Sign-off log from a verification run: a sampled set of HITL "
                "decision records were validated against the registered signing "
                "key (KMS reference + signature_ref + verifier output). Expected: "
                "all sampled signatures verify."
            ),
            "rationale": (
                "Signature presence is necessary but not sufficient. A forged or "
                "improperly-signed approval would still appear present in the "
                "evidence store. Cryptographic verification confirms integrity."
            ),
        },
        {
            "step": "Confirm approver identities are authorised",
            "expected_artifact": (
                "Mapping of HITL approver identities to the authorisation roster "
                "in force during the assessment window; any approver outside the "
                "roster is reported."
            ),
            "rationale": (
                "A valid signature from an unauthorised approver still fails the "
                "policy intent. Authorisation is a separate dimension from signature integrity."
            ),
        },
    ]
