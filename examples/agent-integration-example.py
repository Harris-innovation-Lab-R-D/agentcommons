"""
Goku Federal Contracting Agent - AgentCommons Active Learning Integration Example

Shows how Goku (federal contracting agent) integrates with AgentCommons:
1. Pre-task: Query for similar SBIR wins, detect approach conflicts
2. Task execution: Normal Goku workflow
3. Post-task: Export proposal learnings, tag outcomes
"""

import json
from typing import Dict, Any, Optional

# In real implementation:
# from sys import path
# path.insert(0, '/path/to/python_modules')
# from agentcommons_active import AgentCommonsActiveLearning


class GokuFederalBDAgent:
    """Simplified Goku agent with AgentCommons integration."""

    def __init__(self):
        """Initialize Goku with active learning."""
        self.agent_name = "Goku"
        self.agent_type = "federal-contracting"

        # Initialize active learning (would be real client in production)
        # self.active_learning = AgentCommonsActiveLearning(
        #     agent_name=self.agent_name,
        #     agent_type=self.agent_type
        # )

        self.output = None

    def execute_sbir_proposal_task(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute SBIR proposal writing with active learning.

        Args:
            opportunity: Opportunity details (ID, description, etc.)

        Returns:
            Task result with exported learnings
        """
        task_id = opportunity.get("id", "task-unknown")
        task_title = f"SBIR {opportunity.get('phase', 'Phase 1')} Proposal"

        print(f"\n{'='*60}")
        print(f"GOKU: Starting {task_title}")
        print(f"{'='*60}\n")

        # ===== STEP 1: PRE-TASK QUERY =====
        print("1️⃣  PRE-TASK: Querying AgentCommons for similar work...")

        pre_context = self._pre_task_phase(
            domain="federal-contracting",
            topic=task_title,
            task_id=task_id
        )

        print(f"   ✓ Found {pre_context['similar_work_count']} similar SBIR wins")
        print(f"   ✓ Conflicts detected: {pre_context['conflicts_count']}")

        if pre_context['recommendations']:
            print(f"   📌 Recommendations:")
            for rec in pre_context['recommendations']:
                print(f"      - {rec['message']}")

        # ===== STEP 2: CHECK FOR APPROACH CONFLICTS =====
        if pre_context['conflicts']:
            print(f"\n   ⚠️  CONFLICT DETECTED: {len(pre_context['conflicts'])} approach divergence(s)")
            for conflict in pre_context['conflicts']:
                print(f"      - {conflict['conflict_type']}: "
                      f"{conflict['approach_divergence']:.0%} divergent from past work")

            # In real scenario, Carlton would review and decide
            print(f"\n   → Escalating to Carlton for decision...")
            # decision = carlton.review_conflicts(pre_context['conflicts'])
            decision = "proceed_proposed"  # Simulate decision
            print(f"   ✓ Carlton approved: {decision}")

        # ===== STEP 3: NORMAL GOKU TASK EXECUTION =====
        print(f"\n2️⃣  EXECUTION: Running proposal generation workflow...")
        print(f"   - Analyzing opportunity...")
        print(f"   - Building executive summary...")
        print(f"   - Writing technical approach...")
        print(f"   - Structuring management plan...")
        print(f"   - Compiling budget narrative...")

        # Simulate task result
        task_result = self._execute_proposal_workflow(opportunity)

        print(f"   ✓ Proposal generated: {task_result['page_count']} pages")
        print(f"   ✓ Estimated win probability: {task_result['win_probability']:.0%}")
        print(f"   ✓ Timeline: {task_result['timeline_days']} days (vs. {opportunity.get('deadline_days', 60)} target)")

        # ===== STEP 4: POST-TASK EXPORT & CONFLICT DETECTION =====
        print(f"\n3️⃣  POST-TASK: Exporting learnings to AgentCommons...")

        export_result = self._post_task_phase(
            agent_output=task_result,
            domain="federal-contracting",
            task_id=task_id,
            task_title=task_title,
            outcome=task_result['outcome']
        )

        print(f"   ✓ Exported to AgentCommons (ID: {export_result.get('id')})")
        print(f"   ✓ Learnings extracted: {export_result.get('learnings_count', 0)}")
        print(f"   ✓ Tags generated: {', '.join(export_result.get('tags', [])[:5])}")

        if export_result.get('conflicts'):
            print(f"\n   ⚠️  POST-TASK CONFLICT: Different approach from similar past work")
            print(f"   → Escalating for Carlton's decision...")

        print(f"\n{'='*60}")
        print(f"✅ Task complete: {task_title}")
        print(f"{'='*60}\n")

        return {
            "task_id": task_id,
            "task_title": task_title,
            "pre_context": pre_context,
            "execution": task_result,
            "export": export_result
        }

    def _pre_task_phase(self, domain: str, topic: str, task_id: str) -> Dict[str, Any]:
        """
        Pre-task: Query AgentCommons for related work and conflicts.

        In real implementation, calls:
        context = self.active_learning.query_and_check_conflicts(...)
        """
        # Simulated response
        return {
            "task_id": task_id,
            "domain": domain,
            "similar_work_count": 3,
            "conflicts_count": 1,
            "recommendations": [
                {
                    "type": "related_work",
                    "message": "Similar SBIR win from Goku (2026-03-15): 'Fast-track parallel proposal workflow'"
                }
            ],
            "conflicts": [
                {
                    "conflict_type": "speed_vs_quality",
                    "approach_divergence": 0.65,
                    "past_outcome": "Success (95% Pwin)",
                    "source_agent": "Goku"
                }
            ],
            "status": "conflicts_detected"
        }

    def _execute_proposal_workflow(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute normal Goku proposal workflow.

        Returns simulated output for demo purposes.
        """
        return {
            "task_type": "proposal_writing",
            "outcome": "success",
            "page_count": 45,
            "timeline_days": 12,
            "win_probability": 0.87,
            "approach": "Parallel workstreams (technical, management, budget) with daily syncs",
            "sections_written": [
                "Executive Summary (2 pages)",
                "Technical Approach (15 pages)",
                "Management Plan (8 pages)",
                "Budget & Budget Narrative (12 pages)",
                "Appendices (8 pages)"
            ],
            "efficiency_metrics": {
                "timeline_compression": 0.25,  # 25% faster than baseline
                "reuse_rate": 0.30,  # 30% content reused from past proposals
                "quality_score": 0.92  # 0-1 scale
            },
            "key_learnings": [
                "Parallel execution with daily syncs reduces timeline by 25%",
                "Pre-written boilerplate (abstracts, company background) saves 12-15 hours",
                "AI-assisted first draft generation improves quality and speed",
                "Reviewer integration at day 7 catches major issues early"
            ]
        }

    def _post_task_phase(
        self,
        agent_output: Dict[str, Any],
        domain: str,
        task_id: str,
        task_title: str,
        outcome: str
    ) -> Dict[str, Any]:
        """
        Post-task: Export learnings to AgentCommons.

        In real implementation, calls:
        export = self.active_learning.export_and_detect_conflicts(...)
        """
        # Simulated export response
        return {
            "id": f"goku-{task_id}-{1709296800}",
            "status": "stored",
            "learnings_count": 4,
            "tags": [
                "#federal-contracting",
                "#agent:goku",
                "#outcome:success",
                "#sbir",
                "#timeline-compression",
                "#proposal-writing",
                "#2026-03"
            ],
            "learnings": agent_output.get('key_learnings', []),
            "metadata": {
                "opportunity_id": task_id,
                "approach": "Parallel workstreams with daily syncs",
                "outcome": outcome,
                "efficiency": agent_output.get('efficiency_metrics', {})
            },
            "conflicts_count": 0
        }


def demo_integration():
    """Demonstrate Goku with AgentCommons integration."""
    print("\n" + "="*60)
    print("🚀 GOKU FEDERAL CONTRACTING AGENT")
    print("   with AgentCommons Active Learning")
    print("="*60)

    agent = GokuFederalBDAgent()

    # Example opportunity
    opportunity = {
        "id": "SBIR-2026-001",
        "title": "Advanced Materials Processing",
        "phase": "Phase 1",
        "deadline_days": 60,
        "estimated_budget": 150000
    }

    # Execute with full active learning pipeline
    result = agent.execute_sbir_proposal_task(opportunity)

    print("\n📊 FINAL SUMMARY:")
    print(f"   Pre-task conflicts: {result['pre_context']['conflicts_count']}")
    print(f"   Execution outcome: {result['execution']['outcome']}")
    print(f"   Learnings exported: {result['export']['learnings_count']}")

    print("\n📚 LEARNINGS FOR FUTURE AGENTS:")
    for i, learning in enumerate(result['export']['learnings'], 1):
        print(f"   {i}. {learning}")


if __name__ == "__main__":
    demo_integration()
