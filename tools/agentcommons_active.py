"""
AgentCommons Active Learning - Main integration entry point

Provides unified interface for agents to query past work, detect conflicts,
and export learnings. Handles initialization, caching, and fallbacks.
"""

import json
from typing import List, Dict, Optional, Any, Union
from datetime import datetime

from agentcommons_client import AgentCommonsClient, AgentCommonsUnavailableError
from agentcommons_pretask import PreTaskQueryer
from agentcommons_posttask import PostTaskExporter
from agentcommons_conflict import ConflictManager


class AgentCommonsActiveLearning:
    """
    Main entry point for active learning integration.

    Usage:
        active = AgentCommonsActiveLearning(agent_name="Goku")

        # Pre-task: Find related work and check conflicts
        context = active.query_and_check_conflicts(
            domain="federal-contracting",
            topic="SBIR Phase 1 proposal"
        )

        # ... agent does work ...

        # Post-task: Export learnings and detect conflicts
        export = active.export_and_detect_conflicts(
            agent_output=agent_result,
            domain="federal-contracting",
            task_id="task-001",
            outcome="success"
        )
    """

    def __init__(
        self,
        agent_name: str,
        agent_type: str,
        client: Optional[AgentCommonsClient] = None
    ):
        """
        Initialize active learning system.

        Args:
            agent_name: Name of agent (e.g., "Goku")
            agent_type: Type of agent (e.g., "federal-contracting")
            client: Optional AgentCommonsClient (creates default if not provided)
        """
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.client = client or AgentCommonsClient()

        # Initialize sub-systems
        self.pre_querier = PreTaskQueryer(client=self.client)
        self.post_exporter = PostTaskExporter(client=self.client)
        self.conflict_manager = ConflictManager()

        self._session_conflicts = {}  # Track conflicts in current session

    def query_and_check_conflicts(
        self,
        domain: str,
        topic: str,
        task_id: str,
        check_conflicts: bool = True,
        escalate_threshold: float = 0.75,
        days_back: int = 90,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Pre-task workflow: find related work and check for conflicts.

        This is the main entry point for agents before starting work.

        Args:
            domain: Domain name (e.g., "federal-contracting")
            topic: Task topic (e.g., "SBIR Phase 1 proposal")
            task_id: Current task ID
            check_conflicts: Whether to detect conflicting approaches
            escalate_threshold: Min similarity for escalating conflicts
            days_back: Look back N days
            limit: Max past work items to find

        Returns:
            Context dict with related work, conflicts, and recommendations
        """
        context = {
            "task_id": task_id,
            "domain": domain,
            "topic": topic,
            "created_at": datetime.now().isoformat(),
            "similar_work": [],
            "conflicts": [],
            "recommendations": [],
            "status": "ready"
        }

        # Query similar work
        try:
            similar_work = self.pre_querier.query_similar_work(
                domain=domain,
                topic=topic,
                agent_type=self.agent_name,
                days_back=days_back,
                limit=limit
            )

            context["similar_work"] = similar_work
            context["similar_work_count"] = len(similar_work)

            # Generate recommendations from similar work
            if similar_work:
                best_match = similar_work[0]
                context["recommendations"].append({
                    "type": "related_work",
                    "source": best_match.get("source_agent"),
                    "message": f"Found similar work: {best_match.get('content', '')[:100]}...",
                    "confidence": best_match.get("relevance_score", 0.0)
                })

        except AgentCommonsUnavailableError:
            context["status"] = "agentcommons_unavailable"

        # Check for conflicts if requested
        if check_conflicts and similar_work:
            conflicts = self.pre_querier.detect_conflicting_approaches(
                problem=topic,
                proposed_approach="(to be determined by agent)",
                agent_type=self.agent_name,
                similarity_threshold=escalate_threshold
            )

            context["conflicts"] = conflicts
            context["conflicts_count"] = len(conflicts)

            if conflicts:
                context["status"] = "conflicts_detected"
                context["recommendations"].append({
                    "type": "conflict",
                    "message": f"⚠️ {len(conflicts)} conflicting approach(es) found",
                    "action_required": True
                })

                # Store for potential escalation
                decision = self.pre_querier.escalate_conflicts_to_user(
                    conflicts=conflicts,
                    task_id=task_id,
                    user_id="Carlton"
                )
                self._session_conflicts[task_id] = decision

        return context

    def export_and_detect_conflicts(
        self,
        agent_output: Union[str, Dict[str, Any]],
        domain: str,
        task_id: str,
        task_title: Optional[str] = None,
        outcome: Optional[str] = None,
        approach: Optional[str] = None,
        learnings: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        check_conflicts: bool = True
    ) -> Dict[str, Any]:
        """
        Post-task workflow: export learnings and detect conflicts.

        This is the main entry point for agents after completing work.

        Args:
            agent_output: Raw agent output (text or dict)
            domain: Domain name
            task_id: Task ID
            task_title: Optional task title
            outcome: Task outcome (success/partial/failed)
            approach: Agent's approach (used for conflict detection)
            learnings: Optional pre-extracted learnings
            metadata: Optional additional metadata
            check_conflicts: Whether to detect conflicts with past work

        Returns:
            Export result with conflict detection
        """
        export = {
            "task_id": task_id,
            "domain": domain,
            "export_at": datetime.now().isoformat(),
            "status": "exported",
            "conflicts": [],
            "decisions_required": []
        }

        # Export learnings to AgentCommons
        try:
            export_result = self.post_exporter.export_and_detect_conflicts(
                agent_output=agent_output,
                source_agent=self.agent_name,
                agent_type=self.agent_type,
                domain=domain,
                task_id=task_id,
                task_title=task_title,
                outcome=outcome,
                approach=approach,
                metadata=metadata or {}
            )

            export.update(export_result)

        except Exception as e:
            export["status"] = "export_failed"
            export["error"] = str(e)
            return export

        # Check for conflicts if requested
        if check_conflicts and approach:
            conflicts = self._detect_post_task_conflicts(
                domain=domain,
                approach=approach,
                outcome=outcome
            )

            if conflicts:
                export["conflicts"] = conflicts
                export["conflicts_count"] = len(conflicts)

                for conflict in conflicts:
                    decision = self.conflict_manager.create_decision_record(
                        comparison=conflict["comparison"],
                        source_task_id=task_id
                    )
                    export["decisions_required"].append(decision)
                    self._session_conflicts[f"{task_id}-post"] = decision

        return export

    def _detect_post_task_conflicts(
        self,
        domain: str,
        approach: str,
        outcome: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Internal: detect conflicts in post-task phase.

        Compares current task's approach against successful past approaches
        from the same domain.
        """
        # Query for successful past work in same domain
        try:
            similar_work = self.pre_querier.query_similar_work(
                domain=domain,
                topic=approach,
                agent_type=self.agent_name,
                limit=3
            )
        except AgentCommonsUnavailableError:
            return []

        conflicts = []

        for past_work in similar_work:
            past_approach = past_work.get("metadata", {}).get("approach")
            if not past_approach:
                continue

            # Skip if it's the same approach
            if approach.lower().strip() == past_approach.lower().strip():
                continue

            # Compare approaches
            comparison = self.conflict_manager.compare_approaches(
                approach1=approach,
                approach2=past_approach,
                problem_context=domain,
                metadata1={"task_id": "current", "outcome": outcome},
                metadata2={
                    "task_id": past_work.get("id"),
                    "outcome": past_work.get("metadata", {}).get("outcome"),
                    "source_agent": past_work.get("source_agent")
                }
            )

            # Flag if approaches differ significantly but overall similarity is high
            # (i.e., solving same problem differently)
            if (comparison["overall_similarity"] > 0.6 and
                comparison["semantic_similarity"] < 0.7):

                conflicts.append({
                    "comparison": comparison,
                    "past_work_id": past_work.get("id"),
                    "past_source": past_work.get("source_agent"),
                    "detected_at": datetime.now().isoformat()
                })

        return conflicts

    def get_session_conflicts(self) -> Dict[str, Any]:
        """Get all conflicts detected in current session."""
        return self._session_conflicts

    def info(self) -> Dict[str, Any]:
        """Get system info."""
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "client_info": self.client.info(),
            "session_conflicts": len(self._session_conflicts),
            "conflict_manager_conflicts": len(self.conflict_manager.conflicts_registry)
        }


if __name__ == "__main__":
    # Quick integration test
    active = AgentCommonsActiveLearning(
        agent_name="Goku",
        agent_type="federal-contracting"
    )

    print("=== Pre-Task: Query and Check Conflicts ===")
    pre_context = active.query_and_check_conflicts(
        domain="federal-contracting",
        topic="SBIR Phase 1 proposal strategy",
        task_id="task-sbir-001",
        limit=3
    )
    print(f"Status: {pre_context['status']}")
    print(f"Similar work found: {pre_context['similar_work_count']}")
    print(f"Conflicts detected: {pre_context['conflicts_count']}")
    print(f"Recommendations: {len(pre_context['recommendations'])}\n")

    # Simulate agent work
    agent_output = """
    Task: SBIR Phase 1 Proposal
    Outcome: Success
    
    Approach: Used parallel workstreams with daily syncs
    
    KEY LEARNINGS:
    - Timeline compressed by 25%
    - Daily sync meetings improved coordination
    - Pre-written boilerplate saved 15 hours
    
    Metrics:
    - Submitted 3 days early
    - 95% win probability
    """

    print("=== Post-Task: Export and Detect Conflicts ===")
    export = active.export_and_detect_conflicts(
        agent_output=agent_output,
        domain="federal-contracting",
        task_id="task-sbir-001",
        task_title="SBIR Phase 1 Proposal",
        outcome="success",
        approach="Parallel workstreams with daily syncs",
        metadata={"opportunity_id": "OPP-2026-001"}
    )

    print(f"Export status: {export['status']}")
    print(f"Learnings extracted: {export.get('learnings_count', 0)}")
    print(f"Tags generated: {export.get('tags_count', 0)}")
    print(f"Post-task conflicts: {export.get('conflicts_count', 0)}")
    print(f"Decisions required: {len(export.get('decisions_required', []))}\n")

    print("=== System Info ===")
    print(json.dumps(active.info(), indent=2, default=str))
