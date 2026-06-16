-- sample_evidence.sql
-- Passing bounded-tier evidence for Check01-Check15.
-- Self-contained: CREATE TABLE statements at the top, INSERTs below.
-- Tenant: acme-corp, environment: prod. Times are relative ('now' - N days).

-- ---------------------------------------------------------------
-- Schema (CREATE TABLE IF NOT EXISTS for idempotent fixture loads)
-- ---------------------------------------------------------------

CREATE TABLE IF NOT EXISTS gate_tool_requests (
    request_hash TEXT PRIMARY KEY, run_id TEXT, trace_id TEXT,
    agent_instance_id TEXT, originating_identity TEXT, tenant_id TEXT, environment TEXT,
    tool_name TEXT, tool_category TEXT, tool_schema_hash TEXT,
    identity_verified INTEGER, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_policy_decisions (
    decision_id TEXT PRIMARY KEY, request_hash TEXT, run_id TEXT, trace_id TEXT,
    tenant_id TEXT, environment TEXT, tool_category TEXT, decision TEXT,
    reason TEXT, obligations TEXT, policy_bundle_hash TEXT,
    signature_ref TEXT, signing_key_id TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_tool_responses (
    request_hash TEXT, tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_ledger_events (
    event_hash TEXT PRIMARY KEY, sequence_number INTEGER, prev_event_hash TEXT,
    sink_uri TEXT, tenant_id TEXT, environment TEXT, run_id TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_breaker_events (
    event_id TEXT PRIMARY KEY, event_type TEXT, tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_budget_events (
    event_id TEXT PRIMARY KEY, event_type TEXT, tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_replay_traces (
    trace_id TEXT PRIMARY KEY, tenant_id TEXT, environment TEXT,
    model_id TEXT, prompt_bundle_hash TEXT, tool_schema_hash TEXT,
    snapshot_uri TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_semantic_traces (
    event_id TEXT PRIMARY KEY, run_id TEXT, trace_id TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_hitl_decisions (
    approval_id TEXT PRIMARY KEY, policy_decision_id TEXT,
    signature_ref TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_memory_responses (
    response_id TEXT PRIMARY KEY, item_id TEXT, request_type TEXT,
    memory_decision_id TEXT, quality_decision_id TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_memory_decisions (
    decision_id TEXT PRIMARY KEY, decision TEXT, reason TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_memory_quarantine (
    event_id TEXT PRIMARY KEY, item_id TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_agent_messages (
    message_id TEXT PRIMARY KEY, validation_status TEXT, reason TEXT,
    tenant_id TEXT, environment TEXT, time TEXT
);
CREATE TABLE IF NOT EXISTS gate_policy_bundles (
    bundle_hash TEXT PRIMARY KEY, bundle_version TEXT, signed_at TEXT
);
CREATE TABLE IF NOT EXISTS gate_gateway_identities (
    identity TEXT PRIMARY KEY
);

-- ---------------------------------------------------------------
-- Configured fixtures
-- ---------------------------------------------------------------

-- The Tool Gateway identity (every legitimate tool request originates here).
INSERT INTO gate_gateway_identities VALUES ('spiffe://acme/gateway/tool-gateway');

-- Active policy bundle registered in the signed registry.
INSERT INTO gate_policy_bundles VALUES ('sha256:bundle-v1', 'v1.0.0', datetime('now', '-15 days'));

-- ---------------------------------------------------------------
-- Tool requests + matching policy decisions
-- Check01: every request_hash has a matching policy_decisions row -> PASS.
-- Check03: identity_verified = 1 on all -> PASS.
-- Check04: every request has tool_schema_hash; one schema reject below.
-- Check13: every decision references the active policy_bundle_hash.
-- ---------------------------------------------------------------

INSERT INTO gate_tool_requests VALUES
  ('sha256:req-001', 'run-1', 'tr-1', 'spiffe://acme/agent/planner',
   'spiffe://acme/gateway/tool-gateway', 'acme-corp', 'prod',
   'crm.lookup', 'read_only', 'sha256:tool-schema-v1', 1, datetime('now', '-2 days')),
  ('sha256:req-002', 'run-2', 'tr-2', 'spiffe://acme/agent/planner',
   'spiffe://acme/gateway/tool-gateway', 'acme-corp', 'prod',
   'crm.update', 'reversible_write', 'sha256:tool-schema-v1', 1, datetime('now', '-2 days')),
  ('sha256:req-003', 'run-3', 'tr-3', 'spiffe://acme/agent/treasury',
   'spiffe://acme/gateway/tool-gateway', 'acme-corp', 'prod',
   'transfer_funds', 'financial', 'sha256:tool-schema-v1', 1, datetime('now', '-1 days')),
  ('sha256:req-004', 'run-4', 'tr-4', 'spiffe://acme/agent/devops',
   'spiffe://acme/gateway/tool-gateway', 'acme-corp', 'prod',
   'deploy_service', 'infrastructure', 'sha256:tool-schema-v1', 1, datetime('now', '-1 days')),
  ('sha256:req-005', 'run-5', 'tr-5', 'spiffe://acme/agent/planner',
   'spiffe://acme/gateway/tool-gateway', 'acme-corp', 'prod',
   'crm.lookup', 'read_only', 'sha256:tool-schema-v1', 1, datetime('now', '-12 hours'));

INSERT INTO gate_policy_decisions VALUES
  ('dec-001', 'sha256:req-001', 'run-1', 'tr-1', 'acme-corp', 'prod',
   'read_only', 'allow', NULL, '', 'sha256:bundle-v1', NULL, NULL, datetime('now', '-2 days')),
  ('dec-002', 'sha256:req-002', 'run-2', 'tr-2', 'acme-corp', 'prod',
   'reversible_write', 'allow', NULL, '', 'sha256:bundle-v1', NULL, NULL, datetime('now', '-2 days')),
  -- Check09: high-impact decisions are SIGNED.
  ('dec-003', 'sha256:req-003', 'run-3', 'tr-3', 'acme-corp', 'prod',
   'financial', 'allow', NULL, 'hitl_required', 'sha256:bundle-v1',
   'sig:dec-003', 'key:treasury-2026', datetime('now', '-1 days')),
  ('dec-004', 'sha256:req-004', 'run-4', 'tr-4', 'acme-corp', 'prod',
   'infrastructure', 'allow', NULL, '', 'sha256:bundle-v1',
   'sig:dec-004', 'key:devops-2026', datetime('now', '-1 days')),
  ('dec-005', 'sha256:req-005', 'run-5', 'tr-5', 'acme-corp', 'prod',
   'read_only', 'allow', NULL, '', 'sha256:bundle-v1', NULL, NULL, datetime('now', '-12 hours')),
  -- Check04: at least one schema-validation reject in the window.
  ('dec-rej-001', 'sha256:req-bad', NULL, NULL, 'acme-corp', 'prod',
   'read_only', 'deny', 'schema_validation_failed', '', 'sha256:bundle-v1',
   NULL, NULL, datetime('now', '-3 days'));

-- Tool responses for the financial decision (used by Check14).
INSERT INTO gate_tool_responses VALUES
  ('sha256:req-003', 'acme-corp', 'prod', datetime('now', '-1 days'));

-- ---------------------------------------------------------------
-- Ledger chain (Check05): contiguous prev_event_hash linkage.
-- ---------------------------------------------------------------
INSERT INTO gate_ledger_events VALUES
  ('sha256:le-1', 1, 'GENESIS',      's3://acme-ledger/', 'acme-corp', 'prod', 'run-1', datetime('now', '-2 days')),
  ('sha256:le-2', 2, 'sha256:le-1',  's3://acme-ledger/', 'acme-corp', 'prod', 'run-2', datetime('now', '-2 days')),
  ('sha256:le-3', 3, 'sha256:le-2',  's3://acme-ledger/', 'acme-corp', 'prod', 'run-3', datetime('now', '-1 days')),
  ('sha256:le-4', 4, 'sha256:le-3',  's3://acme-ledger/', 'acme-corp', 'prod', 'run-4', datetime('now', '-1 days')),
  ('sha256:le-5', 5, 'sha256:le-4',  's3://acme-ledger/', 'acme-corp', 'prod', 'run-5', datetime('now', '-12 hours'));

-- ---------------------------------------------------------------
-- Breaker events (Check07): trigger + activation present.
-- ---------------------------------------------------------------
INSERT INTO gate_breaker_events VALUES
  ('be-1', 'breaker.trigger',  'acme-corp', 'prod', datetime('now', '-7 days')),
  ('be-2', 'stop.activation',  'acme-corp', 'prod', datetime('now', '-7 days'));

-- ---------------------------------------------------------------
-- Budget events (Check08): at least one throttle/deny.
-- ---------------------------------------------------------------
INSERT INTO gate_budget_events VALUES
  ('bu-1', 'budget.decrement', 'acme-corp', 'prod', datetime('now', '-5 days')),
  ('bu-2', 'budget.throttle',  'acme-corp', 'prod', datetime('now', '-4 days')),
  ('bu-3', 'budget.deny',      'acme-corp', 'prod', datetime('now', '-3 days'));

-- ---------------------------------------------------------------
-- Replay traces (Check06): complete metadata for the high-impact runs.
-- ---------------------------------------------------------------
INSERT INTO gate_replay_traces VALUES
  ('tr-3', 'acme-corp', 'prod', 'gpt-4-prod', 'sha256:prompt-v1', 'sha256:tool-schema-v1',
   's3://acme-replay/tr-3', datetime('now', '-1 days')),
  ('tr-4', 'acme-corp', 'prod', 'gpt-4-prod', 'sha256:prompt-v1', 'sha256:tool-schema-v1',
   's3://acme-replay/tr-4', datetime('now', '-1 days'));

-- ---------------------------------------------------------------
-- Semantic traces (Check12): one event per run_id used above.
-- ---------------------------------------------------------------
INSERT INTO gate_semantic_traces VALUES
  ('st-1', 'run-1', 'tr-1', 'acme-corp', 'prod', datetime('now', '-2 days')),
  ('st-2', 'run-2', 'tr-2', 'acme-corp', 'prod', datetime('now', '-2 days')),
  ('st-3', 'run-3', 'tr-3', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('st-4', 'run-4', 'tr-4', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('st-5', 'run-5', 'tr-5', 'acme-corp', 'prod', datetime('now', '-12 hours'));

-- ---------------------------------------------------------------
-- HITL decisions (Check14): signed approval for the financial decision.
-- ---------------------------------------------------------------
INSERT INTO gate_hitl_decisions VALUES
  ('appr-1', 'dec-003', 'sig:hitl-1', datetime('now', '-1 days'));

-- ---------------------------------------------------------------
-- Memory responses + decisions (Check10): coverage = 100%.
-- Also includes a cross-tenant deny event (negative test artefact).
-- ---------------------------------------------------------------
INSERT INTO gate_memory_responses VALUES
  ('mr-1', 'item-a', 'read', 'mdec-1', 'qdec-mr-1', 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mr-2', 'item-b', 'read', 'mdec-2', 'qdec-mr-2', 'acme-corp', 'prod', datetime('now', '-1 days'));

INSERT INTO gate_memory_decisions VALUES
  ('mdec-1', 'allow', NULL, 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mdec-2', 'allow', NULL, 'acme-corp', 'prod', datetime('now', '-1 days')),
  ('mdec-3', 'deny',  'cross_tenant_read', 'acme-corp', 'prod', datetime('now', '-5 days'));

-- ---------------------------------------------------------------
-- Memory quarantine (Check11): event present, item not reused.
-- ---------------------------------------------------------------
INSERT INTO gate_memory_quarantine VALUES
  ('mq-1', 'poisoned-1', 'acme-corp', 'prod', datetime('now', '-4 days'));

-- ---------------------------------------------------------------
-- Agent message rejects (Check15): spoofed + nonce replay.
-- ---------------------------------------------------------------
INSERT INTO gate_agent_messages VALUES
  ('am-1', 'reject', 'spoofed_sender', 'acme-corp', 'prod', datetime('now', '-2 days')),
  ('am-2', 'reject', 'nonce_replay',   'acme-corp', 'prod', datetime('now', '-2 days'));
