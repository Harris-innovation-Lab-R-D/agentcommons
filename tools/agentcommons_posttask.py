"""
PostTaskExporter - Export agent learnings to AgentCommons after task completion

Extracts insights from agent output, auto-generates tags, and persists learnings
to the centralized memory network for future agents to learn from.
"""

import json
import re
from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from agentcommons_client import AgentCommonsClient, AgentCommonsUnavailableError


class PostTaskExporter:
    """Export learnings and task outcomes to AgentCommons."""

    def __init__(self, client: Optional[AgentCommonsClient] = None):
        """
        Initialize PostTaskExporter.

        Args:
            client: Optional AgentCommonsClient (creates default if not provided)
        """
        self.client = client or AgentCommonsClient()

    def extract_learnings(
        self,
        agent_output: Union[str, Dict[str, Any]],
        task_type: str,
        keywords: Optional[List[str]] = None
    ) -> List[str]:
        """
        Parse agent output and extract key learnings.

        Args:
            agent_output: Raw agent output (text or structured dict)
            task_type: Type of task (e.g., "proposal_writing", "sales_outreach")
            keywords: Optional keywords to search for (e.g., ["timeline", "cost"])

        Returns:
            List of extracted learning strings
        """
        learnings = []

        # Convert dict to text if needed
        if isinstance(agent_output, dict):
            text = json.dumps(agent_output, indent=2)
        else:
            text = str(agent_output)

        # Search for explicit learning patterns
        learning_patterns = [
            r"(?:KEY LEARNING|LEARNED|INSIGHT|KEY INSIGHT|FINDING|DISCOVERED)[\s:]+([^.!?\n]+[.!?]?)",
            r"(?:Best practice|Lesson|Recommendation)[\s:]+([^.!?\n]+[.!?]?)",
            r"## (?:Insights|Learnings|Key Findings)(.*?)(?=##|$)"
        ]

        for pattern in learning_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            learnings.extend(matches)

        # Extract metric-related learnings
        metric_patterns = [
            r"(?:achieved|improved|reduced|increased).*?(?:by|to|at)\s+(\d+%?|\$[\d,]+)",
            r"(?:timeline|duration|cost|budget)[\s:]+(\d+\s*(?:hours?|days?|weeks?|months?|dollars?|%))"
        ]

        for pattern in metric_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                learnings.extend([f"Metric: {m}" for m in matches])

        # Extract keyword-based learnings
        if keywords:
            for keyword in keywords:
                keyword_pattern = rf"(?:[^.!?\n]*{keyword}[^.!?\n]*[.!?])"
                matches = re.findall(keyword_pattern, text, re.IGNORECASE)
                learnings.extend(matches)

        # Clean up duplicates and empty strings
        learnings = list(set(l.strip() for l in learnings if l.strip() and len(l.strip()) > 10))

        return learnings

    def auto_tag(
        self,
        domain: str,
        agent_type: str,
        outcome: Optional[str] = None,
        task_title: Optional[str] = None,
        additional_tags: Optional[List[str]] = None
    ) -> List[str]:
        """
        Auto-generate tags for memory entry.

        Args:
            domain: Domain name (e.g., "federal-contracting")
            agent_type: Agent type (e.g., "Goku")
            outcome: Task outcome (e.g., "success", "partial", "failed")
            task_title: Task title for keyword extraction
            additional_tags: Manual tags to include

        Returns:
            List of tags (prefixed with #)
        """
        tags = set()

        # Domain tag
        tags.add(f"#{domain}")

        # Agent type tag
        tags.add(f"#agent:{agent_type.lower()}")

        # Outcome tag
        if outcome:
            outcome_lower = outcome.lower()
            if outcome_lower in ["success", "win", "completed"]:
                tags.add("#outcome:success")
            elif outcome_lower in ["partial", "incomplete"]:
                tags.add("#outcome:partial")
            elif outcome_lower in ["failed", "failed"]:
                tags.add("#outcome:failed")

        # Extract keywords from task title
        if task_title:
            keywords = [
                "proposal", "sbir", "pipeline", "prospect", "discovery", "research",
                "outreach", "negotiation", "timeline", "cost", "scope", "quality",
                "automation", "analysis", "synthesis", "decision", "strategy",
                "intel", "competitive", "win-probability", "capture-planning"
            ]

            task_lower = task_title.lower()
            for keyword in keywords:
                if keyword in task_lower:
                    tags.add(f"#{keyword}")

        # Add manual tags
        if additional_tags:
            for tag in additional_tags:
                if not tag.startswith("#"):
                    tag = f"#{tag}"
                tags.add(tag)

        # Add timestamp tag (year-month)
        now = datetime.now()
        tags.add(f"#{now.year}-{now.month:02d}")

        return sorted(list(tags))

    def push_to_agentcommons(
        self,
        content: str,
        source_agent: str,
        agent_type: str,
        domain: str,
        tags: List[str],
        task_id: Optional[str] = None,
        outcome: Optional[str] = None,
        learnings: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Export learning to AgentCommons SQLite.

        Args:
            content: Main content/summary of the learning
            source_agent: Agent name (e.g., "Goku")
            agent_type: Agent type (e.g., "federal-contracting")
            domain: Domain (e.g., "federal-contracting")
            tags: List of tags
            task_id: Optional task ID for traceability
            outcome: Task outcome (success/partial/failed)
            learnings: Optional list of extracted learnings
            metadata: Optional additional metadata (dict)

        Returns:
            Export result with ID and status
        """
        export_record = {
            "id": f"{source_agent.lower()}-{task_id or 'auto'}-{datetime.now().timestamp()}",
            "content": content,
            "source_agent": source_agent,
            "agent_type": agent_type,
            "domain": domain,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "embedding_model": self.client.embedding_model,
            "task_id": task_id,
            "outcome": outcome,
            "learnings": learnings or [],
            "metadata": metadata or {}
        }

        try:
            # Call API to store in AgentCommons
            response = self.client._call_api("write/memory", {
                "memory": json.dumps(export_record)
            })

            export_record["status"] = "stored"
            export_record["api_response"] = response

        except AgentCommonsUnavailableError:
            # Fallback: store in client cache as "pending"
            self.client._memory_cache[export_record["id"]] = [export_record]
            export_record["status"] = "pending_sync"

        return export_record

    def export_and_detect_conflicts(
        self,
        agent_output: Union[str, Dict[str, Any]],
        source_agent: str,
        agent_type: str,
        domain: str,
        task_id: str,
        task_title: Optional[str] = None,
        outcome: Optional[str] = None,
        approach: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Full post-task workflow: export + detect conflicts.

        Args:
            agent_output: Raw agent output
            source_agent: Agent name
            agent_type: Agent type
            domain: Domain
            task_id: Task ID
            task_title: Optional task title
            outcome: Task outcome
            approach: Agent's approach (used for conflict detection)
            metadata: Additional metadata

        Returns:
            Export result with conflict detection
        """
        # Extract learnings
        learnings = self.extract_learnings(agent_output, agent_type, keywords=None)

        # Auto-generate tags
        tags = self.auto_tag(
            domain=domain,
            agent_type=agent_type,
            outcome=outcome,
            task_title=task_title
        )

        # Generate content summary
        content = task_title or "Task summary from agent output"
        if isinstance(agent_output, dict) and "summary" in agent_output:
            content = agent_output["summary"]

        # Push to AgentCommons
        export_result = self.push_to_agentcommons(
            content=content,
            source_agent=source_agent,
            agent_type=agent_type,
            domain=domain,
            tags=tags,
            task_id=task_id,
            outcome=outcome,
            learnings=learnings,
            metadata=metadata or {}
        )

        # Prepare conflict detection result
        export_result["learnings_count"] = len(learnings)
        export_result["tags_count"] = len(tags)

        return export_result


if __name__ == "__main__":
    # Quick test
    exporter = PostTaskExporter()

    # Example: Extract learnings from agent output
    sample_output = """
    TASK: Write SBIR Phase 1 proposal
    
    KEY LEARNINGS:
    - Parallel workstream execution reduced timeline by 25%
    - Daily sync meetings improved coordination
    - Pre-written boilerplate saved 15 hours
    
    OUTCOME: Proposal submitted 3 days early
    """

    learnings = exporter.extract_learnings(
        agent_output=sample_output,
        task_type="proposal_writing"
    )
    print(f"Extracted {len(learnings)} learnings:")
    for learning in learnings:
        print(f"  - {learning}")

    # Generate tags
    tags = exporter.auto_tag(
        domain="federal-contracting",
        agent_type="Goku",
        outcome="success",
        task_title="SBIR Phase 1 Proposal Writing",
        additional_tags=["sbir", "timeline-compression"]
    )
    print(f"\nGenerated tags: {', '.join(tags)}")

    # Export to AgentCommons
    export_result = exporter.push_to_agentcommons(
        content="Successfully compressed SBIR Phase 1 proposal timeline using parallel workstreams",
        source_agent="Goku",
        agent_type="federal-contracting",
        domain="federal-contracting",
        tags=tags,
        task_id="task-sbir-2026-001",
        outcome="success",
        learnings=learnings,
        metadata={"opportunity_id": "OPP-2026-001"}
    )
    print(f"\nExport result:\n{json.dumps(export_result, indent=2, default=str)}")
