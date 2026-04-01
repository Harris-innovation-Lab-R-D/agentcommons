# AgentCommons Active Learning - Complete Guide

## Overview

The Active Learning System enables agents to learn from each other through a four-phase cycle:

1. **Pre-Task Query** — Find related past work, detect conflicting approaches
2. **Task Execution** — Agent performs work with institutional memory context
3. **Post-Task Export** — Extract learnings, auto-tag, store in AgentCommons
4. **Conflict Resolution** — Carlton reviews and decides on approach conflicts

This creates a **feedback loop** where each task enriches the organizational knowledge base and improves future agent performance.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AgentCommons Core                        │
│  (SQLite backend with embeddings, tags, metadata)           │
└─────────────────────────────────────────────────────────────┘
              ↑                              ↑
              │                              │
       ┌──────┴──────────────┐      ┌──────┴──────────────┐
       │ Pre-Task Querier    │      │ Post-Task Exporter  │
       │ • Find similar work │      │ • Extract learnings │
       │ • Detect conflicts  │      │ • Auto-tag          │
       │ • Escalate to user  │      │ • Detect conflicts  │
       └────────────────────┘      └────────────────────┘
              ↑                              ↓
       ┌──────────────────────────────────────────┐
       │    Agent (Goku, Loki, OpenCode, etc.)    │
       │  ┌──────────────────────────────────┐   │
       │  │ AgentCommonsActiveLearning       │   │
       │  │ • Unified integration point      │   │
       │  │ • Handles pre/post workflows     │   │
       │  │ • Manages conflicts              │   │
       │  └──────────────────────────────────┘   │
       └──────────────────────────────────────────┘
              ↓
       ┌─────────────────────┐
       │   ConflictManager   │
       │ • Compare approaches│
       │ • Create decisions  │
       │ • Record outcomes   │
       └─────────────────────┘
              ↓
       ┌─────────────────────┐
       │   Carlton (User)    │
       │ • Review conflicts  │
       │ • Make decisions    │
       │ • Provide rationale │
       └─────────────────────┘
```

## Integration Steps for Each Agent

### Step 1: Initialize Active Learning

```python
from agentcommons_active import AgentCommonsActiveLearning

class MyAgent:
    def __init__(self):
        self.agent_name = "MyAgent"
        self.agent_type = "domain-type"
        
        # Initialize active learning
        self.active_learning = AgentCommonsActiveLearning(
            agent_name=self.agent_name,
            agent_type=self.agent_type
        )
```

### Step 2: Pre-Task Query

Before starting work, query for related past work:

```python
def execute_task(self, task_details):
    # Query for related work and check conflicts
    context = self.active_learning.query_and_check_conflicts(
        domain="your-domain",
        topic="your-task-topic",
        task_id="task-001",
        check_conflicts=True,
        escalate_threshold=0.75,
        limit=5
    )
    
    # Review recommendations
    print(f"Found {context['similar_work_count']} related past work items")
    if context['conflicts']:
        print(f"⚠️  {context['conflicts_count']} approach conflicts detected")
        # Wait for Carlton's decision if conflicts exist
        if context['status'] == 'conflicts_detected':
            await carlton_approval(context)
    
    # Proceed with task execution
    result = self.do_work(task_details, context)
    
    return result
```

### Step 3: Post-Task Export

After completing work, export learnings:

```python
def after_task_execution(self, task_details, task_result):
    # Export learnings and check for conflicts
    export = self.active_learning.export_and_detect_conflicts(
        agent_output=task_result,
        domain="your-domain",
        task_id="task-001",
        task_title="Your Task Title",
        outcome="success",  # or "partial", "failed"
        approach="Description of approach used",
        metadata={
            "opportunity_id": "OPP-001",
            "metrics": {"timeline": 12, "quality_score": 0.95}
        }
    )
    
    print(f"✓ Exported to AgentCommons")
    print(f"✓ Learnings: {export['learnings_count']}")
    print(f"✓ Tags: {export['tags_count']}")
    
    if export['conflicts']:
        print(f"⚠️  Post-task conflicts detected")
        # Carlton reviews these for future agent guidance
```

## Pre-Task Query Patterns

### Pattern 1: Find Similar Past Work

Find what similar tasks the agent has done before:

```python
context = active_learning.query_and_check_conflicts(
    domain="federal-contracting",
    topic="SBIR Phase 1 proposal",
    task_id="task-sbir-001"
)

for past_work in context['similar_work']:
    print(f"Agent: {past_work['source_agent']}")
    print(f"Date: {past_work['created_at']}")
    print(f"Outcome: {past_work['outcome']}")
    print(f"Relevance: {past_work['relevance_score']:.0%}")
```

### Pattern 2: Cross-Domain Learning

Find approaches from other domains that might apply:

```python
# Goku wants to learn how Loki handles timeline compression
context = active_learning.query_and_check_conflicts(
    domain="federal-contracting",
    topic="timeline compression strategies",
    task_id="task-001"
)
# Will include insights from Loki's sales pipeline work
```

### Pattern 3: Check for Conflicting Approaches

Detect when different agents solved the same problem differently:

```python
context = active_learning.query_and_check_conflicts(
    domain="federal-contracting",
    topic="SBIR Phase 1 proposal",
    task_id="task-001",
    check_conflicts=True,
    escalate_threshold=0.75  # Only flag significant conflicts
)

if context['conflicts']:
    print(f"⚠️  {len(context['conflicts'])} conflicting approach(es):")
    for conflict in context['conflicts']:
        print(f"  - {conflict['conflict_type']}: {conflict['approach_divergence']:.0%} different")
```

## Post-Task Export Patterns

### Pattern 1: Basic Learning Export

Extract and export key learnings from task completion:

```python
export = active_learning.export_and_detect_conflicts(
    agent_output="Task summary with learnings",
    domain="federal-contracting",
    task_id="task-sbir-001",
    outcome="success"
)
```

### Pattern 2: Structured Metadata Export

Include detailed metadata for richer context:

```python
export = active_learning.export_and_detect_conflicts(
    agent_output=task_result,
    domain="federal-contracting",
    task_id="task-sbir-001",
    task_title="SBIR Phase 1 Proposal",
    outcome="success",
    approach="Parallel workstreams with daily syncs",
    metadata={
        "opportunity_id": "OPP-2026-001",
        "timeline_days": 12,
        "timeline_compression": 0.25,
        "quality_score": 0.95,
        "win_probability": 0.87,
        "key_success_factors": [
            "Parallel execution",
            "Daily sync meetings",
            "Pre-written boilerplate"
        ]
    }
)
```

### Pattern 3: Conditional Metadata

Export different metadata based on task type:

```python
metadata = {}

if task_type == "proposal_writing":
    metadata = {
        "proposal_pages": result['pages'],
        "quality_score": result['quality'],
        "timeline_compression": result['timeline_vs_baseline'],
        "reuse_rate": result['content_reused_percent']
    }

elif task_type == "prospect_research":
    metadata = {
        "prospects_researched": result['count'],
        "qualification_rate": result['qualified_percent'],
        "intelligence_sources": result['sources_used']
    }

export = active_learning.export_and_detect_conflicts(
    agent_output=result,
    domain=task_domain,
    task_id=task_id,
    metadata=metadata
)
```

## Conflict Workflow

### Step 1: Conflict Detection

Agent task creates conflict escalation:

```
Goku: "I'm using approach A for SBIR proposals (parallel workstreams)"
AgentCommons: "But past work used approach B (sequential reviews)"
→ Detected conflict: Speed vs. Quality
→ Problem similarity: 80%
→ Approach divergence: 65%
```

### Step 2: Escalation to Carlton

ConflictManager creates decision record:

```python
decision_record = {
    "conflict_id": "conflict-task-001-123456",
    "status": "pending",
    "requester": "Carlton",
    "approach1": "Parallel workstreams with daily syncs",
    "approach2": "Sequential with weekly reviews",
    "trade_offs": ["speed_vs_quality"],
    "user_prompt": "Which approach is canonical for SBIR proposals?"
}
```

### Step 3: Carlton's Decision

Carlton reviews conflict and chooses:

```python
# Carlton's options:
# 1. "canonical_approach1" → Mark Approach 1 as the standard
# 2. "canonical_approach2" → Mark Approach 2 as the standard
# 3. "context_dependent" → Both valid in different contexts
# 4. "hybrid" → Combine elements from both
# 5. "research" → Need more information

carlton.make_decision(
    conflict_id="conflict-task-001-123456",
    decision="hybrid",
    rationale="Use parallel (speed) + quality gates (reviews at day 7, 10)"
)
```

### Step 4: Decision Recorded

AgentCommons marks approaches with Carlton's decision:

```python
# Future agents learn from this:
{
    "conflict_id": "conflict-task-001-123456",
    "status": "resolved",
    "canonical_approach": "hybrid",
    "guidance": "For SBIR proposals on tight timelines: use parallel workstreams + quality gates",
    "decided_by": "Carlton",
    "decided_at": "2026-03-31T14:30:00Z"
}
```

## Best Practices

### What to Tag

Use tags to make learning discoverable:

```python
tags = [
    "#domain",              # #federal-contracting, #sales-pipeline
    "#agent:name",          # #agent:goku, #agent:loki
    "#outcome:status",      # #outcome:success, #outcome:failed
    "#method",              # #proposal-writing, #timeline-compression
    "#YYYY-MM"              # #2026-03 (temporal sorting)
]

# Auto-generated by auto_tag()
```

### What to Escalate

Escalate conflicts to Carlton when:

- ✅ **Problem similarity > 75%** AND **approach divergence > 40%**
- ✅ **Multiple agents solved it differently**
- ✅ **Outcomes differ significantly** (one succeeded, one didn't)
- ✅ **Trade-off is strategic** (speed vs. quality, cost vs. scope)

Don't escalate:

- ❌ Minor wording differences (85%+ similarity)
- ❌ Low-impact variations (both approaches identical)
- ❌ Context-specific variations that are already documented

### Metadata Expectations

Include structured metadata for pattern matching:

```python
# Good: Structured, metric-driven
metadata = {
    "timeline_days": 12,
    "timeline_vs_baseline_percent": 0.25,  # 25% improvement
    "quality_score": 0.95,  # 0-1 scale
    "reuse_rate": 0.30,  # 30% content reused
    "key_blockers": ["resource_availability"],
    "success_factors": ["parallel_execution", "daily_syncs"]
}

# Bad: Unstructured, hard to search
metadata = {
    "notes": "Proposal went well, lots of teamwork"
}
```

## Testing & Validation

### Unit Tests

Test each module independently:

```bash
python -m pytest tests/test_pretask.py -v
python -m pytest tests/test_posttask.py -v
python -m pytest tests/test_conflict.py -v
python -m pytest tests/test_active.py -v
```

### Integration Tests

Test full workflow end-to-end:

```bash
python tests/test_integration.py
# Runs: pre-task → work → post-task → conflict detection
```

### Test Data

Use provided sample conflicts and exports:

```python
from tests.test_data import sample_conflicts, sample_exports

# Test conflict detection
conflicts = manager.compare_approaches(
    approach1=sample_conflicts[0]["approach1"],
    approach2=sample_conflicts[0]["approach2"],
    problem_context=sample_conflicts[0]["problem"]
)

assert conflicts["overall_similarity"] > 0.6
```

## Schema Validation

Pre-task, post-task, and conflict records follow strict schemas:

### PreTaskContext Schema

```json
{
  "task_id": "string",
  "domain": "string",
  "topic": "string",
  "similar_work": [
    {
      "id": "string",
      "content": "string",
      "source_agent": "string",
      "relevance_score": 0.0-1.0,
      "created_at": "ISO8601"
    }
  ],
  "conflicts": [
    {
      "past_work_id": "string",
      "problem_similarity": 0.0-1.0,
      "approach_divergence": 0.0-1.0,
      "conflict_type": "string"
    }
  ]
}
```

### PostTaskExport Schema

```json
{
  "id": "string",
  "status": "stored|pending_sync",
  "content": "string",
  "source_agent": "string",
  "tags": ["#tag1", "#tag2"],
  "learnings": ["learning1", "learning2"],
  "metadata": {
    "outcome": "success|partial|failed",
    "approach": "string",
    "metrics": {}
  }
}
```

### ConflictDecision Schema

```json
{
  "conflict_id": "string",
  "status": "pending|resolved",
  "comparison": {
    "approach1": "string",
    "approach2": "string",
    "overall_similarity": 0.0-1.0,
    "trade_offs": []
  },
  "decision": "canonical_approach1|canonical_approach2|context_dependent|hybrid",
  "decided_by": "string",
  "decided_at": "ISO8601",
  "rationale": "string"
}
```

## Troubleshooting

### No Similar Work Found

**Problem:** `similar_work_count = 0`

**Causes:**
- Domain or topic is too new
- Query is too narrow (increase `limit`)
- Relevant past work wasn't tagged properly

**Solution:**
```python
# Try broader topic
context = active_learning.query_and_check_conflicts(
    domain="federal-contracting",
    topic="proposal management",  # Broader than "SBIR Phase 1"
    limit=10  # Increase limit
)
```

### Conflicts Not Escalating

**Problem:** Conflicts detected but not escalating to Carlton

**Causes:**
- `check_conflicts=False` in query call
- `escalate_threshold` too high (default 0.75 = 75% similarity)
- Conflict manager not initialized

**Solution:**
```python
# Ensure check_conflicts is True
context = active_learning.query_and_check_conflicts(
    domain="federal-contracting",
    topic="SBIR Phase 1",
    check_conflicts=True,  # Explicit
    escalate_threshold=0.70  # Lower threshold
)
```

### Learnings Not Extracted

**Problem:** `learnings_count = 0` after post-task export

**Causes:**
- Agent output format not matching regex patterns
- No explicit "LEARNING:", "KEY INSIGHT:", etc. in output
- Keywords not found in agent output

**Solution:**
```python
# Pass structured learning objects instead of plain text
export = active_learning.export_and_detect_conflicts(
    agent_output=task_result,
    domain="federal-contracting",
    task_id="task-001",
    # Optional: explicit learnings
    learnings=[
        "Parallel execution saves 25% timeline",
        "Daily syncs improve coordination"
    ]
)
```

## Next Steps

1. **Integrate Goku (Pilot Agent)**
   - Test pre-task queries for federal opportunities
   - Test post-task export of proposal learnings
   - Validate conflict detection on approach decisions
   - Get Carlton's feedback on conflict escalations

2. **Integrate Remaining Agents**
   - Loki: Sales pipeline & prospect research
   - OpenCode: Software development
   - Others: Domain-specific workflows

3. **Scale Active Learning**
   - Increase embedding model capacity
   - Add more sophisticated similarity detection
   - Build agent-to-agent recommendation system
   - Create dashboard for Carlton's decisions

4. **Feedback Loop**
   - Track decision outcomes (did Carlton's choice improve future tasks?)
   - Adjust escalation thresholds based on Carlton's preferences
   - Auto-detect patterns in decisions (when does Carlton choose speed vs. quality?)
   - Use patterns to auto-make routine decisions

## References

- `agentcommons_active.py` — Main integration entry point
- `agentcommons_pretask.py` — Pre-task query logic
- `agentcommons_posttask.py` — Post-task export logic
- `agentcommons_conflict.py` — Conflict detection & management
- `agentcommons_client.py` — Core API client
- `goku-federal-bd-example.py` — Goku integration example
- `conflict-resolution-example.py` — Carlton's decision workflow
