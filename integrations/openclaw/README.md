# AgentCommons Integration - OpenClaw Workspace

This skill provides **OpenClaw-specific integration** with AgentCommons (a federated agent memory network).

## What's Here vs What's Upstream

### Local to This Workspace (Proprietary)
- `agentcommons_client.py` — OpenClaw client wrapper (Harris-specific initialization)
- `cache_management.py` — Harris-specific caching strategies
- `example_federal_contracting.py` — Harris contracting patterns (reference only)
- `SKILL.md` — OpenClaw integration guide (how to use in your agents)

### Contributed to Upstream (`hil/agentcommons/`)
The following **generic, reusable modules** are maintained upstream for community contribution:

- **Tools** (upstream in `hil/agentcommons/tools/`)
  - `agentcommons_pretask.py` — Pre-task query module
  - `agentcommons_posttask.py` — Post-task export module
  - `agentcommons_active.py` — Unified active learning integration
  - `agentcommons_conflict.py` — Conflict detection and management

- **Examples** (upstream in `hil/agentcommons/examples/`)
  - `agent-integration-example.py` — Generic integration pattern
  - `agent-integration-sales-example.py` — Domain-specific pattern
  - `conflict-resolution-example.py` — Conflict workflow

- **Documentation** (upstream in `hil/agentcommons/docs/`)
  - `active-learning-guide.md` — Complete integration guide for any organization

- **Tests** (upstream in `hil/agentcommons/tests/`)
  - `test_active_learning.py` — Test suite for active learning modules

- **Deployment** (upstream in `hil/agentcommons/docker/`)
  - `docker-compose.yml` — Standard deployment configuration
  - `.env.example` — Configuration template

## Organization Principle

**Separate by audience:**

- **Upstream (`hil/agentcommons/`)** — Reusable for *any organization* (no Harris references)
- **Workspace (this directory)** — Harris-specific (proprietary data, integration patterns)

This makes it clear what's contributing to the community and what stays private.

## Usage in OpenClaw

```python
from skills.agentcommons_integration.python_modules.agentcommons_client import AgentCommonsClient

client = AgentCommonsClient()
results = client.query_by_tag("#federal-contracting")
```

## Documentation

- **Setup & deployment:** See `hil/AGENTCOMMONS_SETUP_WORKSPACE.md` (Harris-specific)
- **Generic integration:** See `hil/agentcommons/DEPLOYMENT_GUIDE.md` (upstream)
- **Active learning guide:** See `hil/agentcommons/docs/active-learning-guide.md` (upstream)
- **OpenClaw skill guide:** See `SKILL.md` (this directory)

## Contributing Back to AgentCommons

When the active learning system matures:

1. Modules in `hil/agentcommons/` are ready to submit
2. Open a PR to [QuiGonGitt/agentcommons](https://github.com/QuiGonGitt/agentcommons)
3. Keep workspace repo clean (Harris data stays local)
4. Continue using upstream modules via `import` statements

See `hil/agentcommons/docs/submission-guide.md` for upstream contribution process.
