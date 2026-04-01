"""
Advanced Cache Management Examples

Demonstrates cache control, metrics, and optimization patterns.
"""

from agentcommons_client import AgentCommonsClient
import json
from pathlib import Path


def cache_statistics_dashboard(client: AgentCommonsClient):
    """
    Display cache performance dashboard.
    """
    stats = client.cache_stats()
    info = client.info()

    print("\n" + "="*60)
    print("AgentCommons Cache Dashboard")
    print("="*60)

    print(f"\nBackend Status:")
    print(f"  Backend Type: {info['backend_type']}")
    print(f"  API URL: {info['api_url']}")
    print(f"  Embedding Model: {info['embedding_model']}")

    print(f"\nCache Performance:")
    print(f"  Hit Rate: {stats['hit_rate']:.1%}")
    print(f"  Total Hits: {stats['hits']}")
    print(f"  Total Misses: {stats['misses']}")
    print(f"  In-Memory Entries: {stats['memory_entries']}")
    print(f"  Disk Cache Size: {stats['disk_cache_size']:,} bytes")

    print(f"\nCache Location: {info['cache_dir']}")
    print("="*60 + "\n")

    return stats


def list_cached_entries(client: AgentCommonsClient):
    """
    List all cached entries with timestamps and sizes.
    """
    cache_dir = Path(client.cache_dir)
    entries = []

    for cache_file in sorted(cache_dir.glob("*.json")):
        try:
            with open(cache_file) as f:
                data = json.load(f)
                size = cache_file.stat().st_size
                timestamp = data.get("timestamp", "unknown")
                result_count = len(data.get("results", []))
                entries.append({
                    "file": cache_file.name,
                    "timestamp": timestamp,
                    "results": result_count,
                    "size_bytes": size
                })
        except Exception as e:
            print(f"  Error reading {cache_file}: {e}")

    if not entries:
        print("No cached entries found.")
        return

    print(f"\nCached Entries ({len(entries)} total):\n")
    print(f"{'File':<40} {'Results':<10} {'Size':<10} {'Timestamp'}")
    print("-" * 75)
    for entry in entries:
        print(f"{entry['file']:<40} {entry['results']:<10} {entry['size_bytes']:<10} {entry['timestamp']}")

    total_size = sum(e['size_bytes'] for e in entries)
    total_results = sum(e['results'] for e in entries)
    print("-" * 75)
    print(f"{'TOTAL':<40} {total_results:<10} {total_size:<10}")


def clear_old_cache(client: AgentCommonsClient, hours_old: int = 24):
    """
    Clear cache entries older than specified hours.

    Args:
        client: AgentCommonsClient instance
        hours_old: Clear entries older than this many hours
    """
    seconds_old = hours_old * 3600
    print(f"Clearing cache entries older than {hours_old} hours...")

    before_stats = client.cache_stats()
    client.clear_cache(older_than=seconds_old)
    after_stats = client.cache_stats()

    print(f"Before: {before_stats['disk_cache_size']} bytes")
    print(f"After:  {after_stats['disk_cache_size']} bytes")
    print(f"Freed:  {before_stats['disk_cache_size'] - after_stats['disk_cache_size']} bytes")


def clear_all_cache(client: AgentCommonsClient):
    """
    Clear all cache (memory + disk).
    """
    print("Clearing all cache...")
    before_size = client.cache_stats()['disk_cache_size']
    client.clear_cache(older_than=None)
    print(f"Cleared {before_size} bytes of cache.")


def warm_cache(client: AgentCommonsClient, common_queries: list):
    """
    Pre-populate cache with common queries for faster subsequent access.

    Args:
        client: AgentCommonsClient instance
        common_queries: List of dicts with 'type' and 'value' keys

    Example:
        queries = [
            {"type": "tag", "value": "#federal-contracting"},
            {"type": "similarity", "value": "SBIR Phase 1 strategy"},
        ]
        warm_cache(client, queries)
    """
    print(f"Warming cache with {len(common_queries)} queries...\n")

    for query in common_queries:
        qtype = query.get("type")
        value = query.get("value")

        try:
            if qtype == "tag":
                results = client.query_by_tag(value, limit=10)
                print(f"  ✓ Tag '{value}': {len(results)} results cached")
            elif qtype == "similarity":
                results = client.query_by_similarity(value, limit=10)
                print(f"  ✓ Similarity '{value}': {len(results)} results cached")
            else:
                print(f"  ✗ Unknown query type: {qtype}")
        except Exception as e:
            print(f"  ✗ Query failed: {e}")

    stats = client.cache_stats()
    print(f"\nCache warmed: {stats['memory_entries']} memory entries, "
          f"{stats['disk_cache_size']} bytes on disk")


def cache_comparison(client1: AgentCommonsClient, client2: AgentCommonsClient, query: str):
    """
    Compare cache hit rates between two client instances.
    """
    print(f"\nCache Comparison Test: '{query}'")
    print("-" * 50)

    # Client 1 (cold)
    results1 = client1.query_by_similarity(query, limit=5)
    stats1_before = client1.cache_stats()

    results1_again = client1.query_by_similarity(query, limit=5)
    stats1_after = client1.cache_stats()

    # Client 2 (separate cache)
    results2 = client2.query_by_similarity(query, limit=5)
    stats2 = client2.cache_stats()

    print(f"\nClient 1:")
    print(f"  1st query: {stats1_before['hits']} hits, {stats1_before['misses']} misses")
    print(f"  2nd query: {stats1_after['hits']} hits (cache HIT) vs {stats1_after['misses']} misses")

    print(f"\nClient 2:")
    print(f"  1st query: {stats2['hits']} hits, {stats2['misses']} misses (separate cache)")

    print(f"\nCache Isolation: {'✓ Confirmed' if stats2['misses'] > 0 else '✗ Caches may be shared'}")


if __name__ == "__main__":
    # Initialize client
    client = AgentCommonsClient()

    # Dashboard
    cache_statistics_dashboard(client)

    # List entries
    list_cached_entries(client)

    # Warm cache with common queries
    common_queries = [
        {"type": "tag", "value": "#federal-contracting"},
        {"type": "tag", "value": "#sales-pipeline"},
        {"type": "similarity", "value": "SBIR proposal strategy"},
        {"type": "similarity", "value": "Prospect qualification"},
    ]
    warm_cache(client, common_queries)

    # Show cache after warming
    print("\nCache after warming:")
    cache_statistics_dashboard(client)

    # List entries again
    list_cached_entries(client)
