"""
Conflict Resolution Flow - How Carlton Interacts with AgentCommons Conflicts

Demonstrates:
1. Conflict detection and escalation to Carlton
2. Carlton's decision-making interface
3. Recording decision back to AgentCommons
4. Marking approaches as canonical or deprecated
"""

import json
from datetime import datetime
from typing import Dict, Any


class CarltonConflictHandler:
    """
    Carlton's conflict resolution interface.

    In the Harris Innovation Lab setup, Carlton (the portfolio manager)
    receives conflict escalations and makes strategic decisions about
    which approaches agents should use.
    """

    def __init__(self):
        """Initialize Carlton's conflict handler."""
        self.pending_decisions = {}
        self.resolved_decisions = {}

    def receive_conflict(self, decision_record: Dict[str, Any]) -> None:
        """
        Receive a conflict escalation from an agent.

        Args:
            decision_record: Decision record from ConflictManager
        """
        conflict_id = decision_record["conflict_id"]
        self.pending_decisions[conflict_id] = decision_record

        print(f"\n{'='*70}")
        print(f"📋 CONFLICT ESCALATION TO CARLTON")
        print(f"{'='*70}")
        print(f"Conflict ID: {conflict_id}")
        print(f"Task: {decision_record['source_task_id']}")
        print(f"Status: {decision_record['status']}")
        print(f"Received: {decision_record['created_at']}\n")

    def display_conflict_prompt(self, conflict_id: str) -> None:
        """Display the conflict decision prompt."""
        if conflict_id not in self.pending_decisions:
            print(f"Conflict {conflict_id} not found")
            return

        record = self.pending_decisions[conflict_id]
        print(record["user_prompt"])

    def display_options(self, conflict_id: str) -> None:
        """Display available decision options."""
        if conflict_id not in self.pending_decisions:
            return

        record = self.pending_decisions[conflict_id]
        print("\n📌 YOUR OPTIONS:\n")

        for option in record["options"]:
            print(f"{option['id']}:")
            print(f"  → {option['label']}")
            print(f"  {option['description']}")
            if "rationale_prompt" in option:
                print(f"  {option['rationale_prompt']}")
            print()

    def make_decision(
        self,
        conflict_id: str,
        decision: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Record Carlton's decision.

        Args:
            conflict_id: ID of conflict being resolved
            decision: Choice from available options
            rationale: Explanation for the decision

        Returns:
            Updated decision record
        """
        if conflict_id not in self.pending_decisions:
            return {"error": f"Conflict {conflict_id} not found"}

        record = self.pending_decisions[conflict_id]

        # Validate decision
        valid_decisions = [opt["id"] for opt in record["options"]]
        if decision not in valid_decisions:
            return {"error": f"Invalid decision: {decision}"}

        # Record decision
        record["decision"] = decision
        record["decided_by"] = "Carlton"
        record["decided_at"] = datetime.now().isoformat()
        record["rationale"] = rationale
        record["status"] = "resolved"

        # Move to resolved
        self.resolved_decisions[conflict_id] = record
        del self.pending_decisions[conflict_id]

        print(f"\n✅ DECISION RECORDED")
        print(f"   Decision: {decision}")
        print(f"   Rationale: {rationale}")

        return record

    def list_pending(self) -> list:
        """List all pending conflicts awaiting Carlton's decision."""
        print(f"\n📋 PENDING CONFLICTS ({len(self.pending_decisions)}):\n")

        for conflict_id, record in self.pending_decisions.items():
            print(f"• {conflict_id}")
            print(f"  Task: {record['source_task_id']}")
            print(f"  Status: {record['status']}")
            print(f"  Created: {record['created_at'][:10]}\n")


def demo_conflict_resolution():
    """Demonstrate Carlton's conflict resolution workflow."""

    print("\n" + "="*70)
    print("🎬 CONFLICT RESOLUTION DEMONSTRATION")
    print("="*70)

    carlton = CarltonConflictHandler()

    # Simulated conflict record from Goku task
    conflict_record = {
        "conflict_id": "conflict-task-sbir-001-1709296800",
        "status": "pending",
        "requester": "Carlton",
        "source_task_id": "task-sbir-001",
        "created_at": "2026-03-31T14:30:00Z",
        "comparison": {
            "approach1": "Parallel workstream execution with daily syncs to compress timeline",
            "approach2": "Sequential, thorough workstream execution with weekly reviews",
            "problem_context": "How to deliver high-quality SBIR proposal on tight timeline",
            "similarities": ["execution", "workstream", "timeline", "quality"],
            "differences": {
                "only_in_approach1": ["parallel", "daily", "syncs", "compress"],
                "only_in_approach2": ["sequential", "thorough", "weekly", "reviews"]
            },
            "trade_offs": [
                {
                    "type": "speed_vs_quality",
                    "approach1_leans": "speed",
                    "approach2_leans": "quality"
                }
            ],
            "semantic_similarity": 0.72,
            "structure_similarity": 0.68,
            "overall_similarity": 0.70,
            "metadata1": {
                "source_agent": "Goku (current)",
                "task_id": "task-sbir-001",
                "outcome": "success"
            },
            "metadata2": {
                "source_agent": "Goku (past)",
                "task_id": "task-sbir-2025-015",
                "outcome": "success"
            }
        },
        "user_prompt": """## Conflicting Approaches Detected

**Problem:** How to deliver high-quality SBIR proposal on tight timeline

### Approach 1 (Current)
Parallel workstream execution with daily syncs to compress timeline

### Approach 2 (Past Success)
Sequential, thorough workstream execution with weekly reviews

### Analysis
- **Overall similarity:** 70%
- **Semantic similarity:** 72%
- **Structural similarity:** 68%
- **Common elements:** execution, workstream, timeline, quality
- **Trade-offs:**
  - Speed vs. Quality: Approach 1 leans toward speed, Approach 2 toward quality

Both approaches have been successful. The question is:
- **Approach 1** sacrifices some thoroughness for speed
- **Approach 2** takes more time but produces higher quality

**What's your recommendation?**
""",
        "options": [
            {
                "id": "canonical_approach1",
                "label": "Approach 1 is canonical",
                "description": "Mark approach1 (parallel with daily syncs) as the canonical solution",
                "rationale_prompt": "Why is approach 1 better?"
            },
            {
                "id": "canonical_approach2",
                "label": "Approach 2 is canonical",
                "description": "Mark approach2 (sequential with weekly reviews) as the canonical solution",
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
            }
        ],
        "decision": None,
        "decided_by": None,
        "decided_at": None,
        "rationale": None
    }

    # Step 1: Receive conflict
    print("\n1️⃣  GOKU AGENT sends conflict escalation...")
    carlton.receive_conflict(conflict_record)

    # Step 2: Display conflict for Carlton
    print("\n2️⃣  CARLTON REVIEWS CONFLICT:")
    carlton.display_conflict_prompt(conflict_record["conflict_id"])

    # Step 3: Show options
    print("\n3️⃣  AVAILABLE OPTIONS:")
    carlton.display_options(conflict_record["conflict_id"])

    # Step 4: Carlton makes decision
    print("4️⃣  CARLTON MAKES DECISION:")
    print("   Analyzing trade-offs...")
    print("   • Current deadline: 12 days")
    print("   • Approach 1 works better for tight timelines")
    print("   • Approach 2 is proven but slower")
    print("   • Decision: Use Approach 1 (parallel) but add quality gates")

    decision = carlton.make_decision(
        conflict_id=conflict_record["conflict_id"],
        decision="hybrid",
        rationale="""
For SBIR proposals on tight timelines (< 14 days):
- Use Approach 1 (parallel workstreams with daily syncs) for speed
- Add quality gates: peer review at day 7, external review at day 10
- Keep weekly stakeholder sync from Approach 2 for alignment
        """.strip()
    )

    # Step 5: Decision recorded
    print(f"\n5️⃣  DECISION RECORDED TO AGENTCOMMONS:")
    print(f"   Status: {decision['status']}")
    print(f"   Marking as: 'Hybrid approach - context dependent'")

    # Step 6: Update agent behavior
    print(f"\n6️⃣  AGENTS UPDATED:")
    print(f"   ✓ Goku receives decision: Use hybrid approach")
    print(f"   ✓ Future agents learn from this decision")
    print(f"   ✓ Canonical marking added to AgentCommons")

    print(f"\n{'='*70}")
    print(f"✅ CONFLICT RESOLVED")
    print(f"{'='*70}\n")

    # Step 7: Show decision record
    print("📊 FINAL DECISION RECORD:\n")
    print(json.dumps({
        "conflict_id": decision["conflict_id"],
        "status": decision["status"],
        "decision": decision["decision"],
        "decided_by": decision["decided_by"],
        "decided_at": decision["decided_at"],
        "rationale": decision["rationale"]
    }, indent=2))

    # Step 8: Show how agents use this
    print("\n\n💡 HOW FUTURE AGENTS USE THIS DECISION:\n")
    print("When Goku (or other agents) encounter similar SBIR proposals:")
    print("  1. Query AgentCommons: 'How do I handle SBIR proposals?'")
    print("  2. Find this decision record: 'Hybrid approach recommended'")
    print("  3. See Carlton's rationale: 'For tight timelines < 14 days'")
    print("  4. Implement: Parallel workstreams + quality gates")
    print("  5. Feedback loop: Report success/failure back to AgentCommons")

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    demo_conflict_resolution()
