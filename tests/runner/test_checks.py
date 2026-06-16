"""
Per-check tests. One class per check id with at minimum:

    test_pass                          - status == PASS or PARTIAL when
                                         that is the check's normal
                                         passing-evidence outcome.
    test_fail                          - status == FAIL given a deliberate
                                         failure pattern.
    test_partial_returns_manual_steps  - PARTIAL checks list non-empty
                                         manual_steps.

Tier-aware checks (Check16, Check17, Check18) add tier-specific tests.
"""
from __future__ import annotations

import pytest

from runner.checks import (
    Check01, Check02, Check03, Check04, Check05,
    Check06, Check07, Check08, Check09, Check10,
    Check11, Check12, Check13, Check14, Check15,
    Check16, Check17, Check18, Check19,
)
from runner.checks.base import (
    STATUS_PASS, STATUS_FAIL, STATUS_PARTIAL, STATUS_ERROR, STATUS_SKIP,
    CLASS_PARTIAL,
)


TENANT = "acme-corp"
ENV = "prod"
BOUNDED = "bounded"
HIGH = "high_privilege"
SANDBOX = "sandbox"


def _run(cls, adapter, config, tier=BOUNDED):
    check = cls(adapter=adapter, config=config)
    return check.execute(tenant_id=TENANT, environment=ENV, tier=tier)


# ============================================================
# Check01 - AUTOMATED
# ============================================================

class TestCheck01:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check01, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_when_request_lacks_policy_decision(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        # Inject a tool request with no matching policy decision.
        adapter.execute_script(
            "INSERT INTO gate_tool_requests "
            "(request_hash, tenant_id, environment, time) VALUES "
            "('sha256:orphan', 'acme-corp', 'prod', datetime('now', '-1 days'));"
        )
        result = _run(Check01, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check02 - PARTIAL
# ============================================================

class TestCheck02:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check02, adapter, default_check_config)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps, "PARTIAL must populate manual_steps"

    def test_fail_when_non_gateway_identity_calls_tool(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        # Inject a request whose originating_identity is NOT in the gateway list.
        adapter.execute_script(
            "INSERT INTO gate_tool_requests VALUES "
            "('sha256:bypass-1', 'run-b', 'tr-b', 'spiffe://attacker/x', "
            "'spiffe://attacker/x', 'acme-corp', 'prod', 'crm.lookup', "
            "'read_only', 'sha256:tool-schema-v1', 1, datetime('now', '-1 days'));"
        )
        result = _run(Check02, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check03 - AUTOMATED
# ============================================================

class TestCheck03:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check03, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_when_identity_not_verified(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_tool_requests SET identity_verified = 0 WHERE request_hash = 'sha256:req-001';"
        )
        result = _run(Check03, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check04 - AUTOMATED
# ============================================================

class TestCheck04:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check04, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_when_schema_hash_missing(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_tool_requests SET tool_schema_hash = NULL WHERE request_hash = 'sha256:req-001';"
        )
        result = _run(Check04, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check05 - AUTOMATED
# ============================================================

class TestCheck05:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check05, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_on_chain_break(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_ledger_events SET prev_event_hash = 'sha256:WRONG' "
            "WHERE event_hash = 'sha256:le-3';"
        )
        result = _run(Check05, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check06 - PARTIAL
# ============================================================

class TestCheck06:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check06, adapter, default_check_config)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps


# ============================================================
# Check07 - PARTIAL
# ============================================================

class TestCheck07:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check07, adapter, default_check_config)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps
        assert any("containment drill" in s["step"].lower() for s in result.manual_steps)


# ============================================================
# Check08 - AUTOMATED
# ============================================================

class TestCheck08:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check08, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_when_no_enforcement_events(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "DELETE FROM gate_budget_events WHERE event_type IN ('budget.throttle', 'budget.deny');"
        )
        result = _run(Check08, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check09 - AUTOMATED (high_privilege only)
# ============================================================

class TestCheck09:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check09, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_PASS, result

    def test_skip_at_bounded(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check09, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_SKIP

    def test_fail_when_high_impact_unsigned(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_policy_decisions SET signature_ref = NULL, signing_key_id = NULL "
            "WHERE decision_id = 'dec-003';"
        )
        result = _run(Check09, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check10 - AUTOMATED
# ============================================================

class TestCheck10:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check10, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_when_memory_read_lacks_decision(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_memory_responses SET memory_decision_id = NULL "
            "WHERE response_id = 'mr-1';"
        )
        result = _run(Check10, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check11 - PARTIAL
# ============================================================

class TestCheck11:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check11, adapter, default_check_config)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps

    def test_fail_on_quarantine_leak(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        # Item poisoned-1 returned in a retrieval AFTER it was quarantined.
        adapter.execute_script(
            "INSERT INTO gate_memory_responses VALUES "
            "('mr-leak', 'poisoned-1', 'read', 'mdec-leak', NULL, "
            "'acme-corp', 'prod', datetime('now', '-1 days'));"
        )
        result = _run(Check11, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check12 - AUTOMATED
# ============================================================

class TestCheck12:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check12, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_on_uncorrelated_semantic(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "INSERT INTO gate_semantic_traces VALUES "
            "('st-orphan', 'run-orphan', 'tr-orphan', 'acme-corp', 'prod', datetime('now', '-1 days'));"
        )
        result = _run(Check12, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check13 - AUTOMATED
# ============================================================

class TestCheck13:
    def test_pass(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check13, adapter, default_check_config)
        assert result.status == STATUS_PASS, result

    def test_fail_on_unknown_bundle_hash(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "UPDATE gate_policy_decisions SET policy_bundle_hash = 'sha256:rogue' "
            "WHERE decision_id = 'dec-001';"
        )
        result = _run(Check13, adapter, default_check_config)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check14 - PARTIAL (high_privilege only)
# ============================================================

class TestCheck14:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check14, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps

    def test_fail_when_executed_without_approval(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        adapter.execute_script(
            "DELETE FROM gate_hitl_decisions WHERE approval_id = 'appr-1';"
        )
        result = _run(Check14, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check15 - PARTIAL (high_privilege only)
# ============================================================

class TestCheck15:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check15, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_PARTIAL
        assert result.manual_steps


# ============================================================
# Check16 - PARTIAL with tier branching
# ============================================================

class TestCheck16:
    def test_partial_at_bounded(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check16, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_PARTIAL, result
        assert result.manual_steps

    def test_tier_sandbox_passes_on_observe_only(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check16, adapter, default_check_config, tier=SANDBOX)
        assert result.status == STATUS_PASS, result

    def test_fail_on_reconciliation_delta(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_failures.sql")
        result = _run(Check16, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check17 - PARTIAL with tier branching
# ============================================================

class TestCheck17:
    def test_partial_at_bounded(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check17, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_PARTIAL, result
        assert result.manual_steps

    def test_tier_high_privilege_requires_provenance_enforcement(
        self, load_fixture, adapter, default_check_config
    ):
        load_fixture("sample_evidence_v13.sql")
        # The fixture has high_privilege with all three dimensions = deny,
        # so the check should be PARTIAL (the automatable portion passes).
        result = _run(Check17, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_PARTIAL, result

    def test_fail_when_quality_decision_missing(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_failures.sql")
        result = _run(Check17, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check18 - PARTIAL with tier branching
# ============================================================

class TestCheck18:
    def test_partial_at_bounded(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check18, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_PARTIAL, result
        assert result.manual_steps

    def test_high_privilege_passes_when_response_actions_wired(
        self, load_fixture, adapter, default_check_config
    ):
        load_fixture("sample_evidence_v13.sql")
        # Fixture includes a tier_reduction response_action -> high_privilege passes.
        result = _run(Check18, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_PARTIAL, result

    def test_fail_when_no_drift_events(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_failures.sql")
        # sample_failures.sql includes a drift event for the Check19 crossover
        # test; remove it here to isolate the "no drift events" failure mode.
        adapter.execute_script("DELETE FROM gate_drift_decisions;")
        result = _run(Check18, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_FAIL, result

    def test_high_privilege_fail_when_log_only(
        self, load_fixture, adapter, default_check_config
    ):
        load_fixture("sample_evidence_v13.sql")
        # Remove the tier_reduction response action; only log_only remains.
        adapter.execute_script(
            "DELETE FROM gate_response_actions WHERE action IN ('tier_reduction', 'emergency_stop');"
        )
        result = _run(Check18, adapter, default_check_config, tier=HIGH)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Check19
# ============================================================

class TestCheck19:
    def test_partial_returns_manual_steps(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check19, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_PARTIAL, result
        assert result.manual_steps
        assert any("runbook" in s["step"].lower() for s in result.manual_steps)

    def test_fail_on_crossover(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_failures.sql")
        result = _run(Check19, adapter, default_check_config, tier=BOUNDED)
        assert result.status == STATUS_FAIL, result


# ============================================================
# Cross-cutting: SKIP on out-of-tier
# ============================================================

class TestTierApplicability:
    def test_check05_skips_at_sandbox(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence.sql")
        result = _run(Check05, adapter, default_check_config, tier=SANDBOX)
        assert result.status == STATUS_SKIP

    def test_check18_skips_at_sandbox(self, load_fixture, adapter, default_check_config):
        load_fixture("sample_evidence_v13.sql")
        result = _run(Check18, adapter, default_check_config, tier=SANDBOX)
        assert result.status == STATUS_SKIP


# ============================================================
# Defensive: run() never raises
# ============================================================

class TestNeverRaises:
    @pytest.mark.parametrize(
        "cls",
        [Check01, Check02, Check03, Check04, Check05, Check06, Check07, Check08,
         Check09, Check10, Check11, Check12, Check13, Check14, Check15,
         Check16, Check17, Check18, Check19],
    )
    def test_returns_error_status_when_underlying_table_missing(
        self, adapter, default_check_config, cls
    ):
        # No fixture loaded - tables do not exist. Every check must catch and
        # return STATUS_ERROR rather than raise.
        check = cls(adapter=adapter, config=default_check_config)
        # Pick a tier the check applies to.
        tier = cls.applicable_tiers[0]
        result = check.execute(tenant_id=TENANT, environment=ENV, tier=tier)
        assert result.status == STATUS_ERROR
        assert result.error
