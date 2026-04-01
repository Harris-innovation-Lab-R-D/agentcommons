"""
PreTaskQueryer - Query AgentCommons before starting a task

Finds related past work, detects conflicting approaches, and alerts user
before the agent begins work. Enables proactive learning and conflict avoidance.
"""

import json
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
from agentcommons_client import AgentCommonsClient, AgentCommonsUnavailableError


class PreTaskQueryer:
    """Query AgentCommons before task execution to find context and conflicts."""

    def __init__(self, client: Optional[AgentCommonsClient] = None):
        """
        Initialize PreTaskQueryer.

        Args:
            client: Optional AgentCommonsClient (creates default if not provided)
        """
        self.client = client or AgentCommonsClient()

    def query_similar_work(
        self,
        domain: str,
        topic: str,
        agent_type: Optional[str] = None,
        days_back: int = 90,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find related past work by domain and topic.

        Args:
            domain: Domain name (e.g., "federal-contracting", "sales-pipeline")
            topic: Task topic (e.g., "SBIR Phase 1 proposal")
            agent_type: Filter by agent type (e.g., "Goku")
            days_back: Look back N days (default 90)
            limit: Max results to return

        Returns:
            List of similar past work entries with metadata
        """
        tag = f"#{domain}"
        date_range = (
            (datetime.now() - __import__('datetime').timedelta(days=days_back)).isoformat().split('T')[0],
            None
        )

        try:
            results = self.client.query_by_similarity(
                topic=topic,
                agent_types=[agent_type] if agent_type else None,
                date_range=date_range,
                limit=limit
            )

            # Also try tag-based search
            tag_results = self.client.query_by_tag(
                tag=tag,
                agent_types=[agent_type] if agent_type else None,
                date_range=date_range,
                limit=limit
            )

            # Merge, deduplicate by ID
            seen_ids = {r.get("id") for r in results}
            for tag_result in tag_results:
                if tag_result.get("id") not in seen_ids:
                    results.append(tag_result)

            return results[:limit]

        except AgentCommonsUnavailableError:
            return []

    def detect_conflicting_approaches(
        self,
        problem: str,
        proposed_approach: str,
        agent_type: Optional[str] = None,
        similarity_threshold: float = 0.75,
        approach_divergence_threshold: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Find divergent solutions to the same problem.

        Detects when:
        - Past work addresses the same problem (high semantic similarity)
        - But used a different approach (low semantic similarity between solutions)

        Args:
            problem: Problem statement (e.g., "Proposal timeline too long")
            proposed_approach: Our approach to solving it
            agent_type: Filter by agent type
            similarity_threshold: Min similarity for "same problem" (0-1)
            approach_divergence_threshold: Max similarity for "different approach" (0-1)

        Returns:
            List of conflicting past approaches with flagging
        """
        # Find similar problems
        try:
            similar_problems = self.client.query_by_similarity(
                topic=problem,
                agent_types=[agent_type] if agent_type else None,
                min_relevance=similarity_threshold,
                limit=20
            )
        except AgentCommonsUnavailableError:
            return []

        conflicts = []

        for past_entry in similar_problems:
            past_approach = past_entry.get("metadata", {}).get("approach", "")
            if not past_approach:
                continue

            # Compute approach similarity
            approach_sim = self._compute_text_similarity(proposed_approach, past_approach)

            # Flag as conflict if problem is similar but approach differs
            if approach_sim < approach_divergence_threshold:
                conflicts.append({
                    "past_work_id": past_entry.get("id"),
                    "past_content": past_entry.get("content"),
                    "past_approach": past_approach,
                    "past_outcome": past_entry.get("metadata", {}).get("outcome"),
                    "problem_similarity": past_entry.get("relevance_score", 0.0),
                    "approach_divergence": 1.0 - approach_sim,
                    "source_agent": past_entry.get("source_agent"),
                    "created_at": past_entry.get("created_at"),
                    "conflict_type": self._classify_conflict(proposed_approach, past_approach)
                })

        return sorted(conflicts, key=lambda x: x["approach_divergence"], reverse=True)

    def _compute_text_similarity(self, text1: str, text2: str) -> float:
        """
        Simple text similarity (word overlap). For production, use embeddings.

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

    def _classify_conflict(self, approach1: str, approach2: str) -> str:
        """Classify type of conflict (speed vs. quality, cost vs. scope, etc.)"""
        conflict_patterns = {
            "speed_vs_quality": [
                ("fast", "slow"), ("quick", "thorough"), ("rapid", "detailed"),
                ("compress", "comprehensive")
            ],
            "cost_vs_scope": [
                ("minimal", "extensive"), ("lean", "full"), ("cheap", "complete")
            ],
            "innovation_vs_proven": [
                ("novel", "proven"), ("experimental", "established"),
                ("creative", "standard"), ("new", "traditional")
            ],
            "automation_vs_manual": [
                ("automate", "manual"), ("script", "process"), ("bot", "human")
            ]
        }

        approach_lower = (approach1 + " " + approach2).lower()

        for conflict_type, patterns in conflict_patterns.items():
            for term1, term2 in patterns:
                if (term1 in approach_lower and term2 in approach_lower):
                    return conflict_type

        return "other"

    def escalate_conflicts_to_user(
        self,
        conflicts: List[Dict[str, Any]],
        task_id: str,
        user_id: str = "Carlton"
    ) -> Dict[str, Any]:
        """
        Create decision record for user review of conflicting approaches.

        Args:
            conflicts: List of detected conflicts
            task_id: Current task ID
            user_id: User to escalate to (default: Carlton)

        Returns:
            Decision record ready for user input
        """
        if not conflicts:
            return {"status": "no_conflicts"}

        decision_record = {
            "decision_id": f"conflict-{task_id}-{datetime.now().isoformat()}",
            "status": "pending",
            "user_id": user_id,
            "task_id": task_id,
            "created_at": datetime.now().isoformat(),
            "conflicts": conflicts,
            "prompt_for_user": self._generate_user_prompt(conflicts),
            "options": [
                {
                    "id": "proceed_proposed",
                    "label": "Proceed with proposed approach",
                    "description": "Use the approach we selected despite conflicts"
                },
                {
                    "id": "adopt_past",
                    "label": "Adopt past approach",
                    "description": "Use the approach from past work instead",
                    "note": "Choose which past work to adopt"
                },
                {
                    "id": "hybrid",
                    "label": "Hybrid approach",
                    "description": "Combine elements from proposed and past approaches",
                    "note": "Specify which elements to combine"
                },
                {
                    "id": "research",
                    "label": "Research more",
                    "description": "Look for more context before deciding"
                }
            ]
        }

        return decision_record

    def _generate_user_prompt(self, conflicts: List[Dict[str, Any]]) -> str:
        """Generate readable prompt for user review of conflicts."""
        prompt = f"⚠️ **Conflicting Approaches Detected** ({len(conflicts)} conflict(s))\n\n"

        for i, conflict in enumerate(conflicts, 1):
            prompt += f"**Conflict {i}: {conflict['conflict_type'].replace('_', ' ').title()}**\n"
            prompt += f"- **Problem match:** {conflict['problem_similarity']:.0%}\n"
            prompt += f"- **Approach differs by:** {conflict['approach_divergence']:.0%}\n"
            prompt += f"- **Past work:** {conflict['source_agent']} ({conflict['created_at'][:10]})\n"
            prompt += f"- **Past approach:** {conflict['past_approach'][:100]}...\n"
            prompt += f"- **Outcome:** {conflict['past_outcome']}\n\n"

        prompt += "**Your options:**\n"
        prompt += "1. Proceed with our approach anyway\n"
        prompt += "2. Adopt the past approach instead\n"
        prompt += "3. Create a hybrid approach\n"
        prompt += "4. Research more before deciding\n"

        return prompt


if __name__ == "__main__":
    # Quick test
    querier = PreTaskQueryer()

    # Example: Before federal contracting task
    similar = querier.query_similar_work(
        domain="federal-contracting",
        topic="SBIR Phase 1 proposal strategy",
        agent_type="Goku",
        limit=3
    )
    print(f"Found {len(similar)} similar past work entries")

    # Example: Detect conflicts
    conflicts = querier.detect_conflicting_approaches(
        problem="How to compress proposal timeline",
        proposed_approach="Parallel workstream execution with daily syncs",
        agent_type="Goku"
    )
    print(f"Detected {len(conflicts)} conflicting approaches")

    if conflicts:
        decision = querier.escalate_conflicts_to_user(
            conflicts=conflicts,
            task_id="task-2026-0331-001"
        )
        print(f"\nDecision record:\n{json.dumps(decision, indent=2)}")
