# gate-conformance

**GATE conformance checks, self-assessment, operational runbooks, and conformance runner - v1.2.0**

19 conformance checks with test procedures and evidence requirements,
a fillable conformance report template, BigQuery evidence correlation
queries, 9 operational runbooks for Day-2 operations, and a runner
that automates 9 of the 19 checks against your evidence store.

Framework: https://deterministicagents.ai  
Organisation: https://github.com/deterministic-agents  
Documentation: CC BY 4.0 - Andrew Stevens · Code: MIT

---

## v1.2.0 (2026-06-16)

Adds the conformance runner: `python -m runner.cli run --config gate-conformance.yaml`.
Automates 9 of the 19 checks against your evidence store (Check01, 03,
04, 05, 08, 09, 10, 12, 13) and returns PARTIAL with structured
`manual_steps` for the other 10. Supports sqlite (built in) and
BigQuery (optional dependency). Runner output matches the v1.1
conformance report template shape. See `runner/README.md` for the full
quickstart and the per-tier behaviour notes on Check16, Check17, and
Check18.

---

## Contents

```
gate-conformance/
├── self_assessment.yaml              # 19 checks with test procedures
├── conformance_report_template.yaml  # Fillable report for audit submission
├── evidence_correlation.sql          # BigQuery queries for evidence chain traversal
├── operational_runbooks.yaml         # 9 Day-2 runbooks
├── runner/                           # Conformance runner CLI (v1.2.0)
│   ├── cli.py, config.py, report.py
│   ├── adapters/  (sqlite, BigQuery)
│   ├── checks/    (Check01..Check19)
│   └── README.md  (quickstart, tier behaviour, extension guide)
└── tests/runner/                     # 68 pytest cases against sqlite fixtures
```

---

## How to use

### Step 1 - Determine your autonomy tier

| Tier | Required checks |
|---|---|
| `sandbox` | Check04, Check08, Check12 |
| `bounded` | All sandbox + Check01-03, Check05-08, Check10-13, Check16-19 |
| `high_privilege` | All bounded + Check09, Check14, Check15 |

Check16-19 (the v1.3 controls) apply at `bounded` and `high_privilege`.
Check17 and Check18 branch on tier inside the check - see
`runner/README.md` for the per-tier behaviour notes.

### Step 2 - Work through self_assessment.yaml

For each check in your tier, follow the `test_procedure` instructions,
collect the listed `evidence_required` artifacts, and set `status` to
`PASS`, `FAIL`, or `NOT_APPLICABLE`.

### Step 3 - Fill in conformance_report_template.yaml

Complete the `deployment`, `checks`, `metrics`, and `retention_profile`
sections. Set `summary.overall_status` to `CONFORMANT`, `NON_CONFORMANT`,
or `PARTIAL`.

### Step 4 - Run evidence_correlation.sql

Run the queries against your evidence store (BigQuery or adapt for your
query engine). The most important query for conformance is the Check01
query - zero rows means zero tool calls without a policy decision record.

---

## Conformance checks at a glance

| Check | Control | What it verifies |
|---|---|---|
| Check01 | C05 | Zero tool executions without a policy decision record |
| Check02 | C05 | No bypass paths to tools (network + IAM + SDK) |
| Check03 | C01 | 100% verified workload identity on privileged requests |
| Check04 | C05 | Schema validation rejects malformed tool inputs |
| Check05 | C11 | Ledger chain integrity verifies PASS; WORM retention active |
| Check06 | C10 | Replay reproduces incident run with matching hashes |
| Check07 | C06 | Circuit breaker stops side effects within SLO |
| Check08 | C07 | Budget exhaustion denies tool calls (not just logs) |
| Check09 | C12 | 100% signature coverage for financial/irreversible/infra tools |
| Check10 | C01 | Memory ACLs enforced at retrieval time; cross-tenant blocked |
| Check11 | C08 | Poisoning detection quarantines injected documents |
| Check12 | C13 | Evidence chain traversable: semantic → ledger → policy → replay |
| Check13 | C03 | Policy bundle hash in evidence matches deployed bundle |
| Check14 | C09 | HITL-required tool calls blocked without signed approval |
| Check15 | C14 | Multi-agent messages: signature + nonce + expiry enforced |
| Check16 | C17 | Unenrolled workloads are detected and remediated within TTL |
| Check17 | C18 | Memory retrievals pass quality gates before reaching the model |
| Check18 | C19 | Model behaviour is baselined and monitored for drift at cadence |
| Check19 | C19/C16 | Drift and adversarial events are emitted as distinct ledger event types |

---

## Target metrics for CONFORMANT status

| Metric | Target |
|---|---|
| Tool calls without policy decision record | 0 |
| Bypass detections | 0 |
| Attestation coverage | 100% |
| Ledger integrity status | PASS |
| Replay success rate | ≥ 95% |
| Breaker containment SLO | ≥ 99% |
| High-impact signature coverage | 100% |
| HITL-required without approval | 0 |
| Cross-tenant memory violations | 0 |
| Unenrolled workload identities outside remediation TTL (C17) | 0 |
| Memory retrievals without a quality_decision_id at bounded+ (C18) | 0 |
| Days without a drift_decision event at bounded+ (C19) | 0 |
| Drift / adversarial event-type crossover events (C19/C16) | 0 |

---

## Operational runbooks

`operational_runbooks.yaml` contains the minimum set of Day-2 runbooks:

| Runbook | Trigger |
|---|---|
| RB-01 Break-glass stop | Suspected compromise, runaway execution, unsafe actions |
| RB-02 Policy bundle rollback | Policy change causes unexpected denials or allows |
| RB-03 Incident replay | Investigating a run, validating a fix before re-enabling |
| RB-04 HITL outage | HITL service unavailable; approver unavailability |
| RB-05 Invariant bundle update | New high-impact tool; financial limit adjustment |
| RB-06 Agent decommission | Agent purpose complete; version replacement; retirement |
| RB-07 C17 candidate backlog escalation | Discovered-but-unenrolled candidates exceed threshold or TTL expires |
| RB-08 C18 quality gate outage | Memory quality gate service unavailable or failing open |
| RB-09 C19 drift response | Drift threshold breach requires tier reduction or escalation |

Each runbook includes: trigger, severity, SLO, step-by-step actions,
evidence capture requirements, and exit criteria.

---

## Automated conformance runner

The CLI conformance runner ships in this release (v1.2.0). Run all 19
checks against your evidence store with:

```bash
python -m runner.cli run --config gate-conformance.yaml
```

The runner automates 9 of the 19 checks (Check01, 03, 04, 05, 08, 09,
10, 12, 13) and returns PARTIAL with structured `manual_steps` for the
other 10. PARTIAL is not failure - the report carries the specific
artefact each PARTIAL check still needs from the operator.

See `runner/README.md` for the full quickstart, per-tier behaviour
notes on Check16-18, exit codes, and how to add a custom check or
evidence-store backend.

`self_assessment.yaml` remains the normative manual baseline. The
runner and the self-assessment are designed to be used together:
runner output for the automatable subset, self-assessment for the
rest.

---

## v1.1.0 (2026-06-16)

Compatible with GATE v1.3. Adds Check16-Check19 (C17 / C18 / C19), seven new evidence correlation queries, and three new runbooks (RB-07 C17 candidate backlog, RB-08 C18 quality gate outage, RB-09 C19 drift response).

---

## Related repos

| Repo | What it is |
|---|---|
| [gate-contracts](https://github.com/deterministic-agents/gate-contracts) | JSON Schema contracts (canonical dependency) |
| [gate-python](https://github.com/deterministic-agents/gate-python) | Python reference library |
| [gate-policies](https://github.com/deterministic-agents/gate-policies) | OPA/Rego policy and invariant bundles |
| [gate](https://github.com/deterministic-agents/gate) | Framework paper, spec site source |
