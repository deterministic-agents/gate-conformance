-- GATE Evidence Correlation Queries
-- Compatible with: BigQuery (adapt syntax for your query engine)
-- Purpose: Traverse the evidence chain for audit, incident response,
--          and conformance verification.
--
-- Table naming convention assumed:
--   gate_policy_decisions        -  policy decision records
--   gate_tool_requests           -  tool request envelopes
--   gate_tool_responses          -  tool response envelopes
--   gate_ledger_events           -  audit ledger events
--   gate_replay_traces           -  replay trace summaries
--   gate_replay_steps            -  individual replay trace steps
--   gate_semantic_traces         -  semantic observability events
--   gate_hitl_decisions          -  HITL decision records
--   gate_breaker_events          -  circuit breaker trigger events
--   gate_budget_events           -  budget/quota enforcement events
--   gate_memory_decisions        -  memory gateway ACL decisions
--   gate_memory_quarantine       -  memory poisoning quarantine events
--
-- Adapt table names and schema to your actual evidence store schema.


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 01: Zero tool executions without a policy decision record
-- Target: 0 rows
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  t.run_id,
  t.trace_id,
  t.agent_instance_id,
  t.tool_name,
  t.request_hash,
  t.time AS request_time
FROM gate_tool_requests t
LEFT JOIN gate_policy_decisions p
  ON t.request_hash = p.request_hash
WHERE p.decision_id IS NULL
  AND t.environment = 'prod'
  AND t.time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
ORDER BY t.time DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- FULL EVIDENCE CHAIN: from run_id to complete correlated evidence
-- Use for incident investigation or audit sample
-- ─────────────────────────────────────────────────────────────────────────────

-- Replace 'your-run-id-here' with the run_id under investigation
DECLARE run_id_param STRING DEFAULT 'your-run-id-here';

SELECT
  t.time                        AS request_time,
  t.agent_instance_id,
  t.tool_name,
  t.tool_category,
  t.request_hash,
  p.decision_id,
  p.decision,
  p.reason_codes,
  p.policy_bundle_hash,
  r.response_hash,
  r.status                      AS tool_status,
  r.snapshot_uri,
  l.ledger_event_id,
  l.hash_chain.event_hash       AS ledger_event_hash,
  l.hash_chain.prev_event_hash  AS prev_ledger_hash,
  l.immutability.sink_uri       AS worm_uri,
  rs.step_index                 AS replay_step,
  rs.step_type,
  s.intent                      AS semantic_intent,
  s.audit_ref                   AS semantic_audit_ref

FROM gate_tool_requests t
LEFT JOIN gate_policy_decisions p
  ON t.request_hash = p.request_hash AND t.run_id = p.run_id
LEFT JOIN gate_tool_responses r
  ON t.run_id = r.run_id AND t.trace_id = r.trace_id
LEFT JOIN gate_ledger_events l
  ON l.references.policy_decision_id = p.decision_id
LEFT JOIN gate_replay_steps rs
  ON rs.run_id = t.run_id AND rs.request_hash = t.request_hash
LEFT JOIN gate_semantic_traces s
  ON s.run_id = t.run_id AND s.audit_ref = l.ledger_event_id

WHERE t.run_id = run_id_param
ORDER BY t.time, rs.step_index;


-- ─────────────────────────────────────────────────────────────────────────────
-- LEDGER INTEGRITY: Find hash chain gaps or sequence number discontinuities
-- Target: 0 rows (any row indicates potential tampering)
-- ─────────────────────────────────────────────────────────────────────────────

WITH ordered_events AS (
  SELECT
    ledger_event_id,
    sequence_number,
    hash_chain.prev_event_hash,
    hash_chain.event_hash,
    LAG(hash_chain.event_hash) OVER (
      PARTITION BY tenant_id, environment
      ORDER BY sequence_number
    ) AS prev_computed_hash,
    LAG(sequence_number) OVER (
      PARTITION BY tenant_id, environment
      ORDER BY sequence_number
    ) AS prev_sequence_number,
    time
  FROM gate_ledger_events
  WHERE environment = 'prod'
)
SELECT
  ledger_event_id,
  sequence_number,
  prev_event_hash,
  prev_computed_hash,
  CASE
    WHEN prev_event_hash != prev_computed_hash THEN 'HASH_CHAIN_BREAK'
    WHEN sequence_number != prev_sequence_number + 1 THEN 'SEQUENCE_GAP'
    ELSE 'OK'
  END AS integrity_status
FROM ordered_events
WHERE
  (prev_event_hash != prev_computed_hash AND prev_event_hash != 'GENESIS')
  OR (sequence_number != prev_sequence_number + 1)
ORDER BY sequence_number;


-- ─────────────────────────────────────────────────────────────────────────────
-- ORM RISK DISTRIBUTION: Understand score distribution across recent runs
-- Use to calibrate thresholds in Artifact A7
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  tool_category,
  COUNT(*) AS total_decisions,
  ROUND(AVG(inputs.orm_risk_score), 3) AS avg_orm_score,
  ROUND(APPROX_QUANTILES(inputs.orm_risk_score, 100)[OFFSET(50)], 3) AS p50,
  ROUND(APPROX_QUANTILES(inputs.orm_risk_score, 100)[OFFSET(90)], 3) AS p90,
  ROUND(APPROX_QUANTILES(inputs.orm_risk_score, 100)[OFFSET(95)], 3) AS p95,
  ROUND(APPROX_QUANTILES(inputs.orm_risk_score, 100)[OFFSET(99)], 3) AS p99,
  COUNTIF(inputs.orm_risk_score >= 0.65) AS hitl_threshold_breaches,
  COUNTIF(inputs.orm_risk_score >= 0.85) AS block_threshold_breaches
FROM gate_policy_decisions
WHERE environment = 'prod'
  AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY tool_category
ORDER BY avg_orm_score DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- HITL DECISION AUDIT: All approval decisions in the last 30 days
-- Use for: HITL gate compliance, approval fatigue monitoring
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  h.approval_id,
  h.run_id,
  h.request.tool_name,
  h.context.orm_risk_score,
  h.decision.approver_id,
  h.decision.action,
  h.decision.justification,
  h.time AS decision_time,
  TIMESTAMP_DIFF(h.time, p.time, SECOND) AS seconds_to_approve,
  h.evidence.ledger_event_id,
  h.evidence.signature IS NOT NULL AS is_signed
FROM gate_hitl_decisions h
LEFT JOIN gate_policy_decisions p
  ON h.context.policy_decision_id = p.decision_id
WHERE h.environment = 'prod'
  AND h.time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
ORDER BY h.time DESC;


-- Approval fatigue signal: flag approvers with high approval rate and fast decisions
-- High rubber-stamp risk: > 95% approve rate AND < 30s average decision time

SELECT
  decision.approver_id,
  COUNT(*) AS total_decisions,
  COUNTIF(decision.action = 'approve') AS approvals,
  COUNTIF(decision.action = 'deny') AS denials,
  ROUND(COUNTIF(decision.action = 'approve') / COUNT(*) * 100, 1) AS approval_rate_pct,
  ROUND(AVG(
    TIMESTAMP_DIFF(h.time, p.time, SECOND)
  ), 0) AS avg_seconds_to_decide
FROM gate_hitl_decisions h
LEFT JOIN gate_policy_decisions p
  ON h.context.policy_decision_id = p.decision_id
WHERE h.environment = 'prod'
  AND h.time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY decision.approver_id
HAVING approval_rate_pct > 95 AND avg_seconds_to_decide < 30
ORDER BY approval_rate_pct DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- BREAKER EVENTS: Circuit breaker trigger history with containment timing
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  b.time AS triggered_at,
  b.agent_instance_id,
  b.trigger_cause,
  b.threshold_value,
  b.actual_value,
  b.containment_outcome,
  b.time_to_effective_stop_ms,
  b.affected_run_ids
FROM gate_breaker_events b
WHERE b.environment = 'prod'
  AND b.time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
ORDER BY b.time DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- MEMORY QUARANTINE: Poisoning detection events
-- Target: all quarantine events reviewed within 24h
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  q.time AS quarantined_at,
  q.memory_partition,
  q.document_ref,
  q.cause_codes,
  q.provenance_refs,
  q.detection_confidence,
  q.reviewed_by,
  q.review_outcome,
  TIMESTAMP_DIFF(q.reviewed_at, q.time, HOUR) AS hours_to_review
FROM gate_memory_quarantine q
WHERE q.environment = 'prod'
ORDER BY q.time DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- SPEND ANOMALY: Detect runs with unusual cost or tool call volume
-- Useful for C07 economic safety monitoring
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  run_id,
  agent_instance_id,
  SUM(cost_usd) AS total_cost_usd,
  COUNT(*) AS total_tool_calls,
  COUNTIF(tool_category IN ('financial', 'irreversible_write', 'infrastructure')) AS high_impact_calls,
  MIN(time) AS run_start,
  MAX(time) AS run_end,
  TIMESTAMP_DIFF(MAX(time), MIN(time), SECOND) AS run_duration_seconds
FROM gate_tool_requests
WHERE environment = 'prod'
  AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY run_id, agent_instance_id
HAVING
  total_cost_usd > 5.0          -- flag runs over $5
  OR total_tool_calls > 100     -- flag high-volume runs
  OR high_impact_calls > 5      -- flag runs with many high-impact calls
ORDER BY total_cost_usd DESC;
-- GATE Evidence Correlation Queries - v1.1.0 additions
-- Append these queries to evidence_correlation.sql for GATE v1.3.
-- Table naming convention follows the existing v1.0.0 set:
--   gate_discovery_events           (gate.discovery.agent_discovered)
--   gate_remediation_outcomes       (gate.discovery.agent_remediation_outcome)
--   gate_c04_inventory              (current C04 lifecycle records)
--   gate_memory_responses           (memory response envelopes incl. quality_decision_id)
--   gate_quality_decisions          (gate.memory.quality_decision)
--   gate_quality_bundles            (signed quality bundle versions)
--   gate_baselines                  (signed behavioural baselines)
--   gate_drift_decisions            (gate.assurance.drift_decision)
--   gate_response_actions           (gate.assurance.response_action)
--   gate_adversarial_outcomes       (gate.assurance.adversarial_outcome - C16)
--   gate_abom                       (ABOM records)
--   gate_agent_state                (C04 lifecycle states incl. Discovered)


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 16 - Query 1: Unenrolled identity reconciliation
-- Identities present in the tool API stream but not in the C04 inventory,
-- outside the active remediation TTL window. Target: 0 rows.
-- ─────────────────────────────────────────────────────────────────────────────

WITH active_exceptions AS (
  SELECT
    candidate_hash,
    workload_identity,
    exception_ttl_expires_at
  FROM gate_remediation_outcomes
  WHERE outcome = 'exception'
    AND exception_ttl_expires_at > CURRENT_TIMESTAMP()
),
recent_tool_callers AS (
  SELECT DISTINCT agent_instance_id AS workload_identity
  FROM gate_tool_requests
  WHERE environment = 'prod'
    AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
)
SELECT
  rtc.workload_identity,
  'unenrolled - no C04 record and no active exception' AS finding
FROM recent_tool_callers rtc
LEFT JOIN gate_c04_inventory c04
  ON rtc.workload_identity = c04.agent_instance_id
LEFT JOIN active_exceptions ax
  ON rtc.workload_identity = ax.workload_identity
WHERE c04.agent_instance_id IS NULL
  AND ax.workload_identity IS NULL;


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 16 - Query 2: Classifier coverage per observation window
-- Percentage of governed workload identities scanned by the C17 classifier
-- per 24-hour observation window. Target: 100%.
-- ─────────────────────────────────────────────────────────────────────────────

WITH governed_identities AS (
  SELECT DISTINCT agent_instance_id AS workload_identity
  FROM gate_tool_requests
  WHERE environment = 'prod'
    AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
),
scanned_identities AS (
  SELECT DISTINCT JSON_EXTRACT_SCALAR(candidate_payload, '$.workload_identity') AS workload_identity
  FROM gate_discovery_events
  WHERE environment = 'prod'
    AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
)
SELECT
  COUNT(DISTINCT g.workload_identity) AS total_governed,
  COUNT(DISTINCT s.workload_identity) AS scanned,
  SAFE_DIVIDE(COUNT(DISTINCT s.workload_identity) * 100.0,
              COUNT(DISTINCT g.workload_identity)) AS coverage_pct
FROM governed_identities g
LEFT JOIN scanned_identities s
  ON g.workload_identity = s.workload_identity;


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 17 - Query 3: Quality decision coverage
-- Count of memory retrievals returned with and without a quality_decision_id.
-- Target: zero without.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  COUNT(*) AS total_retrievals,
  COUNT(quality_decision_id) AS retrievals_with_quality_decision,
  COUNT(*) - COUNT(quality_decision_id) AS retrievals_without_quality_decision,
  SAFE_DIVIDE(COUNT(quality_decision_id) * 100.0, COUNT(*)) AS coverage_pct
FROM gate_memory_responses
WHERE environment = 'prod'
  AND request_type = 'read'
  AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY);


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 17 - Query 4: Quality bundle version consistency
-- Verify the quality_bundle_hash recorded in every quality_decision event
-- matches a known, signed bundle version.
-- Target: zero unknown hashes.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  qd.quality_bundle_hash,
  COUNT(*) AS decisions_referencing_unknown_bundle
FROM gate_quality_decisions qd
LEFT JOIN gate_quality_bundles qb
  ON qd.quality_bundle_hash = qb.bundle_hash
WHERE qb.bundle_hash IS NULL
  AND qd.environment = 'prod'
  AND qd.time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY qd.quality_bundle_hash;


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 18 - Query 5: Baseline currency per agent
-- Agents at bounded tier or above whose current baseline is missing or
-- exceeds the configured maximum age. Replace @max_age_days at runtime
-- (recommend 90).
-- Target: 0 rows.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
  agent.agent_instance_id,
  agent.autonomy_tier,
  CASE
    WHEN b.created_at IS NULL THEN 'no_baseline'
    WHEN TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), b.created_at, DAY) > @max_age_days
      THEN 'baseline_stale'
    ELSE 'ok'
  END AS finding,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), b.created_at, DAY) AS baseline_age_days
FROM gate_agent_state agent
LEFT JOIN gate_abom a
  ON agent.agent_instance_id = a.agent_instance_id
  AND a.is_current = TRUE
LEFT JOIN gate_baselines b
  ON a.current_baseline_hash = b.baseline_hash
WHERE agent.autonomy_tier IN ('bounded', 'high_privilege')
  AND agent.state = 'Run'
  AND (
    b.baseline_hash IS NULL
    OR TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), b.created_at, DAY) > @max_age_days
  );


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 18 - Query 6: Drift decision cadence gaps
-- Gaps between consecutive drift_decision events per (agent, dimension)
-- exceeding the configured cadence (replace @cadence_hours, recommend 24).
-- Target: 0 rows.
-- ─────────────────────────────────────────────────────────────────────────────

WITH ordered AS (
  SELECT
    JSON_EXTRACT_SCALAR(payload, '$.agent_instance_id') AS agent_instance_id,
    dimension,
    time,
    LAG(time) OVER (
      PARTITION BY JSON_EXTRACT_SCALAR(payload, '$.agent_instance_id'), dimension
      ORDER BY time
    ) AS previous_time
  FROM gate_drift_decisions
  WHERE environment = 'prod'
    AND time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
)
SELECT
  agent_instance_id,
  dimension,
  previous_time,
  time AS current_time,
  TIMESTAMP_DIFF(time, previous_time, HOUR) AS gap_hours
FROM ordered
WHERE previous_time IS NOT NULL
  AND TIMESTAMP_DIFF(time, previous_time, HOUR) > @cadence_hours;


-- ─────────────────────────────────────────────────────────────────────────────
-- CHECK 19 - Query 7: Event type distinction (C16 vs C19)
-- Both ledger event types must be observable within the assessment window
-- with zero crossover. Returns one row summarising counts.
-- Target: c19_drift > 0, c16_adversarial > 0, crossover = 0.
-- ─────────────────────────────────────────────────────────────────────────────

WITH window AS (
  SELECT TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) AS window_start
),
drift AS (
  SELECT COUNT(*) AS c19_drift_count
  FROM gate_drift_decisions
  WHERE environment = 'prod'
    AND time >= (SELECT window_start FROM window)
),
adversarial AS (
  SELECT COUNT(*) AS c16_adversarial_count
  FROM gate_adversarial_outcomes
  WHERE environment = 'prod'
    AND time >= (SELECT window_start FROM window)
),
crossover AS (
  -- Any drift_decision event_type appearing in the adversarial table,
  -- or vice versa. Should be impossible under a correct implementation.
  SELECT COUNT(*) AS crossover_count
  FROM gate_adversarial_outcomes
  WHERE event_type = 'gate.assurance.drift_decision'
  UNION ALL
  SELECT COUNT(*) AS crossover_count
  FROM gate_drift_decisions
  WHERE event_type = 'gate.assurance.adversarial_outcome'
)
SELECT
  d.c19_drift_count,
  a.c16_adversarial_count,
  (SELECT SUM(crossover_count) FROM crossover) AS crossover_count
FROM drift d, adversarial a;
