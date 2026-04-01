"""
ConflictManager - Detect, manage, and resolve approach conflicts

Compares similar solutions semantically and flags divergent approaches
for Carlton's decision-making. Records decisions back to AgentCommons
to mark canonical vs. deprecated approaches.
"""

import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class ConflictStatus(Enum):
    """Status of a conflict resolution."""
    PENDING = "pending"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class ConflictManager:
    """Detect and manage conflicting approaches."""

    def __init__(self):
        """Initialize ConflictManager."""
        self.conflicts_registry = {}  # conflict_id → conflict record

    def compare_approaches(
        self,
        approach1: str,
        approach2: str,
        problem_context: str,
        metadata1: Optional[Dict[str, Any]] = None,
        metadata2: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compare two approaches semantically and structurally.

        Args:
            approach1: First approach description
            approach2: Second approach description
            problem_context: The problem both approaches address
            metadata1: Optional metadata for approach1
            metadata2: Optional metadata for approach2

        Returns:
            Comparison result with similarity scores and dimensions
        """
        comparison = {
            "approach1": approach1,
            "approach2": approach2,
            "problem_context": problem_context,
            "created_at": datetime.now().isoformat(),
            "similarities": self._extract_similarities(approach1, approach2),
            "differences": self._extract_differences(approach1, approach2),
            "trade_offs": self._identify_tradeoffs(approach1, approach2),
            "semantic_similarity": self._compute_semantic_similarity(approach1, approach2),
            "structure_similarity": self._compute_structure_similarity(approach1, approach2),
            "metadata1": metadata1 or {},
            "metadata2": metadata2 or {}
        }

        # Overall similarity score
        comparison["overall_similarity"] = (
            comparison["semantic_similarity"] * 0.6 +
            comparison["structure_similarity"] * 0.4
        )

        return comparison

    def _extract_similarities(self, approach1: str, approach2: str) -> List[str]:
        """Extract common elements between approaches."""
        words1 = set(approach1.lower().split())
        words2 = set(approach2.lower().split())

        # Common words (excluding very common ones)
        common_words = words1 & words2
        stopwords = {"the", "a", "an", "and", "or", "but", "is", "are", "was", "were"}
        common = [w for w in common_words if w not in stopwords and len(w) > 3]

        return sorted(common)

    def _extract_differences(self, approach1: str, approach2: str) -> Dict[str, List[str]]:
        """Extract unique elements in each approach."""
        words1 = set(approach1.lower().split())
        words2 = set(approach2.lower().split())

        stopwords = {"the", "a", "an", "and", "or", "but", "is", "are", "was", "were"}

        only_in_1 = [w for w in words1 - words2 if len(w) > 3 and w not in stopwords]
        only_in_2 = [w for w in words2 - words1 if len(w) > 3 and w not in stopwords]

        return {
            "only_in_approach1": sorted(only_in_1),
            "only_in_approach2": sorted(only_in_2)
        }

    def _identify_tradeoffs(self, approach1: str, approach2: str) -> List[Dict[str, str]]:
        """Identify explicit trade-offs (speed vs. quality, cost vs. scope, etc.)"""
        tradeoff_patterns = {
            "speed_vs_quality": (
                ["fast", "quick", "rapid", "compress", "parallel"],
                ["slow", "thorough", "detailed", "comprehensive", "sequential"]
            ),
            "cost_vs_scope": (
                ["minimal", "lean", "cheap", "budget", "cost-effective"],
                ["extensive", "full", "complete", "comprehensive", "expensive"]
            ),
            "innovation_vs_proven": (
                ["novel", "experimental", "creative", "new", "cutting-edge"],
                ["proven", "established", "traditional", "standard", "conventional"]
            ),
            "automation_vs_manual": (
                ["automate", "script", "bot", "tool", "system"],
                ["manual", "process", "human", "review", "checklist"]
            ),
            "scalability_vs_simplicity": (
                ["scalable", "distributed", "modular", "enterprise"],
                ["simple", "monolithic", "contained", "direct"]
            )
        }

        tradeoffs = []
        combined = (approach1 + " " + approach2).lower()

        for tradeoff_type, (markers_a, markers_b) in tradeoff_patterns.items():
            has_a = any(m in combined for m in markers_a)
            has_b = any(m in combined for m in markers_b)

            if has_a and has_b:
                tradeoffs.append({
                    "type": tradeoff_type,
                    "approach1_leans": "A" if any(m in approach1.lower() for m in markers_a) else "B",
                    "approach2_leans": "A" if any(m in approach2.lower() for m in markers_a) else "B"
                })

        return tradeoffs

    def _compute_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Compute semantic similarity via word overlap.
        Production version would use embeddings.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0-1
        """
        if not text1 or not text2:
            return 0.0

        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _compute_structure_similarity(self, text1: str, text2: str) -> float:
        """
        Compute structural similarity (sentence count, word count patterns).

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0-1
        """
        sentences1 = len([s for s in text1.split(".") if s.strip()])
        sentences2 = len([s for s in text2.split(".") if s.strip()])

        words1 = len(text1.split())
        words2 = len(text2.split())

        # Compare structure (should both be 1-3 sentences, similar length)
        sent_ratio = min(sentences1, sentences2) / max(sentences1, sentences2) if max(sentences1, sentences2) > 0 else 0.0
        word_ratio = min(words1, words2) / max(words1, words2) if max(words1, words2) > 0 else 0.0

        return (sent_ratio * 0.4 + word_ratio * 0.6)

    def create_decision_record(
        self,
        comparison: Dict[str, Any],
        source_task_id: str,
        requester: str = "Carlton"
    ) -> Dict[str, Any]:
        """
        Create a decision record for user review of approach conflict.

        Args:
            comparison: Result from compare_approaches()
            source_task_id: ID of task where conflict was detected
            requester: User to handle decision (default: Carlton)

        Returns:
            Decision record ready for user interaction
        """
        conflict_id = f"conflict-{source_task_id}-{datetime.now().timestamp()}"

        decision_record = {
            "conflict_id": conflict_id,
            "status": ConflictStatus.PENDING.value,
            "requester": requester,
            "source_task_id": source_task_id,
            "created_at": datetime.now().isoformat(),
            "comparison": comparison,
            "user_prompt": self._generate_decision_prompt(comparison),
            "options": [
                {
                    "id": "canonical_approach1",
                    "label": "Approach 1 is canonical",
                    "description": "Mark approach1 as the canonical (preferred) solution",
                    "rationale_prompt": "Why is approach 1 better?"
                },
                {
                    "id": "canonical_approach2",
                    "label": "Approach 2 is canonical",
                    "description": "Mark approach2 as the canonical (preferred) solution",
                    "rationale_prompt": "Why is approach 2 better?"
                },
                {
                    "id": "context_dependent",
                    "label": "Context-dependent",
                    "description": "Both are valid depending on context",
                    "context_prompt": "When should each be used?"
                },
                {
                    "id": "hybrid",
                    "label": "Recommend hybrid",
                    "description": "Combine elements from both approaches",
                    "hybrid_prompt": "How should they be combined?"
                },
                {
                    "id": "research",
                    "label": "Needs more research",
                    "description": "Insufficient data to decide yet",
                    "research_prompt": "What information is needed?"
                }
            ],
            "decision": None,
            "decided_by": None,
            "decided_at": None,
            "rationale": None
        }

        self.conflicts_registry[conflict_id] = decision_record

        return decision_record

    def _generate_decision_prompt(self, comparison: Dict[str, Any]) -> str:
        """Generate readable prompt for user decision."""
        prompt = "## Conflicting Approaches Detected\n\n"

        prompt += f"**Problem:** {comparison['problem_context']}\n\n"

        prompt += "### Approach 1\n"
        prompt += f"{comparison['approach1']}\n\n"

        prompt += "### Approach 2\n"
        prompt += f"{comparison['approach2']}\n\n"

        prompt += "### Analysis\n"
        prompt += f"- **Overall similarity:** {comparison['overall_similarity']:.0%}\n"
        prompt += f"- **Semantic similarity:** {comparison['semantic_similarity']:.0%}\n"
        prompt += f"- **Structural similarity:** {comparison['structure_similarity']:.0%}\n"

        if comparison.get("similarities"):
            prompt += f"- **Common elements:** {', '.join(comparison['similarities'][:5])}\n"

        if comparison.get("trade_offs"):
            prompt += "- **Trade-offs:**\n"
            for tradeoff in comparison.get("trade_offs", []):
                prompt += f"  - {tradeoff['type'].replace('_', ' ').title()}\n"

        prompt += "\n**What's your recommendation?**\n"

        return prompt

    def apply_user_decision(
        self,
        conflict_id: str,
        decision: str,
        rationale: str,
        decided_by: str = "Carlton"
    ) -> Dict[str, Any]:
        """
        Record user's decision and mark approaches as canonical/deprecated.

        Args:
            conflict_id: ID of conflict being resolved
            decision: User's choice (from options list)
            rationale: Explanation for the decision
            decided_by: User making decision (default: Carlton)

        Returns:
            Updated decision record
        """
        if conflict_id not in self.conflicts_registry:
            return {"error": f"Conflict {conflict_id} not found"}

        record = self.conflicts_registry[conflict_id]

        record["decision"] = decision
        record["decided_by"] = decided_by
        record["decided_at"] = datetime.now().isoformat()
        record["rationale"] = rationale
        record["status"] = ConflictStatus.RESOLVED.value

        # Prepare canonical/deprecated marking
        canonical_marking = {
            "conflict_id": conflict_id,
            "decided_at": record["decided_at"],
            "decision_type": decision,
            "rationale": rationale
        }

        if decision == "canonical_approach1":
            canonical_marking["canonical_approach"] = 1
            canonical_marking["deprecated_approach"] = 2

        elif decision == "canonical_approach2":
            canonical_marking["canonical_approach"] = 2
            canonical_marking["deprecated_approach"] = 1

        elif decision == "context_dependent":
            canonical_marking["context_guidance"] = rationale

        elif decision == "hybrid":
            canonical_marking["hybrid_guidance"] = rationale

        record["canonical_marking"] = canonical_marking

        return record

    def get_conflict(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a conflict by ID."""
        return self.conflicts_registry.get(conflict_id)

    def list_conflicts(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List conflicts, optionally filtered by status."""
        conflicts = list(self.conflicts_registry.values())
        if status:
            conflicts = [c for c in conflicts if c["status"] == status]
        return conflicts


if __name__ == "__main__":
    # Quick test
    manager = ConflictManager()

    # Example: Compare two approaches
    comparison = manager.compare_approaches(
        approach1="Parallel workstream execution with daily syncs to compress timeline",
        approach2="Sequential, thorough workstream execution with weekly reviews for quality",
        problem_context="How to deliver SBIR Phase 1 proposal on time while maintaining quality"
    )

    print(f"Comparison result:")
    print(f"  Overall similarity: {comparison['overall_similarity']:.0%}")
    print(f"  Trade-offs: {len(comparison['tradeoffs'])} identified")
    print(f"  Similarities: {comparison['similarities']}")
    print(f"  Differences: {comparison['differences']}\n")

    # Create decision record
    decision_record = manager.create_decision_record(
        comparison=comparison,
        source_task_id="task-2026-0331-001"
    )

    print(f"Decision record created: {decision_record['conflict_id']}")
    print(f"Status: {decision_record['status']}")
    print(f"Options: {len(decision_record['options'])}\n")

    # Simulate user decision
    updated = manager.apply_user_decision(
        conflict_id=decision_record["conflict_id"],
        decision="canonical_approach1",
        rationale="Parallel execution better for time-sensitive proposals; daily syncs ensure quality",
        decided_by="Carlton"
    )

    print(f"Decision applied:")
    print(f"  Decision: {updated['decision']}")
    print(f"  Canonical: Approach {updated['canonical_marking']['canonical_approach']}")
    print(f"  Marked at: {updated['decided_at']}")
