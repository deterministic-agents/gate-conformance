"""
Check02 - No bypass paths to tools (C05).

PARTIAL.

Automatable portion: confirm no tool API call in the assessment window
was made by an identity OTHER than the Tool Gateway service identity.
Operators record the gateway identity in
config.gateway_identity / table_name_overrides.

Manual portion: the brief requires:
  1. Network policy / firewall denies agent-runtime -> tool backend
  2. IAM bindings show agent service account has no direct backend access
  3. Codebase grep finds no direct_tool_client / bypass_gateway

The runner cannot grep an external codebase or inspect cloud IAM /
firewall without credentials, so we capture these as manual_steps.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check02(CheckRunner):
    check_id = "Check02"
    title = "No bypass paths to tools"
    control = "C05"
    classification = CLASS_PARTIAL
    applicable_tiers = ["bounded", "high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)
            # All tool-backend calls observed in the evidence store should
            # originate from the Tool Gateway identity. Anything else is
            # a candidate bypass.
            sql = f"""
                SELECT COUNT(*) AS suspicious
                FROM {self.table('gate_tool_requests')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND COALESCE(originating_identity, agent_instance_id)
                      NOT IN (
                        SELECT identity FROM {self.table('gate_gateway_identities')}
                      )
            """
            suspicious = self.adapter.scalar(
                sql,
                {
                    "environment": environment,
                    "tenant_id": tenant_id,
                    "since": since,
                },
            ) or 0
            automated_finding = (
                f"Tool calls from non-gateway identities in last {window_days}d: {suspicious}."
            )
            if suspicious > 0:
                return CheckResult(
                    check_id=self.check_id,
                    status=STATUS_FAIL,
                    automated_finding=automated_finding,
                    metrics={"count_non_gateway_originated_calls": int(suspicious)},
                    manual_steps=_manual_steps(),
                    notes="Bypass candidates detected in the evidence stream.",
                )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                manual_steps=_manual_steps(),
                notes="Bypass paths cannot be fully verified from the evidence store alone.",
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
            "step": "Verify network egress denies agent runtime -> tool backends",
            "expected_artifact": (
                "Network policy / firewall rule export showing the agent runtime "
                "subnet has no route to tool backend endpoints (ERP, CRM, external "
                "APIs) except via the gateway CIDR. Negative test: attempt curl "
                "from agent runtime to tool backend; expect timeout/deny."
            ),
            "rationale": "C05 invariant: only the Tool Gateway reaches tool backends.",
        },
        {
            "step": "Verify IAM bindings show no direct backend access for agent identity",
            "expected_artifact": (
                "IAM binding audit output (list policy bindings for agent service "
                "account / workload identity). Expected: no bindings on tool backend "
                "resources."
            ),
            "rationale": "C05 invariant cannot be enforced if IAM grants direct access.",
        },
        {
            "step": "Codebase scan for direct tool clients or bypass markers",
            "expected_artifact": (
                "grep -r 'direct_tool_client|bypass_gateway' across agent repo; "
                "expected: zero matches."
            ),
            "rationale": "Defence in depth: a network/IAM gap closes only if the SDK does not bypass.",
        },
    ]
