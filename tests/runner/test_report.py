"""
Report aggregation tests.

Build mixed-status CheckResult lists and assert the report's overall
status, counts, and metadata are correct.
"""
from __future__ import annotations

from runner.checks.base import (
    CheckResult,
    STATUS_PASS, STATUS_FAIL, STATUS_PARTIAL, STATUS_ERROR, STATUS_SKIP,
    CLASS_AUTOMATED, CLASS_PARTIAL,
)
from runner.config import Config
from runner.report import Report
from runner import (
    __version__ as RUNNER_VERSION,
    __gate_conformance_version__ as GATE_CONFORMANCE_VERSION,
    __gate_version__ as GATE_VERSION,
)


def _config(tier="bounded") -> Config:
    return Config(
        evidence_store={"type": "sqlite", "path": ":memory:"},
        tenant_id="acme-corp",
        environment="prod",
        autonomy_tier=tier,
        thresholds={},
        table_name_overrides={},
        assessment_window_days=30,
    )


def _result(check_id: str, status: str, classification: str = CLASS_AUTOMATED) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        status=status,
        classification=classification,
        title=f"{check_id} title",
        control="C0X",
        tier="bounded",
    )


# ---------------------------------------------------------------

def test_overall_status_conformant_when_all_pass():
    results = [_result(f"Check{i:02d}", STATUS_PASS) for i in range(1, 20)]
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    assert report.summary["overall_status"] == "CONFORMANT"
    assert report.summary["must_pass_checks_failing"] == 0
    assert report.summary["open_partial_checks"] == 0


def test_overall_status_non_conformant_when_any_fail():
    results = [_result(f"Check{i:02d}", STATUS_PASS) for i in range(1, 19)]
    results.append(_result("Check19", STATUS_FAIL))
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    assert report.summary["overall_status"] == "NON_CONFORMANT"
    assert report.summary["must_pass_checks_failing"] == 1


def test_overall_status_non_conformant_on_error():
    """ERROR counts as a must-pass failure - never silently passes."""
    results = [_result(f"Check{i:02d}", STATUS_PASS) for i in range(1, 19)]
    results.append(_result("Check19", STATUS_ERROR))
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    assert report.summary["overall_status"] == "NON_CONFORMANT"


def test_overall_status_partial_when_partial_present_no_failures():
    results = [_result(f"Check{i:02d}", STATUS_PASS) for i in range(1, 19)]
    results.append(_result("Check19", STATUS_PARTIAL, classification=CLASS_PARTIAL))
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    assert report.summary["overall_status"] == "PARTIAL"
    assert report.summary["open_partial_checks"] == 1
    assert report.summary["must_pass_checks_failing"] == 0


def test_all_19_check_ids_appear_in_report_even_when_skipped():
    """
    The runner is responsible for executing every registered check. Even
    when a tier-applicability skip means a check ran in SKIP mode, its
    row appears in the report (so auditors see the full surface).
    """
    results = [_result(f"Check{i:02d}", STATUS_PASS) for i in range(1, 17)]
    results.append(_result("Check17", STATUS_SKIP, classification=CLASS_PARTIAL))
    results.append(_result("Check18", STATUS_SKIP, classification=CLASS_PARTIAL))
    results.append(_result("Check19", STATUS_PARTIAL, classification=CLASS_PARTIAL))

    report = Report.from_results(
        results, _config(tier="sandbox"), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    ids_in_report = {row["check_id"] for row in report.checks}
    assert ids_in_report == {f"Check{i:02d}" for i in range(1, 20)}


def test_report_metadata_contains_gate_version_1_3():
    results = [_result("Check01", STATUS_PASS)]
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    assert report.gate_version == "1.3"
    assert report.gate_conformance_version == "1.2.0"
    assert report.report_version == "1.1"


def test_report_round_trips_through_yaml():
    import yaml

    results = [
        _result("Check01", STATUS_PASS),
        _result("Check19", STATUS_PARTIAL, classification=CLASS_PARTIAL),
    ]
    report = Report.from_results(
        results, _config(), generated_by="test",
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )
    rt = yaml.safe_load(report.to_yaml())
    assert rt["gate_version"] == "1.3"
    assert rt["summary"]["open_partial_checks"] == 1
    assert any(c["check_id"] == "Check19" for c in rt["checks"])
