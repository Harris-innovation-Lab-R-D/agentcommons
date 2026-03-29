#!/usr/bin/env python3
"""
openclaw-bridge.py — Bridge OpenClaw file-based agent memory into AgentCommons SQLite format.

Reads markdown memory files from an OpenClaw workspace, parses them into discrete
knowledge entries, strips PII, optionally embeds them, and writes a valid AgentCommons
dataset folder ready for submission.

Supports two OpenClaw memory file types:
  - MEMORY.md          — curated long-term memory with ## section headers
  - memory/YYYY-MM-DD.md — daily session logs in narrative form

Usage:
  python tools/openclaw-bridge.py \\
    --workspace /path/to/openclaw/workspace \\
    --tags federal-contracting,cmmc,compliance \\
    --out ./community/federal-contracting/federal-contracting-patterns \\
    --name federal-contracting-patterns \\
    --agent-type research \\
    --dry-run

  python tools/openclaw-bridge.py --workspace . --list-sections
"""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import struct
import sys
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tags that indicate personal/interpersonal content — never exportable.
# Mirrors the same constant in export.py.
BLOCKED_TAGS = {
    "personality", "relationship", "style", "personal", "private",
    "preferences", "feedback", "decision",
}

# Minimum character length for a parsed entry to be considered meaningful.
MIN_ENTRY_LENGTH = 60

# Maximum character length before an entry is considered suspiciously long
# (a sign that section-splitting failed). Warn but don't drop.
WARN_ENTRY_LENGTH = 4000

# Schema for the AgentCommons knowledge database.
KNOWLEDGE_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id        TEXT PRIMARY KEY,
    content   TEXT NOT NULL,
    embedding TEXT NOT NULL,
    tags      TEXT NOT NULL DEFAULT '[]',
    source_at TEXT NOT NULL
);
"""

# Required fields in AgentCommons metadata.json.
REQUIRED_METADATA_FIELDS = {
    "name", "version", "embedding_model", "topic_tags",
    "agent_type", "record_count", "language",
    "submitted_by", "submitted_at", "provenance", "description",
}

# Valid agent_type values per submission guide.
VALID_AGENT_TYPES = {"engineering", "research", "support", "ops", "other"}

# ---------------------------------------------------------------------------
# PII scrubbing patterns
# ---------------------------------------------------------------------------

# Each tuple: (pattern, replacement_label)
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    # URLs (http/https/ftp/ssh/git)
    (re.compile(r"\b(?:https?|ftp|ssh|git)://[^\s\"'<>]+"), "[URL]"),
    # www. URLs without scheme
    (re.compile(r"\bwww\.[A-Za-z0-9\-]+\.[A-Za-z]{2,}(?:/[^\s\"'<>]*)?"), "[URL]"),
    # Phone numbers: (xxx) xxx-xxxx, xxx-xxx-xxxx, +1-xxx-xxx-xxxx, etc.
    # The leading \(? allows matching the opening paren before the digit boundary.
    (re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"), "[PHONE]"),
    # "Name: Some Person" style fields — common in structured notes
    (re.compile(r"(?i)\b(?:name|author|contact|owner|by|from|to)\s*:\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"), "[NAME]"),
    # IPv4 addresses
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    # API keys / tokens — long alphanumeric strings that look like credentials
    (re.compile(r"\b(?:key|token|secret|password|passwd|api_key|apikey)\s*[=:]\s*\S+", re.IGNORECASE), "[CREDENTIAL]"),
    # JWT-shaped strings (three base64 segments separated by dots)
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"), "[JWT]"),
]

# Compile the name-verb pattern properly (the tuple above has a regex error for that case).
# We handle it separately for clarity.
_NAME_VERB_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(said|wrote|asked|replied|noted|mentioned|told)\b"
)


def scrub_pii(text: str) -> str:
    """
    Remove PII patterns from text using regex substitution.

    Replaces emails, URLs, phone numbers, IP addresses, credentials, JWTs,
    and name-in-label patterns with placeholder tokens.

    Returns the scrubbed text.
    """
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)

    # Handle name-before-verb separately: keep the verb, replace the name.
    text = _NAME_VERB_RE.sub(r"[NAME] \2", text)

    return text


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def parse_memory_md(content: str, filepath: Path) -> list[dict]:
    """
    Parse a curated MEMORY.md file (or any file with ## section headers).

    Splits on ## and ### headers.  Each section becomes one entry whose
    preliminary "tags" are the slugified header words.  The header text
    is preserved as the first line of the entry so content stays coherent.

    Returns a list of dicts: {content, tags, source_file, section_title}
    """
    entries = []
    # Split on lines that start with ## or ### (not ####)
    section_re = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    positions = [(m.start(), m.group(1), m.group(2)) for m in section_re.finditer(content)]

    if not positions:
        # No section headers — treat the whole file as one entry.
        text = content.strip()
        if len(text) >= MIN_ENTRY_LENGTH:
            entries.append({
                "content": text,
                "tags": [],
                "source_file": str(filepath),
                "section_title": filepath.stem,
            })
        return entries

    # Add a sentinel at the end.
    positions.append((len(content), "", ""))

    for i, (start, hashes, title) in enumerate(positions[:-1]):
        end = positions[i + 1][0]
        # The section body is everything after the header line.
        header_line_end = content.index("\n", start) + 1 if "\n" in content[start:] else end
        body = content[header_line_end:end].strip()

        if not body:
            continue

        # Combine header + body so each entry is self-contained.
        full_text = f"{title}\n\n{body}"

        # Derive preliminary tag candidates from the section header words.
        raw_tags = slugify_header_tags(title)

        entries.append({
            "content": full_text.strip(),
            "tags": raw_tags,
            "source_file": str(filepath),
            "section_title": title.strip(),
        })

    return entries


def parse_daily_log(content: str, filepath: Path) -> list[dict]:
    """
    Parse a daily session log (memory/YYYY-MM-DD.md).

    Daily logs are narrative — they don't always have section headers.
    Strategy:
      1. Split on any ## / ### headers (same as MEMORY.md).
      2. Within each section (or the whole file if no headers), further
         split on blank-line-separated paragraphs that are long enough.

    Returns a list of dicts: {content, tags, source_file, section_title}
    """
    # First try section-level splitting (same as MEMORY.md parser).
    section_entries = parse_memory_md(content, filepath)

    if section_entries:
        # Within each section, also split on paragraphs if the body is large.
        expanded = []
        for entry in section_entries:
            if len(entry["content"]) <= WARN_ENTRY_LENGTH:
                expanded.append(entry)
            else:
                paras = split_paragraphs(entry["content"], entry["tags"], filepath, entry["section_title"])
                expanded.extend(paras if paras else [entry])
        return expanded

    # No headers at all — split on paragraphs only.
    return split_paragraphs(content, [], filepath, filepath.stem)


def split_paragraphs(text: str, base_tags: list[str], filepath: Path, section_title: str) -> list[dict]:
    """
    Split text on double-newline paragraph breaks.

    Only keeps paragraphs that meet MIN_ENTRY_LENGTH and look substantive
    (contain at least one sentence-ending punctuation or a colon).
    """
    paragraphs = re.split(r"\n{2,}", text)
    entries = []
    for para in paragraphs:
        para = para.strip()
        if len(para) < MIN_ENTRY_LENGTH:
            continue
        # Require at least one period, colon, or question mark — filters out
        # pure bullet lists of single words and table-of-contents fragments.
        if not re.search(r"[.?!:]", para):
            continue
        entries.append({
            "content": para,
            "tags": list(base_tags),
            "source_file": str(filepath),
            "section_title": section_title,
        })
    return entries


def slugify_header_tags(header: str) -> list[str]:
    """
    Convert a section header string into a list of lowercase slug tags.

    e.g. "Federal Contracting Patterns" → ["federal-contracting-patterns"]
    """
    slug = re.sub(r"[^a-zA-Z0-9\s\-]", "", header).strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return [slug] if slug else []


# ---------------------------------------------------------------------------
# Workspace discovery
# ---------------------------------------------------------------------------

def discover_memory_files(workspace: Path, exclude_files: list[str]) -> list[Path]:
    """
    Discover all OpenClaw memory markdown files in the workspace.

    Returns paths to:
      - MEMORY.md (curated long-term memory) at workspace root
      - memory/YYYY-MM-DD.md daily logs in the memory/ subdirectory

    Files matching any pattern in exclude_files are skipped.
    """
    excluded = {Path(e).name for e in exclude_files} | set(exclude_files)
    files = []

    memory_md = workspace / "MEMORY.md"
    if memory_md.exists() and _not_excluded(memory_md, excluded):
        files.append(memory_md)

    memory_dir = workspace / "memory"
    if memory_dir.is_dir():
        for path in sorted(memory_dir.glob("*.md")):
            if _not_excluded(path, excluded):
                files.append(path)

    return files


def _not_excluded(path: Path, excluded: set[str]) -> bool:
    """Return True if the path should NOT be excluded."""
    return path.name not in excluded and str(path) not in excluded


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def generate_embedding_ollama(text: str, model: str = "nomic-embed-text") -> Optional[list[float]]:
    """
    Generate a real embedding vector via Ollama's local HTTP API.

    Returns a list of floats, or None if Ollama is unavailable.
    Requires ollama to be running locally (default port 11434).
    """
    try:
        import urllib.request
        payload = json.dumps({"model": model, "prompt": text}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("embedding")
    except Exception:
        return None


def generate_embedding_fallback(text: str) -> list[float]:
    """
    Bag-of-words hash embedding fallback (used when Ollama is unavailable).

    Produces a deterministic 384-dimensional float32 vector derived from
    the SHA-256 hash of each whitespace-split token in the text.  This
    preserves identity (same text → same vector) but carries NO semantic
    meaning.  Re-embed with a real model before submitting for production use.

    WARNING: These embeddings are NOT semantically meaningful.
    """
    dims = 384
    vector = [0.0] * dims
    tokens = text.lower().split()
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        # Unpack first `dims` bytes as uint8 and accumulate into vector
        for i, byte_val in enumerate(digest[:min(len(digest), dims)]):
            vector[i % dims] += (byte_val / 255.0) - 0.5

    # L2-normalize so cosine similarity is meaningful at least within the
    # hash space.
    magnitude = sum(v * v for v in vector) ** 0.5
    if magnitude > 0:
        vector = [v / magnitude for v in vector]

    return vector


def get_embedding(text: str, use_ollama: bool) -> tuple[list[float], str, bool]:
    """
    Get an embedding for text.

    Returns (vector, model_name, is_approximate).
    Tries Ollama first when use_ollama=True; falls back to bag-of-words hash.
    """
    if use_ollama:
        vec = generate_embedding_ollama(text)
        if vec is not None:
            return vec, "nomic-embed-text", False
        # Ollama not available — fall through to fallback.
        warnings.warn(
            "Ollama is not available. Using approximate bag-of-words hash embeddings.\n"
            "These embeddings are NOT semantically meaningful. Re-embed with\n"
            "'nomic-embed-text' before submitting to AgentCommons.",
            stacklevel=2,
        )

    return generate_embedding_fallback(text), "bow-hash-placeholder", True


# ---------------------------------------------------------------------------
# Entry ID generation
# ---------------------------------------------------------------------------

def make_entry_id(content: str, source_file: str) -> str:
    """
    Generate a stable, collision-resistant ID for a memory entry.

    Based on SHA-256 of the content + source filename. Truncated to 16 hex
    chars (64-bit) — collision probability is negligible for dataset sizes.
    """
    digest = hashlib.sha256(f"{source_file}:{content}".encode()).hexdigest()
    return digest[:16]


# ---------------------------------------------------------------------------
# Tag management
# ---------------------------------------------------------------------------

def merge_tags(entry_tags: list[str], user_tags: list[str]) -> list[str]:
    """
    Merge auto-detected section tags with user-supplied topic tags.

    User tags are always included; section tags are additive.
    Deduplicates and returns a sorted list.
    """
    merged = set(entry_tags) | set(user_tags)
    return sorted(merged)


def has_blocked_tag(tags: list[str]) -> bool:
    """
    Return True if any tag in the list matches a blocked tag.

    Checks both exact matches and individual words within hyphenated slug tags
    (e.g. 'personal-notes' is blocked because it contains the word 'personal').
    """
    for tag in tags:
        if tag in BLOCKED_TAGS:
            return True
        # Check each hyphen-separated word in a slug tag.
        for word in tag.split("-"):
            if word in BLOCKED_TAGS:
                return True
    return False


# ---------------------------------------------------------------------------
# Metadata validation
# ---------------------------------------------------------------------------

def validate_metadata(metadata: dict) -> list[str]:
    """
    Validate a metadata dict against the AgentCommons spec.

    Returns a list of validation error strings.  Empty list means valid.
    """
    errors = []

    missing = REQUIRED_METADATA_FIELDS - set(metadata.keys())
    if missing:
        errors.append(f"Missing required fields: {', '.join(sorted(missing))}")

    if "agent_type" in metadata and metadata["agent_type"] not in VALID_AGENT_TYPES:
        errors.append(
            f"Invalid agent_type '{metadata['agent_type']}'. "
            f"Must be one of: {', '.join(sorted(VALID_AGENT_TYPES))}"
        )

    if "version" in metadata:
        if not re.match(r"^\d+\.\d+\.\d+$", str(metadata["version"])):
            errors.append(f"version must be semver (e.g. '1.0.0'), got: {metadata['version']!r}")

    if "topic_tags" in metadata:
        if not isinstance(metadata["topic_tags"], list) or not metadata["topic_tags"]:
            errors.append("topic_tags must be a non-empty list")

    if "record_count" in metadata:
        if not isinstance(metadata["record_count"], int) or metadata["record_count"] < 0:
            errors.append("record_count must be a non-negative integer")

    if "language" in metadata:
        if not re.match(r"^[a-z]{2}$", str(metadata["language"])):
            errors.append(f"language should be a 2-letter ISO 639-1 code, got: {metadata['language']!r}")

    if "provenance" in metadata:
        if not isinstance(metadata["provenance"], list):
            errors.append("provenance must be a list")

    if "submitted_at" in metadata:
        try:
            datetime.fromisoformat(metadata["submitted_at"])
        except ValueError:
            errors.append(f"submitted_at must be ISO 8601 date (YYYY-MM-DD), got: {metadata['submitted_at']!r}")

    return errors


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def load_and_parse_workspace(
    workspace: Path,
    exclude_files: list[str],
) -> list[dict]:
    """
    Discover and parse all memory files in the workspace.

    Returns a flat list of raw entry dicts (content, tags, source_file,
    section_title).  Entries are not yet filtered, scrubbed, or embedded.
    """
    files = discover_memory_files(workspace, exclude_files)
    if not files:
        print("No memory files found in workspace.")
        print(f"Expected: {workspace}/MEMORY.md or {workspace}/memory/YYYY-MM-DD.md")
        return []

    all_entries = []
    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"Warning: could not read {filepath}: {exc}", file=sys.stderr)
            continue

        if filepath.name == "MEMORY.md":
            entries = parse_memory_md(content, filepath)
        else:
            entries = parse_daily_log(content, filepath)

        all_entries.extend(entries)

    return all_entries


def filter_entries(
    entries: list[dict],
    filter_tags: list[str],
) -> tuple[list[dict], list[dict]]:
    """
    Filter entries to those matching filter_tags (if provided) and not blocked.

    Returns (exportable, filtered_out) — both are lists of entry dicts.
    """
    exportable = []
    filtered_out = []

    for entry in entries:
        # Auto-block entries whose auto-detected tags contain blocked tags.
        if has_blocked_tag(entry["tags"]):
            filtered_out.append(entry)
            continue

        # If the user supplied topic tags, only export entries whose
        # section-derived tags overlap with any of the requested tags,
        # OR entries from MEMORY.md sections (which get included by default
        # when tags are broad enough to warrant exporting that file).
        # When no filter_tags given, export everything non-blocked.
        if filter_tags:
            entry_tag_set = set(entry["tags"])
            filter_tag_set = set(filter_tags)
            if not (entry_tag_set & filter_tag_set):
                filtered_out.append(entry)
                continue

        exportable.append(entry)

    return exportable, filtered_out


def process_entries(
    entries: list[dict],
    user_tags: list[str],
    use_ollama: bool,
) -> tuple[list[dict], str, bool]:
    """
    Scrub PII, generate embeddings, and merge tags for each exportable entry.

    Returns (processed_entries, embedding_model_name, embeddings_are_approximate).
    All entries in the returned list are ready to insert into the database.
    """
    processed = []
    embedding_model = None
    approximate = False
    ollama_warned = False

    for entry in entries:
        scrubbed = scrub_pii(entry["content"])

        # Warn if entry is suspiciously long (may indicate parsing gap).
        if len(scrubbed) > WARN_ENTRY_LENGTH:
            print(
                f"Warning: entry from {entry['source_file']} (section: '{entry['section_title']}') "
                f"is {len(scrubbed)} chars — consider adding ## headers to split it further.",
                file=sys.stderr,
            )

        merged_tags = merge_tags(entry["tags"], user_tags)
        entry_id = make_entry_id(scrubbed, entry["source_file"])

        vec, model, is_approx = get_embedding(scrubbed, use_ollama)
        embedding_model = model
        if is_approx and not ollama_warned:
            approximate = True
            ollama_warned = True

        processed.append({
            "id": entry_id,
            "content": scrubbed,
            "embedding": json.dumps(vec),
            "tags": json.dumps(merged_tags),
            "source_at": date.today().isoformat(),
            "section_title": entry["section_title"],
            "source_file": entry["source_file"],
        })

    return processed, (embedding_model or "bow-hash-placeholder"), approximate


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_knowledge_db(out_path: Path, entries: list[dict]) -> None:
    """
    Write entries to a knowledge.db SQLite file in AgentCommons format.

    Overwrites any existing file at that path.
    """
    db_path = out_path / "knowledge.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    conn.executescript(KNOWLEDGE_DB_SCHEMA)

    for entry in entries:
        conn.execute(
            "INSERT OR IGNORE INTO memories (id, content, embedding, tags, source_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (entry["id"], entry["content"], entry["embedding"], entry["tags"], entry["source_at"]),
        )

    conn.commit()
    conn.close()


def write_metadata_json(
    out_path: Path,
    name: str,
    tags: list[str],
    agent_type: str,
    record_count: int,
    embedding_model: str,
    approximate_embeddings: bool,
) -> dict:
    """
    Write metadata.json to out_path.  Returns the metadata dict.
    """
    description = (
        f"Domain knowledge dataset covering: {', '.join(tags)}. "
        f"Generated from OpenClaw workspace memory files via openclaw-bridge."
    )
    if approximate_embeddings:
        description += (
            " NOTE: embeddings are approximate (bag-of-words hash) — "
            "re-embed with nomic-embed-text before production use."
        )

    metadata = {
        "name": name,
        "version": "1.0.0",
        "embedding_model": embedding_model,
        "topic_tags": tags,
        "agent_type": agent_type,
        "record_count": record_count,
        "language": "en",
        "submitted_by": "your-github-username",
        "submitted_at": date.today().isoformat(),
        "provenance": [],
        "description": description,
    }

    errors = validate_metadata(metadata)
    if errors:
        # This should never happen with the defaults above — surface it anyway.
        print("Warning: metadata validation errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)

    (out_path / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def write_readme(out_path: Path, name: str, metadata: dict) -> None:
    """
    Write a pre-filled README.md from the AgentCommons template.

    Copies the template if available, otherwise writes a minimal version.
    """
    template_path = Path(__file__).parent.parent / "submissions" / ".template" / "README.md"
    if template_path.exists():
        shutil.copy(template_path, out_path / "README.md")
    else:
        tags_str = ", ".join(metadata.get("topic_tags", []))
        count = metadata.get("record_count", 0)
        model = metadata.get("embedding_model", "nomic-embed-text")
        agent_type = metadata.get("agent_type", "engineering")
        readme = (
            f"# {name}\n\n"
            f"**Version:** {metadata.get('version', '1.0.0')}\n"
            f"**Embedding Model:** {model}\n"
            f"**Topics:** {tags_str}\n"
            f"**Records:** {count}\n"
            f"**Agent Type:** {agent_type}\n\n"
            "---\n\n"
            "## What This Dataset Contains\n\n"
            "[Fill in: what domain knowledge does this dataset cover?]\n\n"
            "---\n\n"
            "## How It Was Generated\n\n"
            "Generated from OpenClaw workspace memory files using `tools/openclaw-bridge.py`.\n\n"
            "---\n\n"
            "## Known Gaps or Limitations\n\n"
            "[Fill in: what does this dataset NOT cover well?]\n\n"
            "---\n\n"
            "## Compatibility\n\n"
            f"- **Embedding model:** {model}\n"
            "- **Re-embedding required:** "
            + ("Yes — placeholder embeddings were used during export." if "placeholder" in model else "No")
            + "\n"
        )
        (out_path / "README.md").write_text(readme)


# ---------------------------------------------------------------------------
# CLI sub-commands
# ---------------------------------------------------------------------------

def cmd_list_sections(workspace: Path, exclude_files: list[str]) -> None:
    """
    Print a preview of all sections that would be parsed from the workspace.

    Does not write any output files.
    """
    entries = load_and_parse_workspace(workspace, exclude_files)
    if not entries:
        return

    by_file: dict[str, list[dict]] = {}
    for entry in entries:
        by_file.setdefault(entry["source_file"], []).append(entry)

    total = 0
    for filepath, file_entries in by_file.items():
        print(f"\n{filepath}")
        print("  " + "-" * (len(filepath)))
        for entry in file_entries:
            title = entry["section_title"]
            chars = len(entry["content"])
            tags_preview = ", ".join(entry["tags"]) if entry["tags"] else "(no tags)"
            blocked = " [BLOCKED]" if has_blocked_tag(entry["tags"]) else ""
            print(f"  • {title!r:<40}  {chars:>5} chars  tags: {tags_preview}{blocked}")
            total += 1

    print(f"\nTotal sections found: {total}")
    print("\nTo export, omit --list-sections and add your --tags filter.")


def cmd_export(
    workspace: Path,
    filter_tags: list[str],
    exclude_files: list[str],
    out_path: Path,
    name: str,
    agent_type: str,
    dry_run: bool,
    no_ollama: bool,
) -> None:
    """
    Main export command: parse → filter → scrub → embed → write.
    """
    # 1. Load and parse all memory files.
    all_entries = load_and_parse_workspace(workspace, exclude_files)
    if not all_entries:
        return

    total_found = len(all_entries)

    # 2. Filter by tags and blocked status.
    exportable, filtered_out = filter_entries(all_entries, filter_tags)

    blocked_count = sum(1 for e in filtered_out if has_blocked_tag(e["tags"]))
    tag_mismatch_count = len(filtered_out) - blocked_count

    print(f"\nParsed {total_found} entries from {workspace}")
    print(f"  Blocked (personal tags):   {blocked_count}")
    print(f"  Filtered (tag mismatch):   {tag_mismatch_count}")
    print(f"  Exportable:                {len(exportable)}")

    if not exportable:
        print("\nNo exportable entries found.")
        if filter_tags:
            print(f"Requested tags: {filter_tags}")
            print("Try --list-sections to see what sections are available.")
        return

    if dry_run:
        print("\n[DRY RUN] The following entries would be exported:\n")
        for i, entry in enumerate(exportable, 1):
            preview = entry["content"][:120].replace("\n", " ")
            print(f"  {i:3}. [{entry['section_title']}] {preview}...")
        print(f"\n[DRY RUN] Total: {len(exportable)} entries. No files written.")
        return

    # 3. Scrub PII and generate embeddings.
    use_ollama = not no_ollama
    processed, embedding_model, approximate = process_entries(exportable, filter_tags, use_ollama)

    if approximate:
        print(
            "\nWARNING: Ollama not available. Embeddings are approximate (bag-of-words hash).\n"
            "         Re-embed with nomic-embed-text before submitting to AgentCommons.\n"
            "         Install Ollama: https://ollama.ai/ then run: ollama pull nomic-embed-text"
        )

    # 4. Write output.
    out_path.mkdir(parents=True, exist_ok=True)
    write_knowledge_db(out_path, processed)
    metadata = write_metadata_json(
        out_path, name, filter_tags or [], agent_type,
        len(processed), embedding_model, approximate,
    )
    write_readme(out_path, name, metadata)

    print(f"\nExport complete.")
    print(f"  Records exported:  {len(processed)}")
    print(f"  Embedding model:   {embedding_model}")
    print(f"  Output:            {out_path}/")
    print()
    print("Next steps:")
    print(f"  1. Review {out_path}/knowledge.db for any remaining sensitive content")
    print(f"  2. Fill in {out_path}/metadata.json (submitted_by, description)")
    print(f"  3. Fill in {out_path}/README.md")
    print(f"  4. Run: python tools/validate.py --dataset {out_path}")
    print(f"  5. Submit via Pull Request to community/<topic>/{name}/")


# ---------------------------------------------------------------------------
# Argument parsing and entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bridge OpenClaw file-based agent memory into AgentCommons SQLite format.\n"
            "Reads MEMORY.md and memory/YYYY-MM-DD.md files, strips PII, and produces\n"
            "a submission-ready AgentCommons dataset folder."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Preview sections in current workspace
  python tools/openclaw-bridge.py --workspace . --list-sections

  # Export with real embeddings (requires Ollama)
  python tools/openclaw-bridge.py \\
    --workspace /path/to/workspace \\
    --tags federal-contracting,cmmc \\
    --out ./community/federal-contracting/fc-patterns \\
    --name fc-patterns \\
    --agent-type research

  # Dry run to preview entries before writing
  python tools/openclaw-bridge.py --workspace . --tags infra --out /tmp/x --dry-run

  # Export without Ollama (uses approximate hash embeddings)
  python tools/openclaw-bridge.py --workspace . --tags k8s --out ./k8s-out --no-ollama
""",
    )

    parser.add_argument(
        "--workspace",
        default=".",
        help="Path to OpenClaw workspace (default: current directory).",
    )
    parser.add_argument(
        "--tags",
        default=None,
        help="Comma-separated topic tags to include (e.g. 'cmmc,compliance'). "
             "If omitted, all non-blocked entries are exported.",
    )
    parser.add_argument(
        "--exclude-files",
        default="",
        help="Comma-separated filenames to skip (e.g. 'MEMORY.md' to skip curated memory).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for the dataset. Required unless --list-sections.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Dataset name (defaults to tags joined by dashes, or workspace folder name).",
    )
    parser.add_argument(
        "--agent-type",
        default="engineering",
        choices=sorted(VALID_AGENT_TYPES),
        help="Agent type for metadata.json (default: engineering).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be exported without writing any files.",
    )
    parser.add_argument(
        "--no-ollama",
        action="store_true",
        help="Skip Ollama and use approximate hash embeddings (faster but not semantic).",
    )
    parser.add_argument(
        "--list-sections",
        action="store_true",
        help="Preview all parsed sections in the workspace without exporting.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        parser.error(f"--workspace path does not exist or is not a directory: {workspace}")

    exclude_files = [f.strip() for f in args.exclude_files.split(",") if f.strip()]

    if args.list_sections:
        cmd_list_sections(workspace, exclude_files)
        return

    if not args.out and not args.dry_run:
        parser.error("--out is required unless using --list-sections or --dry-run")

    filter_tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    # Derive dataset name: explicit > tags > workspace folder name.
    if args.name:
        name = args.name
    elif filter_tags:
        name = "-".join(filter_tags)
    else:
        name = workspace.name

    out_path = Path(args.out).expanduser().resolve() if args.out else Path(f"/tmp/{name}")

    cmd_export(
        workspace=workspace,
        filter_tags=filter_tags,
        exclude_files=exclude_files,
        out_path=out_path,
        name=name,
        agent_type=args.agent_type,
        dry_run=args.dry_run,
        no_ollama=args.no_ollama,
    )


if __name__ == "__main__":
    main()
