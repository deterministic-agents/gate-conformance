# gate-conformance

**GATE conformance checks, self-assessment, and operational runbooks - v1.1.0**

19 conformance checks with test procedures and evidence requirements,
a fillable conformance report template, BigQuery evidence correlation
queries, and 9 operational runbooks for Day-2 operations.

Framework: https://deterministicagents.ai  
Organisation: https://github.com/deterministic-agents  
Documentation: CC BY 4.0 - Andrew Stevens · Code: MIT

---

## Contents

```
gate-conformance/
├── self_assessment.yaml              # 19 checks with test procedures
├── conformance_report_template.yaml  # Fillable report for audit submission
├── evidence_correlation.sql          # BigQuery queries for evidence chain traversal
└── operational_runbooks.yaml         # 9 Day-2 runbooks
```

---

## How to use

### Step 1 - Determine your autonomy tier

| Tier | Required checks |
|---|---|
| `sandbox` | Check04, Check08, Check12 |
| `bounded` | All sandbox + Check01–03, Check05–08, Check10–13 |
| `high_privilege` | All bounded + Check09, Check14, Check15 |

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

Each runbook includes: trigger, severity, SLO, step-by-step actions,
evidence capture requirements, and exit criteria.

---

## Automated conformance runner

The CLI conformance runner is in development and will be released with
GATE v1.3. Until then, `self_assessment.yaml` is the normative manual
verification baseline. Implementations assessed against this release will
be considered conformant with GATE v1.2.8 under the versioning policy.

---

## v1.1.0 (2026-06-16)

Compatible with GATE v1.3. Adds Check16-Check19 (C17 / C18 / C19), seven new evidence correlation queries, and three new runbooks (RB-07 C17 candidate backlog, RB-08 C18 quality gate outage, RB-09 C19 drift response). The conformance runner is in development and ships with v1.3.

---

## Related repos

| Repo | What it is |
|---|---|
| [gate-contracts](https://github.com/deterministic-agents/gate-contracts) | JSON Schema contracts (canonical dependency) |
| [gate-python](https://github.com/deterministic-agents/gate-python) | Python reference library |
| [gate-policies](https://github.com/deterministic-agents/gate-policies) | OPA/Rego policy and invariant bundles |
| [gate](https://github.com/deterministic-agents/gate) | Framework paper, spec site source |
