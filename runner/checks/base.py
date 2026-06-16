"""
Base classes for conformance check implementations.

Every check subclasses CheckRunner, declares its check_id and
applicable_tiers, and implements run(). The runner enforces tier
applicability before calling run() so individual checks do not have to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


# Outcome strings used in CheckResult.status.
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_PARTIAL = "PARTIAL"
STATUS_MANUAL = "MANUAL"
STATUS_ERROR = "ERROR"
STATUS_SKIP = "SKIP"

# Classification strings used by individual checks for their advertised class.
CLASS_AUTOMATED = "AUTOMATED"
CLASS_PARTIAL = "PARTIAL"
CLASS_MANUAL = "MANUAL"


@dataclass
class CheckResult:
    """Outcome of running a single conformance check."""

    check_id: str
    status: str  # one of STATUS_*
    classification: str = ""  # AUTOMATED | PARTIAL | MANUAL
    title: str = ""
    control: str = ""
    tier: str = ""

    # PASS/FAIL/PARTIAL evidence: identifiers of rows or artefacts the runner
    # inspected and the metrics it computed. Free-form but stable per check.
    evidence_refs: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    # PARTIAL checks populate this with the manual evidence still owed.
    # Each entry: {"step": str, "expected_artifact": str, "rationale": str}.
    manual_steps: list[dict[str, str]] = field(default_factory=list)

    # PARTIAL checks populate this with the automatable portion's outcome
    # so the operator can see what the runner actually proved.
    automated_finding: str = ""

    # ERROR populates this with the exception message; otherwise empty.
    error: str = ""

    # Free-form notes for the report.
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Stable serialisation for the report. Empty fields are omitted."""
        d: dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status,
            "classification": self.classification,
            "title": self.title,
            "control": self.control,
            "tier": self.tier,
        }
        for k in ("evidence_refs", "metrics", "manual_steps",
                  "automated_finding", "error", "notes"):
            v = getattr(self, k)
            if v:
                d[k] = v
        return d


class CheckRunner:
    """
    Base class for all conformance check implementations.

    Subclasses MUST set:
        check_id          str matching the Check01..Check19 naming.
        title             one-line title.
        control           primary GATE control id (e.g. "C05").
        classification    CLASS_AUTOMATED | CLASS_PARTIAL | CLASS_MANUAL.
        applicable_tiers  list of tier strings this check runs for.

    Subclasses MUST implement run().
    """

    check_id: ClassVar[str] = ""
    title: ClassVar[str] = ""
    control: ClassVar[str] = ""
    classification: ClassVar[str] = ""
    applicable_tiers: ClassVar[list[str]] = []

    def __init__(self, adapter, config: dict[str, Any]) -> None:
        self.adapter = adapter
        self.config = config

    # ------------------------------------------------------------------
    # Public entry point used by the runner. Wraps run() in tier-applicability
    # and exception handling so individual checks stay clean.
    # ------------------------------------------------------------------
    def execute(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        if tier not in self.applicable_tiers:
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_SKIP,
                classification=self.classification,
                title=self.title,
                control=self.control,
                tier=tier,
                notes=f"Not applicable at tier {tier!r}; applies to {self.applicable_tiers}.",
            )
        try:
            result = self.run(tenant_id=tenant_id, environment=environment, tier=tier)
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                check_id=self.check_id,
                status=STATUS_ERROR,
                classification=self.classification,
                title=self.title,
                control=self.control,
                tier=tier,
                error=f"{type(exc).__name__}: {exc}",
            )
        # Stamp the metadata onto the result so individual checks do not
        # have to remember to copy it.
        result.check_id = self.check_id
        result.classification = self.classification
        result.title = self.title
        result.control = self.control
        result.tier = tier
        return result

    # ------------------------------------------------------------------
    # Subclasses override this. Return a CheckResult with status,
    # evidence_refs, metrics, and (for PARTIAL) manual_steps populated.
    # Tier-applicability is already checked; do not re-check.
    # ------------------------------------------------------------------
    def run(self, tenant_id: str, environment: str, tier: str) -> CheckResult:
        raise NotImplementedError(
            f"{type(self).__name__}.run() must be implemented"
        )

    # ------------------------------------------------------------------
    # Helpers used by concrete check implementations.
    # ------------------------------------------------------------------
    def table(self, logical_name: str) -> str:
        """
        Resolve a logical table name to the concrete name used in the
        operator's evidence store. Honours config.table_name_overrides.
        """
        overrides = self.config.get("table_name_overrides", {}) or {}
        return overrides.get(logical_name, logical_name)

    def threshold(self, key: str, default: Any = None) -> Any:
        """Read a numeric threshold from config.thresholds with a fallback."""
        return self.config.get("thresholds", {}).get(key, default)
