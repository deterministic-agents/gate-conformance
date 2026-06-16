"""
gate-conformance runner
=======================
Automates the automatable subset of GATE Check01-Check19 against a
GATE evidence store, and surfaces a structured manual_steps payload
for the rest.

Compatible with: gate-conformance v1.2.0 (GATE v1.3).

Classification:
    9 AUTOMATED: Check01, 03, 04, 05, 08, 09, 10, 12, 13
    10 PARTIAL:  Check02, 06, 07, 11, 14, 15, 16, 17, 18, 19
    0 MANUAL

PARTIAL is not failure. It means "the runner did everything it could
from the evidence store; here is the manual evidence still owed".

Public surface:
    runner.cli.main         - CLI entry point.
    runner.config.Config    - Loaded configuration.
    runner.report.Report    - Conformance report writer.
    runner.checks.REGISTRY  - Check class registry keyed by check_id.
    runner.adapters         - Evidence store adapters (sqlite, bigquery).
"""

__version__ = "1.0.0"
__gate_conformance_version__ = "1.2.0"
__gate_version__ = "1.3"
