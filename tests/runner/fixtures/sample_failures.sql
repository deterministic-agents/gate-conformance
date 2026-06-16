-- sample_failures.sql
-- Deliberate failures for Check16-Check19. Loaded INSTEAD OF
-- sample_evidence_v13.sql in fail tests. Self-contained.
-- Each failure is isolated to one check where practical so a fail-test
-- for Check16 does not also fail Check17 by accident.

-- ---------------------------------------------------------------
-- v1.3 schema
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gate_tool_requests (
    request_hash TEXT PRIMARY KEY, run_id TEXT, trace_id TEXT,
    agent_instance_id TEXT, originating_identity TEXT, tenant_id TEXT, environment TEXT,
    tool_name TEXT, tool_category TEXT, tool_schema_hash TEXT,
    identity_verified INTEGER, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_memory_responses (
    response_id TEXT PRIMARY KEY, item_id TEXT, request_type TEXT,
    memory_decision_id TEXT, quality_decision_id TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_discovery_events (
    event_id TEXT PRIMARY KEY, candidate_hash TEXT, workload_identity TEXT,
    classifier_bundle_hash TEXT, tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_remediation_outcomes (
    event_id TEXT PRIMARY KEY, candidate_hash TEXT, outcome TEXT,
    owner_identity TEXT, exception_ttl_expires_at TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_c04_inventory (
    agent_instance_id TEXT PRIMARY KEY, state TEXT, autonomy_tier TEXT,
    current_abom_hash TEXT, tenant_id TEXT, environment TEXT
);
CREATE TABLE IF NOT EXISTS gate_classifier_bundles (
    bundle_hash TEXT PRIMARY KEY, signed_at TEXT
);
CREATE TABLE IF NOT EXISTS gate_quality_bundles (
    bundle_hash TEXT PRIMARY KEY, tenant_id TEXT, is_active INTEGER, action_matrix TEXT
);
CREATE TABLE IF NOT EXISTS gate_quality_decisions (
    decision_id TEXT PRIMARY KEY, quality_bundle_hash TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_drift_decisions (
    event_id TEXT PRIMARY KEY, event_type TEXT, agent_instance_id TEXT,
    dimension TEXT, decision TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_response_actions (
    event_id TEXT PRIMARY KEY, drift_decision_id TEXT, action TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_adversarial_outcomes (
    event_id TEXT PRIMARY KEY, event_type TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_baselines (
    baseline_hash TEXT PRIMARY KEY, created_at TEXT
);
CREATE TABLE IF NOT EXISTS gate_abom (
    agent_instance_id TEXT, current_baseline_hash TEXT, is_current INTEGER, tenant_id TEXT
);
CREATE TABLE IF NOT EXISTS gate_agent_state (
    agent_instance_id TEXT PRIMARY KEY, state TEXT, autonomy_tier TEXT,
    tenant_id TEXT, environment TEXT
);

-- ---------------------------------------------------------------
-- Classifier bundle is signed - this lets us isolate the Check16
-- failure to the reconciliation delta rather than an unsigned bundle.
-- ---------------------------------------------------------------
INSERT INTO gate_classifier_bundles VALUES
  ('sha256:classifier-v1', datetime('now', '-20 days'));

INSERT INTO gate_discovery_events VALUES
  ('de-1', 'cand-1', 'spiffe://acme/agent/planner', 'sha256:classifier-v1',
   'acme-corp', 'prod', datetime('now', '-5 days'));

-- ---------------------------------------------------------------
-- CHECK16 FAILURE
-- Unenrolled identity in the tool stream older than the remediation TTL
-- window. spiffe://acme/agent/shadow is NOT in the C04 inventory and has
-- NO active exception. first_seen is well outside the 72h TTL.
-- ---------------------------------------------------------------
INSERT INTO gate_tool_requests VALUES
  ('sha256:fail-001', 'run-f-1', 'tr-f-1',
   'spiffe://acme/agent/shadow', 'spiffe://acme/gateway/tool-gateway',
   'acme-corp', 'prod', 'crm.lookup', 'read_only', 'sha256:tool-schema-v1', 1,
   datetime('now', '-10 days')),
  -- Also include a legitimate agent so the tool stream is not empty.
  ('sha256:fail-002', 'run-f-2', 'tr-f-2',
   'spiffe://acme/agent/planner', 'spiffe://acme/gateway/tool-gateway',
   'acme-corp', 'prod', 'crm.lookup', 'read_only', 'sha256:tool-schema-v1', 1,
   datetime('now', '-1 days'));

-- Only the legitimate agent is in C04.
INSERT INTO gate_c04_inventory VALUES
  ('spiffe://acme/agent/planner', 'Run', 'bounded', 'sha256:abom-planner-v1', 'acme-corp', 'prod');

-- No remediation outcome for cand-shadow -> reconciliation delta = 1.

-- ---------------------------------------------------------------
-- CHECK17 FAILURE
-- A memory_response WITHOUT quality_decision_id. Coverage < 100%.
-- ---------------------------------------------------------------
INSERT INTO gate_memory_responses VALUES
  ('mrf-1', 'item-a', 'read', 'mdec-1', 'qdec-1',         'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mrf-2', 'item-b', 'read', 'mdec-2', NULL,             'acme-corp', 'prod', datetime('now', '-1 days'));

INSERT INTO gate_quality_decisions VALUES
  ('qdec-1', 'sha256:quality-v1', 'acme-corp', 'prod', datetime('now', '-1 days'));

INSERT INTO gate_quality_bundles VALUES (
  'sha256:quality-v1', 'acme-corp', 1,
  '{"bounded":{"legal_text":{"freshness":"deny","confidence":"deny","provenance":"flag"}}}'
);

-- ---------------------------------------------------------------
-- CHECK18 FAILURE
-- agent_state present, baseline tied to ABOM, BUT no drift_decision
-- events in the assessment window. Bounded tier requires drift cadence
-- evidence; absence = FAIL.
-- ---------------------------------------------------------------
INSERT INTO gate_agent_state VALUES
  ('spiffe://acme/agent/planner', 'Run', 'bounded', 'acme-corp', 'prod');

INSERT INTO gate_baselines VALUES
  ('sha256:baseline-v1', datetime('now', '-10 days'));

INSERT INTO gate_abom VALUES
  ('spiffe://acme/agent/planner', 'sha256:baseline-v1', 1, 'acme-corp');

-- Deliberately no rows in gate_drift_decisions for the planner agent.

-- ---------------------------------------------------------------
-- CHECK19 FAILURE
-- Crossover: a row in the adversarial table tagged with the drift
-- event_type. The crossover query catches this.
-- ---------------------------------------------------------------
INSERT INTO gate_drift_decisions VALUES
  ('dd-x-1', 'gate.assurance.drift_decision', 'spiffe://acme/agent/treasury',
   'tool_choice', 'no_drift', 'acme-corp', 'prod', datetime('now', '-2 days'));

INSERT INTO gate_adversarial_outcomes VALUES
  ('ao-x-1', 'gate.assurance.adversarial_outcome', 'acme-corp', 'prod', datetime('now', '-3 days')),
  -- This row is the crossover: an adversarial-outcome row tagged as drift_decision.
  ('ao-x-2', 'gate.assurance.drift_decision',     'acme-corp', 'prod', datetime('now', '-2 days'));
