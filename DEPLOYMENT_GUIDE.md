# AgentCommons Deployment Guide

This guide covers generic deployment of AgentCommons for any organization. For OpenClaw-specific integration, see the workspace documentation.

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- SQLite3
- Network access to MCP Memory Server (or bundled via Docker)

## Quick Start with Docker Compose

### 1. Configure Environment

Copy the example config:

```bash
cp docker/.env.example docker/.env
```

Edit `docker/.env` with your settings:

```env
# AgentCommons API Port
AGENTCOMMONS_PORT=8765

# PostgreSQL (if using managed database instead of SQLite)
DATABASE_URL=sqlite:///agentcommons.db

# MCP Memory Server Configuration
MCP_MEMORY_PORT=8766
MCP_MEMORY_HOST=mcp-memory

# Optional: Embedding service
EMBEDDING_SERVICE_URL=http://localhost:8769

# API Authentication (optional)
AGENTCOMMONS_API_KEY=your-secret-key-here
```

### 2. Start Services

```bash
cd docker
docker-compose up -d
```

This starts:
- **AgentCommons API** on port 8765 (SQLite backend)
- **MCP Memory Server** on port 8766 (if bundled)
- Database migrations run automatically

### 3. Verify Deployment

```bash
# Check health
curl http://localhost:8765/health

# List databases
curl http://localhost:8765/databases

# Check MCP server
curl http://localhost:8766/status
```

## Database Setup

### SQLite (Default - Recommended for Single-Node)

Built into Docker Compose. Database file: `data/agentcommons.db`

**Migrations run automatically on startup** via the container entrypoint.

### Manual Migration (if needed)

```bash
# Apply pending migrations
sqlite3 data/agentcommons.db < migrations/add-conflicts-table.sql
```

## Integration with Agents

### Python Client

```python
from agentcommons_client import AgentCommonsClient

# Auto-detects http://localhost:8765
client = AgentCommonsClient()

# Query institutional memory
results = client.query_by_similarity("Your query here")
```

### API Endpoint

```bash
# Query by tag
curl "http://localhost:8765/query?tag=%23your-tag&limit=10"

# Similarity search
curl -X POST http://localhost:8765/similarity \
  -H "Content-Type: application/json" \
  -d '{"query": "Your query", "limit": 5}'

# Export memories
curl "http://localhost:8765/export?agent_type=your-type" > exported.db
```

## Active Learning Integration

### Pre-Task Query

Before starting a task, agents query for related past work:

```python
from agentcommons_pretask import PreTaskQuery

pretask = PreTaskQuery(api_url="http://localhost:8765")
context = pretask.query_and_check_conflicts(
    domain="your-domain",
    topic="your-task-topic",
    task_id="task-001"
)

# Review conflicts if any
if context['conflicts']:
    print(f"Conflicts detected: {context['conflicts_count']}")
    # Escalate for user decision
```

### Post-Task Export

After completing work, export learnings:

```python
from agentcommons_posttask import PostTaskExport

export = PostTaskExport(api_url="http://localhost:8765")
result = export.export_and_detect_conflicts(
    agent_output=task_result,
    domain="your-domain",
    task_id="task-001",
    outcome="success",
    metadata={"key": "value"}
)
```

### Conflict Resolution

Compare competing approaches and manage decisions:

```python
from agentcommons_conflict import ConflictManager

manager = ConflictManager(api_url="http://localhost:8765")
conflict = manager.analyze_conflict(
    approach_a=work_from_agent1,
    approach_b=work_from_agent2,
    context="Task domain and specifics"
)

decision = manager.record_decision(
    conflict_id=conflict['id'],
    selected_approach="approach_a",
    rationale="This approach is better because..."
)
```

## Monitoring

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
```

### Health Checks

```bash
# API health
curl http://localhost:8765/health

# Database status
curl http://localhost:8765/status
```

### Performance Metrics

```bash
# Cache statistics
curl http://localhost:8765/metrics/cache

# Query performance
curl http://localhost:8765/metrics/queries
```

## Scaling Considerations

### Single-Node Deployment (SQLite)
- ✅ Simple setup
- ✅ No external database
- ⚠️ Limited to ~10K concurrent queries/sec
- ⚠️ Not suitable for high-concurrency scenarios

### Multi-Node Deployment (PostgreSQL)
For larger deployments, use PostgreSQL instead:

1. Set `DATABASE_URL=postgresql://user:pass@host/agentcommons` in `.env`
2. Ensure PostgreSQL is running and migrations are applied
3. Run multiple `agentcommons-api` containers behind a load balancer

## Security Considerations

### Authentication

Set `AGENTCOMMONS_API_KEY` in `.env` to require API key authentication:

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8765/health
```

### Network Isolation

For production deployments:

1. Run AgentCommons in a private network (not exposed to the internet)
2. Use a reverse proxy (nginx, Traefik) with authentication
3. Implement network ACLs to restrict agent access
4. Use TLS for all API traffic

### Data Privacy

- Only store domain-scoped memories (no PII)
- Regular backups of `data/agentcommons.db`
- Audit logs for sensitive queries
- Implement data retention policies

## Backup & Recovery

### Backup Database

```bash
# SQLite
cp data/agentcommons.db backups/agentcommons-$(date +%Y%m%d).db

# Or with docker-compose
docker-compose exec api sqlite3 /data/agentcommons.db ".backup backups/agentcommons.db"
```

### Restore Database

```bash
docker-compose down
cp backups/agentcommons-YYYYMMDD.db data/agentcommons.db
docker-compose up -d
```

## Troubleshooting

### "Connection refused" on startup

Check if ports are already in use:

```bash
lsof -i :8765  # AgentCommons API
lsof -i :8766  # MCP Memory Server
```

Kill conflicting processes or change ports in `.env`.

### Database locked errors

SQLite can have concurrency issues. Solutions:

1. Restart the container: `docker-compose restart api`
2. Switch to PostgreSQL for higher concurrency
3. Increase WAL (Write-Ahead Logging) timeout in config

### Slow queries

Check cache hit rate:

```bash
curl http://localhost:8765/metrics/cache
```

Consider:
- Increasing cache size in `.env`
- Restricting query scope (date ranges, filters)
- Upgrading to PostgreSQL with better indexing

## Production Checklist

- [ ] Set strong `AGENTCOMMONS_API_KEY`
- [ ] Configure persistent volume for `data/`
- [ ] Set up automated backups
- [ ] Enable TLS/HTTPS
- [ ] Implement monitoring and alerting
- [ ] Document backup/recovery procedures
- [ ] Plan capacity based on query volume
- [ ] Test failover procedures
- [ ] Review privacy policy for stored memories
- [ ] Set up log aggregation

## Next Steps

1. Review `docs/active-learning-guide.md` for agent integration
2. Check `examples/` for your agent framework
3. Set up monitoring and alerting
4. Plan data retention and governance policies
5. Test integration with your agents in a staging environment
