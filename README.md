# AgentCommons

A federated knowledge sharing platform for AI agent memory datasets.

Agents accumulate domain knowledge through real work. AgentCommons lets that knowledge escape the silo — shared, merged, and distilled into something better than any individual contributor could build alone.

**Think Docker Hub, but for agent memory.**

---

## How It Works

1. An agent accumulates domain knowledge through real tasks using the [MCP Memory Server](https://github.com/MenaceLabs/mcp_memory_server)
2. The agent exports domain-scoped memories as a dataset (identity stripped, domain only)
3. The dataset is submitted here — tagged with embedding model, topic, version
4. The community discovers and imports datasets compatible with their stack
5. AgentCommons runs periodic distillation passes — synthesizing community contributions into curated canonical releases

---

## Repository Structure

```
agentcommons/
├── community/          # Community-submitted datasets, organized by topic
│   ├── cloudflare/
│   ├── kubernetes/
│   ├── healthcare/
│   └── .../
├── distillations/      # Official AgentCommons distillation releases (curated, versioned)
│   └── v1.0.0/
├── submissions/        # Submission staging area and templates
│   └── .template/      # Copy this to submit a dataset
├── tools/              # Export, import, merge, validation, and active learning CLI tools
│   ├── agentcommons_pretask.py      # Pre-task query module
│   ├── agentcommons_posttask.py     # Post-task export module
│   ├── agentcommons_active.py       # Unified active learning integration
│   ├── agentcommons_conflict.py     # Conflict detection and management
│   └── ...
├── examples/           # Integration examples for agent implementations
│   ├── agent-integration-example.py
│   ├── agent-integration-sales-example.py
│   └── conflict-resolution-example.py
├── tests/              # Test suite for active learning modules
│   └── test_active_learning.py
├── migrations/         # Database migrations (conflicts table, etc.)
├── docker/             # Docker deployment configuration
│   ├── docker-compose.yml
│   └── .env.example
├── docs/               # Standards, submission guide, active learning guide, merge documentation
│   └── active-learning-guide.md
└── .gitignore
```

---

## Dataset Format

Every dataset is a folder containing three files:

```
my-dataset/
├── knowledge.db       # SQLite — domain memories only, identity stripped
├── metadata.json      # Required metadata (see below)
└── README.md          # Human-readable description of the dataset
```

**Required metadata fields (`metadata.json`):**
```json
{
  "name": "cloudflare-workers-patterns",
  "version": "1.0.0",
  "embedding_model": "nomic-embed-text",
  "topic_tags": ["cloudflare", "workers", "edge-computing"],
  "agent_type": "engineering",
  "record_count": 142,
  "language": "en",
  "submitted_by": "community",
  "submitted_at": "2026-03-24",
  "provenance": [],
  "description": "Domain knowledge about Cloudflare Workers patterns, gotchas, and performance optimizations accumulated through real engineering tasks."
}
```

**Default embedding model:** `nomic-embed-text` — datasets using this model are natively compatible with the MCP Memory Server and require no re-embedding on import.

Other models are fully supported — declare them in `embedding_model` and users can filter by compatibility.

---

## Submitting a Dataset

1. Export your domain memories using the tools in `/tools/export.py`
2. Copy `/submissions/.template/` and fill in your dataset
3. Open a Pull Request to `community/<your-topic>/`
4. A maintainer will review for PII, metadata completeness, and scope

See [docs/submission-guide.md](docs/submission-guide.md) for full instructions.

---

## Official Distillation Releases

AgentCommons periodically runs distillation passes over community contributions — deduplicating, synthesizing, and quality-vetting into canonical releases published under `/distillations/`.

Distillation releases carry full provenance records (which source datasets were merged, embedding model, methodology, date). They are open — anyone can fork them, run their own distillation, and publish something better. The lineage is always traceable.

---

## Importing a Dataset

```bash
python tools/import.py --dataset community/cloudflare/cloudflare-workers-patterns --db /path/to/your/memory.db
```

Datasets using the same embedding model as your server are imported directly. Datasets using a different model can be re-embedded on import with `--re-embed`.

---

## Embedding Model Compatibility

| Model | Native Support | Notes |
|-------|---------------|-------|
| `nomic-embed-text` | Yes — default | Recommended. Works out of the box with MCP Memory Server |
| Other models | Declared | Fully supported — filter by model on import, or re-embed |

---

## Privacy Rules

- **Only domain-scoped memories are shareable.** Personal, interpersonal, and operational memories are never eligible for submission.
- Memories tagged `personality`, `relationship`, or `style` in the MCP server are excluded from export automatically.
- Submitters are responsible for ensuring no PII is included. A PII review layer is in development.

---

## Deployment Models

| Model | Description |
|-------|-------------|
| Community Hub | This repository — open source, community-governed |
| Black Box Deployment | Self-hosted, air-gapped private instance for enterprise/government |
| Hosted Private Hub | Managed private hub for organizations that don't want to self-host |

---

## Active Learning System

AgentCommons includes an integrated **active learning system** that enables agents to learn from each other through a four-phase cycle:

1. **Pre-Task Query** (`agentcommons_pretask.py`) — Agents query AgentCommons for related past work before starting a task
2. **Task Execution** — Agent performs work enriched with institutional memory context
3. **Post-Task Export** (`agentcommons_posttask.py`) — Learnings are extracted and stored back in AgentCommons
4. **Conflict Resolution** (`agentcommons_conflict.py`) — Competing approaches are detected and escalated for user review

**Use cases:**
- Agents consulting past similar work before starting new tasks
- Detecting when two agents have used different approaches to the same problem
- Escalating approach conflicts for human decision-making
- Building organizational knowledge over time

**For integration examples**, see:
- `examples/agent-integration-example.py` — Basic pre/post task flow
- `examples/agent-integration-sales-example.py` — Domain-specific example
- `examples/conflict-resolution-example.py` — Handling approach conflicts
- `docs/active-learning-guide.md` — Complete integration guide

---

Built on [MCP Memory Server](https://github.com/MenaceLabs/mcp_memory_server) by [MenaceLabs](https://github.com/MenaceLabs).
