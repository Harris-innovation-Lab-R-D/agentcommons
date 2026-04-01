# AgentCommons Integration Skill (OpenClaw)

OpenClaw-specific integration wrapper for AgentCommons memory network.

**Use when:**
- Agents need to query organizational knowledge (federal contracting, sales pipeline, org structure)
- Performing similarity searches across agent memories
- Filtering memories by agent type, embedding model, or date range
- Batch-querying multiple related topics
- Building institutional memory that transcends individual agents
- Implementing pre-task and post-task active learning workflows

**Do not use for:**
- Real-time agent-to-agent chat (use direct MCP instead)
- Non-memory queries (use native skills for domain-specific queries)

**Generic documentation:** See `hil/agentcommons/` for upstream architecture (not Harris-specific)
**Harris-specific setup:** See `hil/AGENTCOMMONS_SETUP_WORKSPACE.md` for OpenClaw integration patterns

## Overview

AgentCommons is a **centralized SQLite-backed memory hub** that all Harris Innovation Lab agents can query. It provides:

- **Tag-based search** — Find memories labeled with `#federal-contracting`, `#sales-pipeline`, etc.
- **Semantic similarity** — Query by topic/embedding to find related agent memories
- **Filtering** — By agent type (Goku, Loki, Henry), embedding model, date range
- **Result ranking** — Relevance scores with confidence intervals
- **Caching** — In-memory + disk cache for fast repeated queries
- **Auto-detection** — Discovers local MCP Memory Server or remote API endpoint
- **Fallback** — Graceful degradation if AgentCommons is unavailable

## Configuration

### Environment Variables

```bash
# Optional: if not set, auto-detects localhost:8765
AGENTCOMMONS_API_URL=http://localhost:8765

# Optional: disable caching
AGENTCOMMONS_CACHE_DISABLED=false

# Optional: cache directory (defaults to ~/.openclaw/workspace/.agentcommons-cache/)
AGENTCOMMONS_CACHE_DIR=~/.openclaw/workspace/.agentcommons-cache/

# Optional: embedding model (defaults to nomic-embed-text)
AGENTCOMMONS_EMBEDDING_MODEL=nomic-embed-text
```

### Auto-Detection

On first import, the skill will:
1. Try `AGENTCOMMONS_API_URL` if set
2. Try `http://localhost:8765` (MCP Memory Server default)
3. Fall back to in-memory queries only (no persistence)

## Usage

### Basic Tag Search

```python
from agentcommons_client import AgentCommonsClient

client = AgentCommonsClient()

# Query by tag
results = client.query_by_tag("#federal-contracting", limit=10)
for memory in results:
    print(f"[{memory['source_agent']}] {memory['content']}")
    print(f"  Relevance: {memory['relevance_score']:.2f}")
    print(f"  Tags: {', '.join(memory['tags'])}")
```

### Semantic Similarity Search

```python
# Query by embedding similarity
results = client.query_by_similarity(
    "How do we approach SBIR proposals?",
    limit=5,
    agent_types=["Goku"],  # Filter by agent type
    date_range=("2026-01-01", "2026-03-31")
)

for memory in results:
    print(f"{memory['content']}")
    print(f"  Similarity: {memory['relevance_score']:.3f}")
```

### Batch Queries

```python
# Efficient multi-topic query
topics = [
    "GSA schedule negotiations",
    "Win probability assessment",
    "Proposal timeline compression"
]

batch_results = client.query_batch(topics, limit=3)
for topic, memories in batch_results.items():
    print(f"\n{topic}:")
    for mem in memories:
        print(f"  - {mem['content'][:80]}")
```

### Filtering & Ranking

```python
# Advanced filtering with result ranking
results = client.query_by_tag(
    "#sales-pipeline",
    agent_types=["Loki"],
    embedding_models=["nomic-embed-text"],
    date_range=("2026-03-01", "2026-03-31"),
    min_relevance=0.5,
    limit=10,
    rank_by="recency"  # or 'relevance' (default)
)
```

### Error Handling & Fallback

```python
try:
    results = client.query_by_tag("#federal-contracting")
except AgentCommonsUnavailableError:
    print("AgentCommons offline — using local memory only")
    results = client.query_local("#federal-contracting")

if not results:
    print("No memories found for this query")
```

## Cache Behavior

- **In-memory cache (LRU):** 128 entries, auto-evicted on size
- **Disk cache:** `~/.openclaw/workspace/.agentcommons-cache/*.json`
- **Cache invalidation:** Manual via `client.clear_cache()` or auto-expire (24h TTL)
- **Cache stats:** `client.cache_stats()` returns hits, misses, size

## Integration Guide

### For Individual Agents

Add to your agent startup:

```python
from agentcommons_client import AgentCommonsClient

self.agentcommons = AgentCommonsClient()
```

Then in your task execution:

```python
# Before starting a federal contracting proposal
fed_context = self.agentcommons.query_by_tag("#federal-contracting", limit=5)
self.context.append({
    "source": "AgentCommons",
    "memories": fed_context
})
```

### For Agents with Domain Context

Example: **Goku** (federal contracting agent) querying institutional memory:

```python
# High-level: "Give me recent SBIR strategy insights"
sbir_memories = self.agentcommons.query_by_similarity(
    "SBIR Phase 1 proposal strategy and timeline",
    agent_types=["Goku"],  # Find Goku's own past learnings
    date_range=("2026-03-01", None),  # Recent only
    limit=5
)
```

Example: **Loki** (sales agent) cross-querying domain knowledge:

```python
# Cross-domain: "What do federal agents know about prospect qualification?"
fed_intel = self.agentcommons.query_by_tag(
    "#prospect-qualification",
    agent_types=["Goku"],  # Learn from Goku's perspective
    limit=3
)
```

## Result Format

All queries return structured JSON:

```json
[
  {
    "id": "memory_uuid",
    "content": "The proposal team should compress Phase 1 timelines by...",
    "source_agent": "Goku",
    "agent_type": "federal-contracting",
    "tags": ["#federal-contracting", "#SBIR", "#timeline-compression"],
    "created_at": "2026-03-25T14:30:00Z",
    "embedding_model": "nomic-embed-text",
    "relevance_score": 0.87,
    "confidence": 0.95,
    "metadata": {
      "context": "Post-win analysis",
      "opportunity_id": "OPP-2026-001"
    }
  }
]
```

## Performance & Limits

- **Query timeout:** 5s (configurable)
- **Max batch size:** 20 topics
- **Max result limit:** 100 per query
- **Cache size:** ~50MB (tunable)

## Troubleshooting

### "AgentCommonsUnavailableError"

AgentCommons is not reachable. Check:

1. Docker Compose is running: `docker-compose -f ~/.openclaw/workspace/hil/agentcommons-docker/docker-compose.yml ps`
2. API endpoint is correct: `echo $AGENTCOMMONS_API_URL`
3. Network connectivity: `curl http://localhost:8765/health`

### Slow Queries

- Check cache hit rate: `client.cache_stats()`
- Clear stale cache: `client.clear_cache(older_than=86400)` (24h)
- Reduce query scope: Use date ranges, agent filters, or smaller limits

### Low Relevance Scores

Semantic search uses embedding similarity. If scores are low:

- Query content may not match memory content closely
- Try broader topic wording
- Check embedding model matches: `client.info()["embedding_model"]`
- Review recent memories: `client.query_by_tag(..., rank_by="recency")`

## References

See `references/` for:
- `agentcommons_client.py` — Full Python client with source code
- `example_federal_contracting.py` — Goku integration example
- `example_sales_pipeline.py` — Loki integration example
- `cache_management.py` — Advanced caching patterns
