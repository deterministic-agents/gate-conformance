"""
gate-conformance CLI

Usage:
    gate-conformance run \\
        --config gate-conformance.yaml \\
        --environment prod \\
        --tenant acme-corp \\
        --tier bounded \\
        --output-format yaml \\
        --output-file report.yaml

Exit codes:
    0   all must-pass checks PASS (PARTIAL acceptable)
    1   one or more FAIL or ERROR
    2   config error
"""
from __future__ import annotations

import argparse
import os
import sys
from getpass import getuser
from pathlib import Path
from typing import Any

from . import (
    __version__ as RUNNER_VERSION,
    __gate_conformance_version__ as GATE_CONFORMANCE_VERSION,
    __gate_version__ as GATE_VERSION,
)
from .adapters import build_adapter
from .checks import REGISTRY
from .checks.base import STATUS_FAIL, STATUS_ERROR
from .config import Config
from .report import Report


EXIT_OK = 0
EXIT_NON_CONFORMANT = 1
EXIT_CONFIG_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate-conformance",
        description=(
            "Run the GATE v1.3 conformance checks against an evidence store. "
            "Produces a report compatible with conformance_report_template.yaml v1.1."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"gate-conformance runner {RUNNER_VERSION} "
            f"(gate-conformance {GATE_CONFORMANCE_VERSION}, GATE {GATE_VERSION})"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the conformance checks")
    run_p.add_argument("--config", required=True, help="Path to YAML config file")
    run_p.add_argument(
        "--environment",
        choices=("dev", "test", "prod"),
        help="Override config.environment",
    )
    run_p.add_argument("--tenant", help="Override config.tenant_id")
    run_p.add_argument(
        "--tier",
        choices=("sandbox", "bounded", "high_privilege"),
        help="Override config.autonomy_tier",
    )
    run_p.add_argument(
        "--output-format",
        choices=("yaml", "json"),
        default="yaml",
        help="Report serialisation format (default: yaml)",
    )
    run_p.add_argument(
        "--output-file",
        default="-",
        help="Where to write the report (- for stdout; default: -)",
    )
    run_p.add_argument(
        "--check",
        action="append",
        dest="checks",
        help="Limit to a specific check id (repeatable). Default: all checks.",
    )

    list_p = sub.add_parser("list", help="List available checks and their classification")
    list_p.add_argument(
        "--format",
        choices=("table", "yaml"),
        default="table",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        return _cmd_list(args.format)
    if args.command == "run":
        return _cmd_run(args)
    parser.error(f"Unknown command: {args.command}")
    return EXIT_CONFIG_ERROR


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _cmd_list(output_format: str) -> int:
    rows = []
    for check_id in sorted(REGISTRY):
        cls = REGISTRY[check_id]
        rows.append(
            {
                "id": cls.check_id,
                "title": cls.title,
                "control": cls.control,
                "classification": cls.classification,
                "tiers": cls.applicable_tiers,
            }
        )
    if output_format == "yaml":
        import yaml
        sys.stdout.write(yaml.safe_dump({"checks": rows}, sort_keys=False))
        return EXIT_OK
    # table
    widths = (8, 64, 6, 12)
    print(f"{'ID':<{widths[0]}}{'TITLE':<{widths[1]}}{'CTL':<{widths[2]}}{'CLASS':<{widths[3]}}TIERS")
    for r in rows:
        print(
            f"{r['id']:<{widths[0]}}"
            f"{r['title']:<{widths[1]}}"
            f"{r['control']:<{widths[2]}}"
            f"{r['classification']:<{widths[3]}}"
            f"{', '.join(r['tiers'])}"
        )
    return EXIT_OK


def _cmd_run(args) -> int:
    try:
        config = Config.from_file(args.config)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except (ValueError, KeyError) as exc:
        print(f"error: config invalid: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.environment:
        config.environment = args.environment
    if args.tenant:
        config.tenant_id = args.tenant
    if args.tier:
        config.autonomy_tier = args.tier

    try:
        adapter = build_adapter(config.evidence_store)
    except (ValueError, ImportError, FileNotFoundError) as exc:
        print(f"error: cannot build adapter: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    check_cfg = config.as_check_config()
    results = []
    selected = args.checks or sorted(REGISTRY)
    for check_id in selected:
        if check_id not in REGISTRY:
            print(f"error: unknown check id {check_id!r}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        cls = REGISTRY[check_id]
        check = cls(adapter=adapter, config=check_cfg)
        result = check.execute(
            tenant_id=config.tenant_id,
            environment=config.environment,
            tier=config.autonomy_tier,
        )
        results.append(result)

    adapter.close()

    report = Report.from_results(
        results=results,
        config=config,
        generated_by=os.environ.get("USER") or getuser(),
        runner_version=RUNNER_VERSION,
        gate_version=GATE_VERSION,
        gate_conformance_version=GATE_CONFORMANCE_VERSION,
    )

    if args.output_file == "-":
        sys.stdout.write(report.to_yaml() if args.output_format == "yaml" else report.to_json())
    else:
        out = report.write(args.output_file, args.output_format)
        print(f"Report written: {out}", file=sys.stderr)

    must_pass_failing = sum(
        1 for r in results if r.status in (STATUS_FAIL, STATUS_ERROR)
    )
    return EXIT_NON_CONFORMANT if must_pass_failing else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
