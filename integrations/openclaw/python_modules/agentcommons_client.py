"""
AgentCommons Integration Client

Provides query interface to Harris Innovation Lab's centralized memory network.
Handles SQLite backend, embedding similarity, caching, and fallback.
"""

import json
import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from collections import OrderedDict
import requests
from pathlib import Path

try:
    from nomic import embed
except ImportError:
    embed = None


class AgentCommonsUnavailableError(Exception):
    """Raised when AgentCommons backend is unreachable."""
    pass


class AgentCommonsClient:
    """Client for querying AgentCommons memory network."""

    def __init__(self, api_url: Optional[str] = None, cache_dir: Optional[str] = None, 
                 cache_disabled: bool = False, embedding_model: str = "nomic-embed-text"):
        """
        Initialize AgentCommons client.

        Args:
            api_url: Optional API endpoint (auto-detects if not provided)
            cache_dir: Cache directory (defaults to ~/.openclaw/workspace/.agentcommons-cache/)
            cache_disabled: Disable caching if True
            embedding_model: Embedding model name (default: nomic-embed-text)
        """
        self.api_url = api_url or self._auto_detect_api()
        self.embedding_model = embedding_model
        self.cache_disabled = cache_disabled
        self.cache_dir = Path(cache_dir or "~/.openclaw/workspace/.agentcommons-cache/").expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._memory_cache = OrderedDict()  # LRU cache
        self.max_cache_entries = 128
        self._cache_stats = {"hits": 0, "misses": 0}
        self._backend_type = "http" if self.api_url else "local"

    def _auto_detect_api(self) -> Optional[str]:
        """Auto-detect API endpoint: env var → localhost:8765 → None."""
        url = os.getenv("AGENTCOMMONS_API_URL")
        if url:
            return url

        # Try localhost default
        try:
            resp = requests.get("http://localhost:8765/health", timeout=1)
            if resp.status_code == 200:
                return "http://localhost:8765"
        except Exception:
            pass

        return None

    def _get_cache_key(self, query_type: str, query_value: str, filters: Dict) -> str:
        """Generate cache key from query parameters."""
        key_str = f"{query_type}:{query_value}:{json.dumps(filters, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Load results from cache (memory + disk)."""
        if self.cache_disabled:
            return None

        # Check memory cache
        if cache_key in self._memory_cache:
            self._cache_stats["hits"] += 1
            self._memory_cache.move_to_end(cache_key)  # LRU
            return self._memory_cache[cache_key]

        # Check disk cache
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    if datetime.fromisoformat(data["timestamp"]) > datetime.now() - timedelta(hours=24):
                        self._cache_stats["hits"] += 1
                        return data["results"]
            except Exception:
                pass

        self._cache_stats["misses"] += 1
        return None

    def _save_to_cache(self, cache_key: str, results: List[Dict]) -> None:
        """Save results to cache (memory + disk)."""
        if self.cache_disabled:
            return

        # Memory cache
        self._memory_cache[cache_key] = results
        self._memory_cache.move_to_end(cache_key)
        if len(self._memory_cache) > self.max_cache_entries:
            self._memory_cache.popitem(last=False)  # Remove oldest

        # Disk cache
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "results": results
                }, f)
        except Exception:
            pass

    def _call_api(self, endpoint: str, params: Dict) -> List[Dict]:
        """Call AgentCommons HTTP API."""
        if not self.api_url:
            raise AgentCommonsUnavailableError("No API endpoint configured")

        try:
            url = f"{self.api_url}/{endpoint}"
            resp = requests.get(url, params=params, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise AgentCommonsUnavailableError(f"API call failed: {e}")

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding for similarity search."""
        if not embed:
            return None
        try:
            result = embed.embed([text], model=self.embedding_model)
            return result[0] if result else None
        except Exception:
            return None

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        mag1 = sum(a ** 2 for a in v1) ** 0.5
        mag2 = sum(b ** 2 for b in v2) ** 0.5
        return dot_product / (mag1 * mag2) if mag1 * mag2 > 0 else 0.0

    def query_by_tag(self, tag: str, agent_types: Optional[List[str]] = None,
                     embedding_models: Optional[List[str]] = None,
                     date_range: Optional[Tuple[str, Optional[str]]] = None,
                     min_relevance: float = 0.0, limit: int = 10) -> List[Dict]:
        """
        Query memories by tag.

        Args:
            tag: Tag to search (e.g., "#federal-contracting")
            agent_types: Filter by agent type (e.g., ["Goku"])
            embedding_models: Filter by embedding model
            date_range: Tuple of (start_date, end_date) or (start_date, None)
            min_relevance: Minimum relevance score (0.0-1.0)
            limit: Max results to return

        Returns:
            List of memory dicts with relevance scores
        """
        filters = {
            "agent_types": agent_types or [],
            "embedding_models": embedding_models or [],
            "date_range": date_range or [],
            "min_relevance": min_relevance,
            "limit": limit
        }

        cache_key = self._get_cache_key("tag", tag, filters)
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            results = self._call_api("query/tag", {
                "tag": tag,
                "agent_types": ",".join(agent_types or []),
                "embedding_models": ",".join(embedding_models or []),
                "date_start": date_range[0] if date_range else None,
                "date_end": date_range[1] if date_range else None,
                "min_relevance": min_relevance,
                "limit": limit
            })
        except AgentCommonsUnavailableError:
            results = self.query_local_by_tag(tag, limit=limit)

        self._save_to_cache(cache_key, results)
        return results

    def query_by_similarity(self, topic: str, agent_types: Optional[List[str]] = None,
                           date_range: Optional[Tuple[str, Optional[str]]] = None,
                           min_relevance: float = 0.0, limit: int = 10) -> List[Dict]:
        """
        Query memories by semantic similarity.

        Args:
            topic: Topic/question to find similar memories
            agent_types: Filter by agent type
            date_range: Tuple of (start_date, end_date) or (start_date, None)
            min_relevance: Minimum relevance score
            limit: Max results

        Returns:
            List of memories ranked by similarity
        """
        filters = {
            "agent_types": agent_types or [],
            "date_range": date_range or [],
            "min_relevance": min_relevance,
            "limit": limit
        }

        cache_key = self._get_cache_key("similarity", topic, filters)
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            results = self._call_api("query/similarity", {
                "topic": topic,
                "agent_types": ",".join(agent_types or []),
                "date_start": date_range[0] if date_range else None,
                "date_end": date_range[1] if date_range else None,
                "min_relevance": min_relevance,
                "limit": limit
            })
        except AgentCommonsUnavailableError:
            results = self.query_local_by_similarity(topic, limit=limit)

        self._save_to_cache(cache_key, results)
        return results

    def query_batch(self, topics: List[str], limit: int = 5) -> Dict[str, List[Dict]]:
        """
        Efficiently query multiple topics in batch.

        Args:
            topics: List of topics/tags to query
            limit: Max results per topic

        Returns:
            Dict mapping topic → list of memories
        """
        results = {}
        for topic in topics[:20]:  # Max 20 topics per batch
            # Try similarity first, fall back to tag
            if topic.startswith("#"):
                results[topic] = self.query_by_tag(topic, limit=limit)
            else:
                results[topic] = self.query_by_similarity(topic, limit=limit)
        return results

    def query_local_by_tag(self, tag: str, limit: int = 10) -> List[Dict]:
        """Local fallback: query in-memory cache by tag."""
        matched = []
        for entry in self._memory_cache.values():
            for mem in entry if isinstance(entry, list) else [entry]:
                if isinstance(mem, dict) and tag in mem.get("tags", []):
                    matched.append(mem)
        return matched[:limit]

    def query_local_by_similarity(self, topic: str, limit: int = 10) -> List[Dict]:
        """Local fallback: simple text matching on cached memories."""
        topic_lower = topic.lower()
        matched = []
        for entry in self._memory_cache.values():
            for mem in entry if isinstance(entry, list) else [entry]:
                if isinstance(mem, dict):
                    content = mem.get("content", "").lower()
                    if any(word in content for word in topic_lower.split()):
                        matched.append(mem)
        return matched[:limit]

    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": self._cache_stats["hits"] / max(1, self._cache_stats["hits"] + self._cache_stats["misses"]),
            "memory_entries": len(self._memory_cache),
            "disk_cache_size": sum(f.stat().st_size for f in self.cache_dir.glob("*.json") if f.is_file())
        }

    def clear_cache(self, older_than: Optional[int] = None) -> None:
        """
        Clear cache.

        Args:
            older_than: Clear entries older than N seconds (None = clear all)
        """
        self._memory_cache.clear()

        if older_than is None:
            # Clear all disk cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass
        else:
            # Clear old disk cache entries
            cutoff = datetime.now() - timedelta(seconds=older_than)
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file) as f:
                        data = json.load(f)
                        if datetime.fromisoformat(data["timestamp"]) < cutoff:
                            cache_file.unlink()
                except Exception:
                    pass

    def info(self) -> Dict[str, Any]:
        """Get client info and backend status."""
        return {
            "api_url": self.api_url,
            "backend_type": self._backend_type,
            "embedding_model": self.embedding_model,
            "cache_disabled": self.cache_disabled,
            "cache_dir": str(self.cache_dir),
            "cache_stats": self.cache_stats()
        }


if __name__ == "__main__":
    # Quick test
    client = AgentCommonsClient()
    print(f"Client info: {client.info()}")
    print(f"Backend: {client._backend_type}")
