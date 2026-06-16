-- sample_evidence_v13.sql
-- Passing bounded-tier evidence for Check16-Check19.
-- Self-contained: CREATE TABLE statements at the top, INSERTs below.
-- Tenant: acme-corp, environment: prod.

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
-- Tool request stream: two agents calling registered tools.
-- These workload identities MUST be in the C04 inventory below for the
-- Check16 reconciliation to come out clean.
-- ---------------------------------------------------------------
INSERT INTO gate_tool_requests VALUES
  ('sha256:v13-001', 'run-v13-1', 'tr-v13-1',
   'spiffe://acme/agent/planner', 'spiffe://acme/gateway/tool-gateway',
   'acme-corp', 'prod', 'crm.lookup', 'read_only', 'sha256:tool-schema-v1', 1,
   datetime('now', '-2 days')),
  ('sha256:v13-002', 'run-v13-2', 'tr-v13-2',
   'spiffe://acme/agent/treasury', 'spiffe://acme/gateway/tool-gateway',
   'acme-corp', 'prod', 'transfer_funds', 'financial', 'sha256:tool-schema-v1', 1,
   datetime('now', '-1 days'));

-- ---------------------------------------------------------------
-- C04 inventory contains exactly the same workload identities. The
-- reconciliation delta outside the TTL window is zero -> Check16 clean.
-- ---------------------------------------------------------------
INSERT INTO gate_c04_inventory VALUES
  ('spiffe://acme/agent/planner',  'Run', 'bounded', 'sha256:abom-planner-v1',  'acme-corp', 'prod'),
  ('spiffe://acme/agent/treasury', 'Run', 'bounded', 'sha256:abom-treasury-v1', 'acme-corp', 'prod');

-- ---------------------------------------------------------------
-- Classifier bundle is signed.
-- ---------------------------------------------------------------
INSERT INTO gate_classifier_bundles VALUES
  ('sha256:classifier-v1', datetime('now', '-20 days'));

-- ---------------------------------------------------------------
-- Discovery events: a few candidates, all enrolled below.
-- ---------------------------------------------------------------
INSERT INTO gate_discovery_events VALUES
  ('de-1', 'cand-1', 'spiffe://acme/agent/planner',  'sha256:classifier-v1', 'acme-corp', 'prod', datetime('now', '-5 days')),
  ('de-2', 'cand-2', 'spiffe://acme/agent/treasury', 'sha256:classifier-v1', 'acme-corp', 'prod', datetime('now', '-5 days'));

INSERT INTO gate_remediation_outcomes VALUES
  ('ro-1', 'cand-1', 'enrolled', 'spiffe://acme/agent/planner',  NULL, 'acme-corp', 'prod', datetime('now', '-5 days')),
  ('ro-2', 'cand-2', 'enrolled', 'spiffe://acme/agent/treasury', NULL, 'acme-corp', 'prod', datetime('now', '-5 days'));

-- ---------------------------------------------------------------
-- Quality bundle: bounded tier enforces freshness + confidence as deny
-- on at least one content_class. provenance stays flag at bounded.
-- ---------------------------------------------------------------
INSERT INTO gate_quality_bundles VALUES (
  'sha256:quality-v1', 'acme-corp', 1,
  '{"bounded":{"legal_text":{"freshness":"deny","confidence":"deny","provenance":"flag"}},"high_privilege":{"legal_text":{"freshness":"deny","confidence":"deny","provenance":"deny"}}}'
);

-- ---------------------------------------------------------------
-- Memory responses: every read carries a quality_decision_id.
-- ---------------------------------------------------------------
INSERT INTO gate_memory_responses VALUES
  ('mrv-1', 'item-a', 'read', 'mdec-v-1', 'qdec-1', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mrv-2', 'item-b', 'read', 'mdec-v-2', 'qdec-2', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mrv-3', 'item-c', 'read', 'mdec-v-3', 'qdec-3', 'acme-corp', 'prod', datetime('now', '-12 hours'));

INSERT INTO gate_quality_decisions VALUES
  ('qdec-1', 'sha256:quality-v1', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('qdec-2', 'sha256:quality-v1', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('qdec-3', 'sha256:quality-v1', 'acme-corp', 'prod', datetime('now', '-12 hours'));

-- ---------------------------------------------------------------
-- Baseline currency: agent_state, ABOM, baselines.
-- Bounded-tier agent in Run state, with a baseline created 10 days ago
-- (within the 90d max-age default).
-- ---------------------------------------------------------------
INSERT INTO gate_agent_state VALUES
  ('spiffe://acme/agent/planner',  'Run', 'bounded', 'acme-corp', 'prod'),
  ('spiffe://acme/agent/treasury', 'Run', 'bounded', 'acme-corp', 'prod');

INSERT INTO gate_baselines VALUES
  ('sha256:baseline-v1', datetime('now', '-10 days')),
  ('sha256:baseline-v2', datetime('now', '-8 days'));

INSERT INTO gate_abom VALUES
  ('spiffe://acme/agent/planner',  'sha256:baseline-v1', 1, 'acme-corp'),
  ('spiffe://acme/agent/treasury', 'sha256:baseline-v2', 1, 'acme-corp');

-- ---------------------------------------------------------------
-- Drift decisions: cadence within 24h, decision = no_drift.
-- Bounded tier passes with log-only responses.
-- ---------------------------------------------------------------
INSERT INTO gate_drift_decisions VALUES
  ('dd-1', 'gate.assurance.drift_decision', 'spiffe://acme/agent/planner',
   'tool_choice', 'no_drift', 'acme-corp', 'prod', datetime('now', '-3 days')),
  ('dd-2', 'gate.assurance.drift_decision', 'spiffe://acme/agent/planner',
   'tool_choice', 'no_drift', 'acme-corp', 'prod', datetime('now', '-2 days')),
  ('dd-3', 'gate.assurance.drift_decision', 'spiffe://acme/agent/planner',
   'tool_choice', 'no_drift', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('dd-4', 'gate.assurance.drift_decision', 'spiffe://acme/agent/treasury',
   'output_length', 'no_drift', 'acme-corp', 'prod', datetime('now', '-3 days')),
  ('dd-5', 'gate.assurance.drift_decision', 'spiffe://acme/agent/treasury',
   'output_length', 'no_drift', 'acme-corp', 'prod', datetime('now', '-2 days')),
  ('dd-6', 'gate.assurance.drift_decision', 'spiffe://acme/agent/treasury',
   'output_length', 'no_drift', 'acme-corp', 'prod', datetime('now', '-1 days'));

-- Response actions: at least one tier_reduction so high-privilege tier
-- tests can pass if the same fixture is reused.
INSERT INTO gate_response_actions VALUES
  ('ra-1', 'dd-1', 'log_only',        'acme-corp', 'prod', datetime('now', '-3 days')),
  ('ra-2', 'dd-3', 'tier_reduction',  'acme-corp', 'prod', datetime('now', '-1 days'));

-- Adversarial outcomes: distinct type, no crossover.
INSERT INTO gate_adversarial_outcomes VALUES
  ('ao-1', 'gate.assurance.adversarial_outcome', 'acme-corp', 'prod', datetime('now', '-4 days')),
  ('ao-2', 'gate.assurance.adversarial_outcome', 'acme-corp', 'prod', datetime('now', '-2 days'));

-- Matching policy_decisions for the v13 tool requests so Check01 passes
-- when this fixture is loaded alongside sample_evidence.sql.
CREATE TABLE IF NOT EXISTS gate_policy_decisions (
    decision_id TEXT PRIMARY KEY, request_hash TEXT, run_id TEXT, trace_id TEXT,
    tenant_id TEXT, environment TEXT, tool_category TEXT, decision TEXT,
    reason TEXT, obligations TEXT, policy_bundle_hash TEXT,
    signature_ref TEXT, signing_key_id TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_policy_bundles (
    bundle_hash TEXT PRIMARY KEY, bundle_version TEXT, signed_at TEXT
);
INSERT OR IGNORE INTO gate_policy_bundles VALUES
  ('sha256:bundle-v1', 'v1.0.0', datetime('now', '-15 days'));
INSERT INTO gate_policy_decisions VALUES
  ('dec-v13-1', 'sha256:v13-001', 'run-v13-1', 'tr-v13-1', 'acme-corp', 'prod',
   'read_only', 'allow', NULL, '', 'sha256:bundle-v1', NULL, NULL, datetime('now', '-2 days')),
  ('dec-v13-2', 'sha256:v13-002', 'run-v13-2', 'tr-v13-2', 'acme-corp', 'prod',
   'financial', 'allow', NULL, '', 'sha256:bundle-v1',
   'sig:dec-v13-2', 'key:treasury-2026', datetime('now', '-1 days'));
