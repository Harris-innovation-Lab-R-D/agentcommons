# openclaw-bridge — Export OpenClaw Memory to AgentCommons

`tools/openclaw-bridge.py` converts OpenClaw file-based agent memory into the AgentCommons
SQLite dataset format, making it easy to contribute domain knowledge without running an
MCP server.

---

## What It Does

OpenClaw stores agent memory as plain markdown files.  This tool:

1. Reads `MEMORY.md` (curated long-term memory) and `memory/YYYY-MM-DD.md` (daily logs)
2. Splits each file into discrete, self-contained knowledge entries by section header and paragraph
3. Strips PII — emails, URLs, phone numbers, IP addresses, credentials, and name patterns
4. Generates embeddings via `nomic-embed-text` (Ollama) or falls back to approximate hash vectors
5. Writes a valid `knowledge.db` + `metadata.json` + `README.md` dataset folder

---

## Prerequisites

**Python 3.10+** — no third-party packages required (stdlib only).

**Optional: Ollama** for real semantic embeddings:

```bash
# Install Ollama: https://ollama.ai/
ollama pull nomic-embed-text
```

If Ollama is not running, the tool falls back to bag-of-words hash embeddings and prints a
clear warning.  Hash embeddings are deterministic but carry no semantic meaning — re-embed
before submitting to AgentCommons.

---

## Quick Start

```bash
# 1. Preview what sections exist in your workspace
python tools/openclaw-bridge.py --workspace /path/to/workspace --list-sections

# 2. Dry run — see what would be exported without writing files
python tools/openclaw-bridge.py \
  --workspace /path/to/workspace \
  --tags federal-contracting,cmmc \
  --out ./community/federal-contracting/fc-patterns \
  --dry-run

# 3. Export for real
python tools/openclaw-bridge.py \
  --workspace /path/to/workspace \
  --tags federal-contracting,cmmc,compliance \
  --out ./community/federal-contracting/fc-patterns \
  --name fc-patterns \
  --agent-type research
```

---

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--workspace PATH` | `.` | Path to OpenClaw workspace directory |
| `--tags TAG,TAG,...` | *(all)* | Topic tags to filter entries by (comma-separated) |
| `--exclude-files FILE,...` | *(none)* | Files to skip (e.g. `MEMORY.md` to skip curated memory) |
| `--out PATH` | *(required)* | Output directory for the dataset folder |
| `--name NAME` | tags joined by `-` | Dataset name for metadata |
| `--agent-type TYPE` | `engineering` | One of: `engineering`, `research`, `support`, `ops`, `other` |
| `--dry-run` | off | Preview entries without writing files |
| `--no-ollama` | off | Skip Ollama; use approximate hash embeddings |
| `--list-sections` | off | Preview parsed sections; no export |

---

## How Parsing Works

### `MEMORY.md` (curated memory)

Split on `##` and `###` section headers.  Each section becomes one entry.  The header text
is prepended to the body so each entry is self-contained.  Auto-derived tags come from the
slugified header words.

### `memory/YYYY-MM-DD.md` (daily logs)

Same section-based splitting.  When a section body exceeds 4 000 characters, it is further
split on paragraph breaks (double newlines).  Paragraphs shorter than 60 characters or
lacking sentence punctuation are dropped.

### Blocked content

Entries whose auto-derived section tags match any of these are never exported:

```
personality  relationship  style  personal  private  preferences  feedback  decision
```

---

## PII Scrubbing

The tool applies regex patterns to remove:

- Email addresses → `[EMAIL]`
- HTTP/HTTPS/FTP/SSH/Git URLs → `[URL]`
- Phone numbers → `[PHONE]`
- IPv4 addresses → `[IP]`
- API keys / tokens in `key=value` form → `[CREDENTIAL]`
- JWT-shaped strings → `[JWT]`
- `Name: Full Name` style fields → `[NAME]`

**Important:** Automated scrubbing is not exhaustive.  Always review `knowledge.db`
before submitting — the submission guide requires a manual review pass.

---

## Embedding Models

| Situation | Model used | Semantic? |
|-----------|-----------|-----------|
| Ollama running with `nomic-embed-text` | `nomic-embed-text` | Yes |
| Ollama not available | `bow-hash-placeholder` | No — re-embed required |
| `--no-ollama` flag | `bow-hash-placeholder` | No — re-embed required |

To re-embed an existing dataset after installing Ollama:

```bash
python tools/openclaw-bridge.py \
  --workspace /path/to/workspace \
  --tags your-tags \
  --out ./your-dataset   # overwrites knowledge.db
```

The `embedding_model` field in `metadata.json` is set automatically.

---

## Output Structure

```
your-dataset/
├── knowledge.db     # SQLite, same schema as AgentCommons MCP server
├── metadata.json    # Dataset metadata (fill in submitted_by, description)
└── README.md        # Template — fill in before submitting
```

---

## After Exporting

Follow the standard AgentCommons submission workflow:

```bash
# 1. Validate the dataset
python tools/validate.py --dataset ./your-dataset

# 2. Fill in metadata.json and README.md

# 3. Copy to community/<primary-topic>/<dataset-name>/
cp -r ./your-dataset ./community/federal-contracting/fc-patterns/

# 4. Open a Pull Request with title: [submission] fc-patterns v1.0.0
```

See [submission-guide.md](./submission-guide.md) for the full workflow.

---

## Excluding Sensitive Sections

If your `MEMORY.md` has sections you never want exported (org names, client details, etc.),
either:

- Add a blocked tag to those sections in the source file, or
- Skip the entire file with `--exclude-files MEMORY.md` and export from daily logs only, or
- Use `--list-sections` to identify the section names, then use `--tags` to select only
  the sections you want

---

## Differences from `export.py`

| | `export.py` | `openclaw-bridge.py` |
|---|---|---|
| Source | MCP Memory Server `memory.db` | OpenClaw markdown files |
| Input format | SQLite (already structured) | Markdown (needs parsing) |
| Embeddings | Pre-computed in MCP server | Generated on export (or fallback) |
| PII scrubbing | Minimal (MCP server handles it) | Full regex scrub pass |
| Scope filter | `WHERE scope = 'team'` | All non-blocked sections |
