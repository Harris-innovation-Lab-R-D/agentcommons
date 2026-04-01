-- AgentCommons Conflicts Table
-- Stores conflict detection records and Carlton's decisions
-- Run this migration after deploying active learning system

-- Create conflicts table
CREATE TABLE IF NOT EXISTS conflicts (
    conflict_id TEXT PRIMARY KEY,
    problem_context TEXT NOT NULL,
    approach_1 TEXT NOT NULL,
    approach_2 TEXT NOT NULL,
    agents_involved TEXT NOT NULL,  -- JSON array of agent names
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | resolved | archived
    decision TEXT,  -- canonical_approach_1 | canonical_approach_2 | context_dependent | hybrid
    decided_by TEXT,  -- Carlton or other user
    decided_at TIMESTAMP,
    
    -- Metadata
    metadata JSON,  -- {
                    --   "problem_similarity": 0.75,
                    --   "approach_divergence": 0.65,
                    --   "trade_offs": ["speed_vs_quality"],
                    --   "source_task_ids": ["task-001", "task-002"],
                    --   "outcome": "success|partial|failed"
                    -- }
    
    rationale TEXT,  -- Carlton's explanation for decision
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexing for performance
    created_at_idx INTEGER GENERATED ALWAYS AS (CAST(created_at AS INTEGER)) STORED,
    status_idx TEXT GENERATED ALWAYS AS (status) STORED
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status);
CREATE INDEX IF NOT EXISTS idx_conflicts_created ON conflicts(created_at);
CREATE INDEX IF NOT EXISTS idx_conflicts_decided_by ON conflicts(decided_by);
CREATE INDEX IF NOT EXISTS idx_conflicts_agents ON conflicts(agents_involved);

-- Add conflict_reference column to memories table (if it exists)
-- Links memories to the conflicts that affected them
ALTER TABLE memories ADD COLUMN IF NOT EXISTS conflict_id TEXT;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS is_canonical BOOLEAN DEFAULT NULL;  -- NULL=no conflict, True=canonical, False=deprecated
ALTER TABLE memories ADD COLUMN IF NOT EXISTS canonical_decision_id TEXT;

CREATE INDEX IF NOT EXISTS idx_memories_conflict_id ON memories(conflict_id);
CREATE INDEX IF NOT EXISTS idx_memories_is_canonical ON memories(is_canonical);

-- Create decision_rationales table for Carlton's decision explanations
-- Stores decision context and outcomes for learning
CREATE TABLE IF NOT EXISTS decision_rationales (
    rationale_id TEXT PRIMARY KEY,
    conflict_id TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT,
    context JSON,  -- {
                   --   "timeline_days": 12,
                   --   "outcome_importance": "critical",
                   --   "trade_off_preference": "speed"
                   -- }
    
    -- Outcome tracking (recorded later)
    outcome TEXT,  -- success | partial | failed
    outcome_notes TEXT,
    validated_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (conflict_id) REFERENCES conflicts(conflict_id)
);

CREATE INDEX IF NOT EXISTS idx_decision_rationales_decided_by ON decision_rationales(decided_by);
CREATE INDEX IF NOT EXISTS idx_decision_rationales_created ON decision_rationales(created_at);

-- Create conflict_outcomes table
-- Tracks whether Carlton's decisions led to good or bad outcomes
-- Enables learning from Carlton's decision patterns
CREATE TABLE IF NOT EXISTS conflict_outcomes (
    outcome_id TEXT PRIMARY KEY,
    conflict_id TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    
    -- Task that resulted from this decision
    task_id TEXT,
    agent_name TEXT,
    outcome TEXT NOT NULL,  -- success | partial | failed
    confidence REAL,  -- How confident we are in this outcome (0-1)
    
    -- Metrics
    metric_1 REAL,  -- timeline_compression, quality_score, etc.
    metric_1_name TEXT,
    metric_2 REAL,
    metric_2_name TEXT,
    
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (conflict_id) REFERENCES conflicts(conflict_id),
    FOREIGN KEY (decision_id) REFERENCES decision_rationales(rationale_id)
);

CREATE INDEX IF NOT EXISTS idx_conflict_outcomes_conflict_id ON conflict_outcomes(conflict_id);
CREATE INDEX IF NOT EXISTS idx_conflict_outcomes_outcome ON conflict_outcomes(outcome);

-- Trigger to update conflicts.updated_at on modification
CREATE TRIGGER IF NOT EXISTS update_conflicts_timestamp
AFTER UPDATE ON conflicts
BEGIN
    UPDATE conflicts SET updated_at = CURRENT_TIMESTAMP WHERE conflict_id = NEW.conflict_id;
END;

-- Trigger to update decision_rationales.updated_at on modification
CREATE TRIGGER IF NOT EXISTS update_decision_rationales_timestamp
AFTER UPDATE ON decision_rationales
BEGIN
    UPDATE decision_rationales SET updated_at = CURRENT_TIMESTAMP WHERE rationale_id = NEW.rationale_id;
END;

-- Views for easier querying

-- View: All unresolved conflicts
CREATE VIEW IF NOT EXISTS pending_conflicts AS
SELECT
    conflict_id,
    problem_context,
    approach_1,
    approach_2,
    agents_involved,
    status,
    created_at,
    json_extract(metadata, '$.problem_similarity') as problem_similarity,
    json_extract(metadata, '$.approach_divergence') as approach_divergence
FROM conflicts
WHERE status = 'pending'
ORDER BY created_at DESC;

-- View: Resolved conflicts with decisions
CREATE VIEW IF NOT EXISTS resolved_conflicts_with_decisions AS
SELECT
    c.conflict_id,
    c.problem_context,
    c.approach_1,
    c.approach_2,
    c.decision,
    c.decided_by,
    c.decided_at,
    c.rationale,
    dr.context,
    COUNT(co.outcome_id) as outcome_count
FROM conflicts c
LEFT JOIN decision_rationales dr ON c.conflict_id = dr.conflict_id
LEFT JOIN conflict_outcomes co ON dr.rationale_id = co.decision_id
WHERE c.status = 'resolved'
GROUP BY c.conflict_id
ORDER BY c.decided_at DESC;

-- View: Carlton's decision success rate
CREATE VIEW IF NOT EXISTS carlton_decision_success_rate AS
SELECT
    decided_by,
    COUNT(DISTINCT c.conflict_id) as total_decisions,
    COUNT(DISTINCT CASE WHEN co.outcome = 'success' THEN co.outcome_id END) as successful,
    ROUND(COUNT(DISTINCT CASE WHEN co.outcome = 'success' THEN co.outcome_id END) * 100.0 / 
          COUNT(DISTINCT c.conflict_id), 2) as success_rate
FROM conflicts c
LEFT JOIN decision_rationales dr ON c.conflict_id = dr.conflict_id
LEFT JOIN conflict_outcomes co ON dr.rationale_id = co.decision_id
WHERE c.status = 'resolved'
GROUP BY decided_by
ORDER BY success_rate DESC;

-- Verify schema was created
SELECT 'Conflicts table created' as status
WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='conflicts');
