#!/usr/bin/env python3
"""
distill.py — Distillation merge tool for AgentCommons.

Takes multiple datasets, clusters semantically similar records,
runs an LLM synthesis pass over each cluster, and produces a
single high-quality canonical dataset with full provenance records.

This is how AgentCommons produces official distillation releases.

Usage:
  python distill.py \\
    --datasets community/cloudflare/workers-v1 community/cloudflare/dns-v1 \\
    --out distillations/cloudflare-v1.0.0 \\
    --embed-model nomic-embed-text \\
    --llm-model gemma3:12b

  python distill.py \\
    --datasets community/kubernetes/k8s-patterns \\
    --out distillations/kubernetes-v1.0.0 \\
    --cluster-threshold 0.85
"""

import argparse
import json
import math
import secrets
import sqlite3
import urllib.request
import urllib.error
from datetime import date, datetime, timezone
from pathlib import Path

AGENTCOMMONS_ROOT = Path(__file__).parent.parent
OLLAMA_URL        = "http://localhost:11434"
DEFAULT_EMBED     = "nomic-embed-text"
DEFAULT_LLM       = "gemma3:12b"
DEFAULT_THRESHOLD = 0.85   # Similarity threshold for clustering


# ── Ollama helpers ─────────────────────────────────────────────────────────────

def get_embedding(text: str, model: str) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["embedding"]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def synthesize_cluster(records: list[str], model: str) -> str:
    """
    Run an LLM pass over a cluster of semantically similar records.
    Produces a single high-quality canonical record.
    """
    if len(records) == 1:
        return records[0]

    numbered = "\n".join(f"{i+1}. {r}" for i, r in enumerate(records))
    prompt = (
        "The following are semantically similar knowledge records from different AI agents. "
        "Synthesize them into a single, high-quality canonical record that captures the most "
        "accurate, complete, and useful version of the knowledge. "
        "Be concise. Do not include meta-commentary about the synthesis process. "
        "Output only the synthesized knowledge record.\n\n"
        f"Records:\n{numbered}\n\n"
        "Synthesized record:"
    )

    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read()).get("response", "").strip()
    except urllib.error.URLError as e:
        # Fallback: return the longest record if LLM is unavailable
        print(f"  Warning: LLM synthesis failed ({e}), using longest record as fallback.")
        return max(records, key=len)


# ── Dataset loading ────────────────────────────────────────────────────────────

def resolve_path(p: str) -> Path:
    path = Path(p)
    if path.exists():
        return path
    relative = AGENTCOMMONS_ROOT / p
    if relative.exists():
        return relative
    raise FileNotFoundError(f"Dataset not found: {p}")


def load_dataset(path: Path) -> tuple[list[dict], dict]:
    db_path = path / "knowledge.db"
    meta_path = path / "metadata.json"

    if not db_path.exists():
        raise FileNotFoundError(f"knowledge.db not found in {path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM memories").fetchall()]
    conn.close()

    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return rows, metadata


# ── Clustering ────────────────────────────────────────────────────────────────

def cluster_records(records: list[dict], embed_model: str, threshold: float) -> list[list[dict]]:
    """
    Group records into clusters where members are above the similarity threshold.
    Uses greedy single-linkage clustering.
    """
    print(f"  Embedding {len(records)} records for clustering...")
    for i, rec in enumerate(records):
        if "embedding" not in rec or not rec["embedding"]:
            rec["_emb"] = get_embedding(rec["content"], embed_model)
        else:
            rec["_emb"] = json.loads(rec["embedding"]) if isinstance(rec["embedding"], str) else rec["embedding"]
        if (i + 1) % 10 == 0:
            print(f"    {i+1}/{len(records)} embedded...")

    clusters = []
    assigned = [False] * len(records)

    for i, rec in enumerate(records):
        if assigned[i]:
            continue
        cluster = [rec]
        assigned[i] = True
        for j, other in enumerate(records):
            if assigned[j] or i == j:
                continue
            if cosine_similarity(rec["_emb"], other["_emb"]) >= threshold:
                cluster.append(other)
                assigned[j] = True
        clusters.append(cluster)

    return clusters


# ── Main distillation ─────────────────────────────────────────────────────────

def distill(dataset_paths: list[str], out_path: Path, embed_model: str, llm_model: str, threshold: float) -> None:
    print(f"\nAgentCommons Distillation")
    print(f"  Datasets:          {len(dataset_paths)}")
    print(f"  Output:            {out_path}")
    print(f"  Embedding model:   {embed_model}")
    print(f"  LLM model:         {llm_model}")
    print(f"  Cluster threshold: {threshold}")
    print()

    # Load all source datasets
    all_records = []
    source_refs = []
    total_input = 0

    for ds_path_str in dataset_paths:
        path = resolve_path(ds_path_str)
        records, metadata = load_dataset(path)
        all_records.extend(records)
        total_input += len(records)
        version = metadata.get("version", "unknown")
        source_refs.append(f"{ds_path_str}@{version}")
        print(f"  Loaded: {path.name} — {len(records)} records")

    print(f"\n  Total input records: {total_input}")
    print()

    # Cluster
    print("Clustering...")
    clusters = cluster_records(all_records, embed_model, threshold)
    print(f"  {total_input} records → {len(clusters)} clusters")
    print()

    # Synthesize each cluster
    print("Synthesizing clusters...")
    synthesized = []
    for i, cluster in enumerate(clusters):
        contents = [r["content"] for r in cluster]
        # Collect all tags across cluster members
        all_tags = set()
        for r in cluster:
            try:
                all_tags.update(json.loads(r.get("tags", "[]")))
            except Exception:
                pass

        print(f"  Cluster {i+1}/{len(clusters)} ({len(cluster)} records)...", end=" ", flush=True)
        synthesized_content = synthesize_cluster(contents, llm_model)
        print("done")

        new_embedding = get_embedding(synthesized_content, embed_model)
        synthesized.append({
            "id":         secrets.token_hex(8),
            "content":    synthesized_content,
            "embedding":  json.dumps(new_embedding),
            "tags":       json.dumps(list(all_tags)),
            "source_at":  datetime.now(timezone.utc).isoformat(),
        })

    print(f"\n  Output records: {len(synthesized)}")
    print(f"  Compression:    {total_input} → {len(synthesized)} ({100 - int(len(synthesized)/total_input*100)}% reduction)")
    print()

    # Write output dataset
    out_path.mkdir(parents=True, exist_ok=True)
    db_out = out_path / "knowledge.db"

    conn = sqlite3.connect(db_out)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id        TEXT PRIMARY KEY,
            content   TEXT NOT NULL,
            embedding TEXT NOT NULL,
            tags      TEXT NOT NULL DEFAULT '[]',
            source_at TEXT NOT NULL
        );
    """)
    for rec in synthesized:
        conn.execute(
            "INSERT INTO memories (id, content, embedding, tags, source_at) VALUES (?, ?, ?, ?, ?)",
            (rec["id"], rec["content"], rec["embedding"], rec["tags"], rec["source_at"])
        )
    conn.commit()
    conn.close()

    # Write metadata
    metadata = {
        "name":           out_path.name,
        "version":        out_path.name.split("-v")[-1] if "-v" in out_path.name else "1.0.0",
        "embedding_model": embed_model,
        "topic_tags":     list({tag for r in synthesized for tag in json.loads(r["tags"])}),
        "agent_type":     "distillation",
        "record_count":   len(synthesized),
        "language":       "en",
        "submitted_by":   "AgentCommons",
        "submitted_at":   date.today().isoformat(),
        "provenance":     source_refs,
        "description":    f"Official AgentCommons distillation release. Synthesized from {len(dataset_paths)} source dataset(s).",
    }
    (out_path / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Write provenance record
    provenance = {
        "release":            str(out_path),
        "produced_at":        date.today().isoformat(),
        "produced_by":        "AgentCommons",
        "methodology":        "cluster-then-synthesize",
        "embedding_model":    embed_model,
        "llm_model":          llm_model,
        "cluster_threshold":  threshold,
        "source_datasets":    source_refs,
        "input_record_count": total_input,
        "output_record_count": len(synthesized),
        "notes":              "",
    }
    (out_path / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")

    # Write README
    (out_path / "README.md").write_text(
        f"# {out_path.name}\n\n"
        f"**Type:** Official AgentCommons distillation release\n"
        f"**Records:** {len(synthesized)} (synthesized from {total_input} source records)\n"
        f"**Embedding model:** {embed_model}\n"
        f"**Produced:** {date.today().isoformat()}\n\n"
        f"## Source Datasets\n\n"
        + "\n".join(f"- {s}" for s in source_refs) +
        "\n\nSee `provenance.json` for full distillation details.\n"
    )

    print(f"Distillation complete.")
    print(f"  Output: {out_path}/")
    print(f"  Files:  knowledge.db, metadata.json, provenance.json, README.md")


def main():
    parser = argparse.ArgumentParser(description="Distill multiple AgentCommons datasets into a canonical release.")
    parser.add_argument("--datasets",          required=True, nargs="+", help="Dataset paths to distill")
    parser.add_argument("--out",               required=True,            help="Output path for distillation release")
    parser.add_argument("--embed-model",       default=DEFAULT_EMBED,    help=f"Embedding model (default: {DEFAULT_EMBED})")
    parser.add_argument("--llm-model",         default=DEFAULT_LLM,      help=f"LLM for synthesis (default: {DEFAULT_LLM})")
    parser.add_argument("--cluster-threshold", type=float, default=DEFAULT_THRESHOLD, help=f"Similarity threshold for clustering (default: {DEFAULT_THRESHOLD})")
    args = parser.parse_args()

    distill(args.datasets, Path(args.out), args.embed_model, args.llm_model, args.cluster_threshold)


if __name__ == "__main__":
    main()
