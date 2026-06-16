# gate-conformance runner

Automates the automatable subset of GATE Check01-Check19 against your evidence store and produces a conformance report compatible with `conformance_report_template.yaml` v1.1.

Compatible with: GATE v1.3, gate-conformance v1.1.0.

## Install

The runner ships inside `gate-conformance`. From a clone of the repo:

```bash
pip install pyyaml                                   # core
pip install google-cloud-bigquery                    # only if using the BigQuery adapter
```

There is no separate package - run the CLI as a module:

```bash
python -m runner.cli --version
```

## Quickstart

```bash
# Copy the template and edit it for your environment.
cp runner/templates/config.example.yaml gate-conformance.yaml
$EDITOR gate-conformance.yaml

# List the registered checks and their classification.
python -m runner.cli list

# Run all 19 checks against the evidence store.
python -m runner.cli run \
    --config gate-conformance.yaml \
    --output-format yaml \
    --output-file report.yaml
```

## Config

See `runner/templates/config.example.yaml` for a working starting point. Required keys: `evidence_store.type` (`sqlite` or `bigquery`), `tenant_id`, `environment`, `autonomy_tier`. Everything else has defaults that match the `conformance_report_template.yaml` v1.1 metrics block.

Override the runner's logical table names with `table_name_overrides:` if your evidence store uses a different schema.

## Exit codes

- `0` - all must-pass checks PASS. PARTIAL results are acceptable.
- `1` - one or more checks FAIL or ERROR.
- `2` - config invalid or adapter cannot be constructed.

## What PARTIAL means

10 of the 19 checks are PARTIAL by design (Check02, 06, 07, 11, 14, 15, 16, 17, 18, 19). PARTIAL is not failure - it means the runner ran the automatable portion against your evidence store and the remaining evidence must be supplied by hand.

For each PARTIAL result, the report includes a `manual_steps` list:

```yaml
- check_id: Check07
  status: PARTIAL
  automated_finding: "Breaker triggers: 4. Stop activations: 4. Containment SLO: 30s (manual)."
  manual_steps:
    - step: "Execute a breaker containment drill"
      expected_artifact: "Drill record showing drill_id, scenario, breaker_trigger_time, ..."
      rationale: "Containment time cannot be measured from production traffic alone."
```

When you have the manual artefacts, attach them to the report and flip the status to PASS for the operator's submission. The runner stays the source of truth for the automated portion only.

For the full test procedure and pass criteria for every check, read `self_assessment.yaml`.

## Tier behaviour

Checks declare which tiers they apply to. A check that does not apply at the current tier returns `SKIP` and still appears in the report so the audit surface is visible.

Three checks branch on tier inside the check (Check16, Check17, Check18):

- **Check16** at `sandbox` accepts observe-only discovery as PASS. At `bounded` or `high_privilege` it requires the enforce-mode reconciliation delta to be zero and the classifier bundle to be signed.
- **Check17** at `bounded` requires `freshness` and `confidence` to be configured as `deny` for at least one content class in the active quality bundle. At `high_privilege` the bundle must additionally enforce `provenance`. The runner reads the bundle's action matrix - it does not assume enforcement based on event presence alone.
- **Check18** at `bounded` requires drift_decision events emitting at cadence. At `high_privilege` it additionally requires at least one observed `tier_reduction` or `emergency_stop` response action - log-only alone fails.

## Adding a check

1. Implement the check class under `runner/checks/checkXX.py`. Subclass `CheckRunner`, set the class attributes, implement `run()`. Wrap the body in `try/except` and return `STATUS_ERROR` on failure - never raise.
2. Import the class in `runner/checks/__init__.py` and add it to `REGISTRY`.
3. Add fixtures to `tests/runner/fixtures/sample_evidence*.sql` and tests to `tests/runner/test_checks.py`.

## Adding an evidence store backend

1. Subclass `EvidenceAdapter` under `runner/adapters/<name>.py`. Implement `query()` and `scalar()` only.
2. Register in `runner/adapters/__init__.py` under `ADAPTERS`.

Checks call `self.adapter.query()` and `self.adapter.scalar()` only. They do not import any backend library. Anything that runs against sqlite runs against BigQuery without modification.

## Tests

```bash
pip install pytest pyyaml
PYTHONPATH=. python -m pytest tests/runner/ -v
```

The fixtures (`sample_evidence.sql`, `sample_evidence_v13.sql`, `sample_failures.sql`) are self-contained: each carries its own `CREATE TABLE IF NOT EXISTS` statements so the adapter does not have to know the schema.
