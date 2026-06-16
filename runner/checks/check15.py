"""
Check15 - Multi-agent messages are signed, versioned, nonce-protected (C14).

PARTIAL.

Automatable portion: envelope validation logs are present; spoofed-sender
and replayed-nonce reject events are present in the assessment window.

Manual portion: actively execute the negative tests (spoofed sender,
replayed nonce) and capture the deny outcomes. The runner cannot
synthesise inter-agent messages from the host.
"""
from __future__ import annotations

from .base import CheckRunner, CheckResult, CLASS_PARTIAL, STATUS_PARTIAL, STATUS_FAIL, STATUS_ERROR
from ._common import since_iso


class Check15(CheckRunner):
    check_id = "Check15"
    title = "Multi-agent messages are signed, versioned, nonce-protected"
    control = "C14"
    classification = CLASS_PARTIAL
    applicable_tiers = ["high_privilege"]

    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        try:
            window_days = int(self.config.get("assessment_window_days", 30))
            since = since_iso(window_days)

            envelope_rejects = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_agent_messages')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND validation_status = 'reject'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            spoofed_rejects = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_agent_messages')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND validation_status = 'reject'
                  AND reason = 'spoofed_sender'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            nonce_rejects = self.adapter.scalar(
                f"""
                SELECT COUNT(*) FROM {self.table('gate_agent_messages')}
                WHERE environment = :environment
                  AND tenant_id = :tenant_id
                  AND time >= :since
                  AND validation_status = 'reject'
                  AND reason = 'nonce_replay'
                """,
                {"environment": environment, "tenant_id": tenant_id, "since": since},
            ) or 0

            automated_finding = (
                f"Envelope rejects in last {window_days}d: {envelope_rejects} "
                f"(spoofed sender: {spoofed_rejects}, nonce replay: {nonce_rejects})."
            )

            return CheckResult(
                check_id=self.check_id,
                status=STATUS_PARTIAL,
                automated_finding=automated_finding,
                metrics={
                    "count_envelope_rejects": int(envelope_rejects),
                    "count_spoofed_sender_rejects": int(spoofed_rejects),
                    "count_nonce_replay_rejects": int(nonce_rejects),
                },
                manual_steps=[
                    {
                        "step": "Execute spoofed-sender negative test",
                        "expected_artifact": (
                            "Test record: synthetic AgentMessageEnvelope with a forged "
                            "sender identity; expected gateway response is reject with "
                            "reason=spoofed_sender; capture the rejection event."
                        ),
                        "rationale": (
                            "Production traffic does not produce attacker-shaped messages on "
                            "demand. A controlled negative test proves the validator catches them."
                        ),
                    },
                    {
                        "step": "Execute replayed-nonce negative test",
                        "expected_artifact": (
                            "Test record: resend an envelope with a previously-used nonce; "
                            "expected reject with reason=nonce_replay."
                        ),
                        "rationale": (
                            "Nonce protection only matters if it actually fires. The negative "
                            "test exercises the protection end-to-end."
                        ),
                    },
                    {
                        "step": "Confirm protocol version compatibility tests run in CI",
                        "expected_artifact": (
                            "CI artefact showing the multi-agent envelope schema is exercised "
                            "across the supported protocol versions; rejects on downgrade."
                        ),
                        "rationale": (
                            "Capability negotiation can be tricked into unsafe downgrade if "
                            "older versions are silently accepted."
                        ),
                    },
                ],
                notes=(
                    "Production reject evidence collected. Negative-test execution required "
                    "for full PASS."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
