-- Canonical schema reference for runner fixtures.
--
-- Each fixture file embeds the CREATE TABLE statements it needs (using
-- CREATE TABLE IF NOT EXISTS) so it is self-contained. This file is the
-- canonical source so the table shapes stay in sync.
--
-- The schema is the runner's logical model. Operators with different
-- column names override via config.table_name_overrides without changing
-- check code.

CREATE TABLE IF NOT EXISTS gate_tool_requests (
    request_hash         TEXT PRIMARY KEY,
    run_id               TEXT,
    trace_id             TEXT,
    agent_instance_id    TEXT,
    originating_identity TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    tool_name            TEXT,
    tool_category        TEXT,
    tool_schema_hash     TEXT,
    identity_verified    INTEGER,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_policy_decisions (
    decision_id          TEXT PRIMARY KEY,
    request_hash         TEXT,
    run_id               TEXT,
    trace_id             TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    tool_category        TEXT,
    decision             TEXT,
    reason               TEXT,
    obligations          TEXT,
    policy_bundle_hash   TEXT,
    signature_ref        TEXT,
    signing_key_id       TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_tool_responses (
    request_hash         TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_ledger_events (
    event_hash           TEXT PRIMARY KEY,
    sequence_number      INTEGER,
    prev_event_hash      TEXT,
    sink_uri             TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    run_id               TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_breaker_events (
    event_id             TEXT PRIMARY KEY,
    event_type           TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_budget_events (
    event_id             TEXT PRIMARY KEY,
    event_type           TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_replay_traces (
    trace_id             TEXT PRIMARY KEY,
    tenant_id            TEXT,
    environment          TEXT,
    model_id             TEXT,
    prompt_bundle_hash   TEXT,
    tool_schema_hash     TEXT,
    snapshot_uri         TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_semantic_traces (
    event_id             TEXT PRIMARY KEY,
    run_id               TEXT,
    trace_id             TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_hitl_decisions (
    approval_id          TEXT PRIMARY KEY,
    policy_decision_id   TEXT,
    signature_ref        TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_memory_responses (
    response_id          TEXT PRIMARY KEY,
    item_id              TEXT,
    request_type         TEXT,
    memory_decision_id   TEXT,
    quality_decision_id  TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_memory_decisions (
    decision_id          TEXT PRIMARY KEY,
    decision             TEXT,
    reason               TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_memory_quarantine (
    event_id             TEXT PRIMARY KEY,
    item_id              TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_agent_messages (
    message_id           TEXT PRIMARY KEY,
    validation_status    TEXT,
    reason               TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_policy_bundles (
    bundle_hash          TEXT PRIMARY KEY,
    bundle_version       TEXT,
    signed_at            TEXT
);

-- v1.3 tables (Check16-19)

CREATE TABLE IF NOT EXISTS gate_discovery_events (
    event_id             TEXT PRIMARY KEY,
    candidate_hash       TEXT,
    workload_identity    TEXT,
    classifier_bundle_hash TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_remediation_outcomes (
    event_id             TEXT PRIMARY KEY,
    candidate_hash       TEXT,
    outcome              TEXT,
    owner_identity       TEXT,
    exception_ttl_expires_at TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

-- C04 inventory and the tool request stream are deliberately distinct
-- tables. The reconciliation join in Check16 reads from both with no
-- aliasing ambiguity.
CREATE TABLE IF NOT EXISTS gate_c04_inventory (
    agent_instance_id    TEXT PRIMARY KEY,
    state                TEXT,
    autonomy_tier        TEXT,
    current_abom_hash    TEXT,
    tenant_id            TEXT,
    environment          TEXT
);

CREATE TABLE IF NOT EXISTS gate_classifier_bundles (
    bundle_hash          TEXT PRIMARY KEY,
    signed_at            TEXT
);

CREATE TABLE IF NOT EXISTS gate_quality_bundles (
    bundle_hash          TEXT PRIMARY KEY,
    tenant_id            TEXT,
    is_active            INTEGER,
    action_matrix        TEXT   -- JSON-encoded
);

CREATE TABLE IF NOT EXISTS gate_quality_decisions (
    decision_id          TEXT PRIMARY KEY,
    quality_bundle_hash  TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_drift_decisions (
    event_id             TEXT PRIMARY KEY,
    event_type           TEXT,
    agent_instance_id    TEXT,
    dimension            TEXT,
    decision             TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_response_actions (
    event_id             TEXT PRIMARY KEY,
    drift_decision_id    TEXT,
    action               TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_adversarial_outcomes (
    event_id             TEXT PRIMARY KEY,
    event_type           TEXT,
    tenant_id            TEXT,
    environment          TEXT,
    time                 TEXT
);

CREATE TABLE IF NOT EXISTS gate_baselines (
    baseline_hash        TEXT PRIMARY KEY,
    created_at           TEXT
);

CREATE TABLE IF NOT EXISTS gate_abom (
    agent_instance_id    TEXT,
    current_baseline_hash TEXT,
    is_current           INTEGER,
    tenant_id            TEXT
);

CREATE TABLE IF NOT EXISTS gate_agent_state (
    agent_instance_id    TEXT PRIMARY KEY,
    state                TEXT,
    autonomy_tier        TEXT,
    tenant_id            TEXT,
    environment          TEXT
);

CREATE TABLE IF NOT EXISTS gate_gateway_identities (
    identity             TEXT PRIMARY KEY
);
