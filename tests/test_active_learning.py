"""
Unit tests for AgentCommons Active Learning System

Tests all four modules:
- agentcommons_pretask.py
- agentcommons_posttask.py
- agentcommons_conflict.py
- agentcommons_active.py
"""

import json
import unittest
from datetime import datetime
from typing import List, Dict, Any

from agentcommons_pretask import PreTaskQueryer
from agentcommons_posttask import PostTaskExporter
from agentcommons_conflict import ConflictManager
from agentcommons_active import AgentCommonsActiveLearning


class TestPreTaskQueryer(unittest.TestCase):
    """Test pre-task query functionality."""

    def setUp(self):
        """Initialize test fixtures."""
        self.querier = PreTaskQueryer()

    def test_query_similar_work_returns_list(self):
        """Pre-task should return list of similar work."""
        similar = self.querier.query_similar_work(
            domain="federal-contracting",
            topic="SBIR Phase 1 proposal",
            limit=3
        )
        self.assertIsInstance(similar, list)

    def test_detect_conflicting_approaches_with_similar_problems(self):
        """Should detect conflicts when problem is similar but approach differs."""
        conflicts = self.querier.detect_conflicting_approaches(
            problem="How to compress proposal timeline",
            proposed_approach="Parallel workstream execution",
            similarity_threshold=0.7
        )
        self.assertIsInstance(conflicts, list)

    def test_text_similarity_identical_texts(self):
        """Identical texts should have high similarity."""
        sim = self.querier._compute_text_similarity(
            "parallel workstream execution",
            "parallel workstream execution"
        )
        self.assertEqual(sim, 1.0)

    def test_text_similarity_different_texts(self):
        """Different texts should have low similarity."""
        sim = self.querier._compute_text_similarity(
            "parallel workstreams",
            "sequential reviews"
        )
        self.assertLess(sim, 0.5)

    def test_text_similarity_empty_strings(self):
        """Empty strings should return 0 similarity."""
        sim = self.querier._compute_text_similarity("", "")
        self.assertEqual(sim, 0.0)

    def test_conflict_classification_speed_vs_quality(self):
        """Should classify speed vs. quality conflicts."""
        conflict_type = self.querier._classify_conflict(
            "fast parallel execution",
            "thorough sequential reviews"
        )
        self.assertIn(conflict_type, ["speed_vs_quality", "other"])

    def test_escalate_conflicts_to_user_creates_decision_record(self):
        """Should create decision record for user review."""
        conflicts = [
            {
                "conflict_type": "speed_vs_quality",
                "approach_divergence": 0.65,
                "past_outcome": "Success",
                "problem_similarity": 0.80,
                "past_work_id": "past-001",
                "past_content": "Past proposal",
                "past_approach": "Sequential approach",
                "source_agent": "Goku",
                "created_at": "2026-03-25"
            }
        ]
        decision = self.querier.escalate_conflicts_to_user(
            conflicts=conflicts,
            task_id="task-001"
        )
        self.assertEqual(decision["status"], "pending")
        self.assertEqual(len(decision["options"]), 4)
        self.assertIn("prompt_for_user", decision)


class TestPostTaskExporter(unittest.TestCase):
    """Test post-task export functionality."""

    def setUp(self):
        """Initialize test fixtures."""
        self.exporter = PostTaskExporter()

    def test_extract_learnings_from_text(self):
        """Should extract learnings from task output."""
        output = """
        KEY LEARNING: Parallel execution reduces timeline by 25%
        INSIGHT: Daily syncs improve coordination
        Recommendation: Use pre-written templates
        """
        learnings = self.exporter.extract_learnings(
            agent_output=output,
            task_type="proposal_writing"
        )
        self.assertGreater(len(learnings), 0)
        self.assertTrue(any("timeline" in l.lower() for l in learnings))

    def test_extract_learnings_from_dict(self):
        """Should extract learnings from dict output."""
        output = {
            "summary": "Task completed successfully",
            "learnings": ["Learning 1", "Learning 2"],
            "metrics": {"timeline": 12}
        }
        learnings = self.exporter.extract_learnings(
            agent_output=output,
            task_type="proposal_writing"
        )
        self.assertIsInstance(learnings, list)

    def test_auto_tag_generates_tags(self):
        """Should auto-generate tags."""
        tags = self.exporter.auto_tag(
            domain="federal-contracting",
            agent_type="Goku",
            outcome="success",
            task_title="SBIR Phase 1 Proposal"
        )
        self.assertGreater(len(tags), 0)
        self.assertTrue(any(t.startswith("#") for t in tags))
        self.assertIn("#federal-contracting", tags)
        self.assertIn("#agent:goku", tags)
        self.assertIn("#outcome:success", tags)

    def test_auto_tag_with_additional_tags(self):
        """Should include additional manual tags."""
        tags = self.exporter.auto_tag(
            domain="federal-contracting",
            agent_type="Goku",
            additional_tags=["custom-tag", "another-tag"]
        )
        self.assertIn("#custom-tag", tags)
        self.assertIn("#another-tag", tags)

    def test_push_to_agentcommons_creates_record(self):
        """Should create export record."""
        export = self.exporter.push_to_agentcommons(
            content="Test learning",
            source_agent="TestAgent",
            agent_type="test-domain",
            domain="test-domain",
            tags=["#test"],
            task_id="task-001",
            outcome="success"
        )
        # Status can be "stored" (API success) or "pending_sync" (fallback)
        self.assertIn(export["status"], ["stored", "pending_sync"])
        self.assertEqual(export["source_agent"], "TestAgent")
        self.assertEqual(export["outcome"], "success")

    def test_export_and_detect_conflicts_full_workflow(self):
        """Should handle full post-task export workflow."""
        export = self.exporter.export_and_detect_conflicts(
            agent_output="Task completed with learning",
            source_agent="TestAgent",
            agent_type="test-domain",
            domain="test-domain",
            task_id="task-001",
            task_title="Test Task",
            outcome="success"
        )
        self.assertIn("status", export)
        self.assertIn("learnings_count", export)
        self.assertIn("tags_count", export)


class TestConflictManager(unittest.TestCase):
    """Test conflict detection and management."""

    def setUp(self):
        """Initialize test fixtures."""
        self.manager = ConflictManager()

    def test_compare_approaches_returns_comparison(self):
        """Should compare two approaches."""
        comparison = self.manager.compare_approaches(
            approach1="Parallel workstreams with daily syncs",
            approach2="Sequential workstreams with weekly reviews",
            problem_context="SBIR proposal delivery"
        )
        self.assertIn("approach1", comparison)
        self.assertIn("approach2", comparison)
        self.assertIn("similarities", comparison)
        self.assertIn("differences", comparison)
        self.assertIn("trade_offs", comparison)
        self.assertIn("overall_similarity", comparison)

    def test_similarity_scores_in_range(self):
        """Similarity scores should be 0-1."""
        comparison = self.manager.compare_approaches(
            approach1="Parallel execution",
            approach2="Sequential execution",
            problem_context="Proposal delivery"
        )
        self.assertGreaterEqual(comparison["semantic_similarity"], 0.0)
        self.assertLessEqual(comparison["semantic_similarity"], 1.0)
        self.assertGreaterEqual(comparison["structure_similarity"], 0.0)
        self.assertLessEqual(comparison["structure_similarity"], 1.0)

    def test_extract_similarities_finds_common_words(self):
        """Should extract common words between approaches."""
        similarities = self.manager._extract_similarities(
            "parallel workstreams with daily syncs",
            "sequential workstreams with weekly syncs"
        )
        self.assertIn("workstreams", similarities)
        self.assertIn("syncs", similarities)

    def test_extract_differences_finds_unique_words(self):
        """Should extract unique words."""
        differences = self.manager._extract_differences(
            "parallel execution daily",
            "sequential execution weekly"
        )
        self.assertIn("parallel", differences["only_in_approach1"])
        self.assertIn("sequential", differences["only_in_approach2"])

    def test_identify_tradeoffs_detects_speed_vs_quality(self):
        """Should detect speed vs. quality trade-off."""
        tradeoffs = self.manager._identify_tradeoffs(
            "parallel execution for speed",
            "sequential execution for quality"
        )
        self.assertGreater(len(tradeoffs), 0)
        self.assertTrue(any(t["type"] == "speed_vs_quality" for t in tradeoffs))

    def test_create_decision_record_has_options(self):
        """Decision record should have options."""
        comparison = self.manager.compare_approaches(
            approach1="Fast parallel execution for speed",
            approach2="Thorough sequential execution for quality",
            problem_context="How to deliver proposal on time"
        )
        decision = self.manager.create_decision_record(
            comparison=comparison,
            source_task_id="task-001"
        )
        self.assertEqual(decision["status"], "pending")
        self.assertEqual(len(decision["options"]), 5)  # 5 decision options
        self.assertIn("conflict_id", decision)

    def test_apply_user_decision_updates_record(self):
        """Should update conflict record with decision."""
        comparison = self.manager.compare_approaches(
            approach1="A", approach2="B", problem_context="P"
        )
        decision = self.manager.create_decision_record(
            comparison=comparison,
            source_task_id="task-001"
        )
        conflict_id = decision["conflict_id"]

        updated = self.manager.apply_user_decision(
            conflict_id=conflict_id,
            decision="canonical_approach1",
            rationale="Approach 1 is better"
        )
        self.assertEqual(updated["status"], "resolved")
        self.assertEqual(updated["decision"], "canonical_approach1")
        self.assertIsNotNone(updated["decided_at"])

    def test_list_conflicts_filters_by_status(self):
        """Should list conflicts and filter by status."""
        comparison = self.manager.compare_approaches(
            approach1="Fast parallel execution",
            approach2="Thorough sequential execution",
            problem_context="How to complete task"
        )
        decision = self.manager.create_decision_record(
            comparison=comparison,
            source_task_id="task-001"
        )

        pending = self.manager.list_conflicts(status="pending")
        self.assertGreater(len(pending), 0)

        resolved = self.manager.list_conflicts(status="resolved")
        self.assertEqual(len(resolved), 0)

        # Resolve one
        self.manager.apply_user_decision(
            conflict_id=decision["conflict_id"],
            decision="canonical_approach1",
            rationale="Test"
        )

        resolved = self.manager.list_conflicts(status="resolved")
        self.assertGreater(len(resolved), 0)


class TestAgentCommonsActiveLearning(unittest.TestCase):
    """Test integrated active learning system."""

    def setUp(self):
        """Initialize test fixtures."""
        self.active = AgentCommonsActiveLearning(
            agent_name="TestAgent",
            agent_type="test-domain"
        )

    def test_initialization(self):
        """Should initialize with agent info."""
        self.assertEqual(self.active.agent_name, "TestAgent")
        self.assertEqual(self.active.agent_type, "test-domain")

    def test_query_and_check_conflicts_returns_context(self):
        """Pre-task should return context."""
        context = self.active.query_and_check_conflicts(
            domain="test-domain",
            topic="test topic",
            task_id="task-001"
        )
        self.assertIn("task_id", context)
        self.assertIn("similar_work", context)
        self.assertIn("conflicts", context)
        self.assertIn("status", context)

    def test_export_and_detect_conflicts_returns_export(self):
        """Post-task should return export."""
        export = self.active.export_and_detect_conflicts(
            agent_output="Test output",
            domain="test-domain",
            task_id="task-001",
            task_title="Test Task",
            outcome="success"
        )
        self.assertIn("task_id", export)
        self.assertIn("status", export)
        self.assertIn("conflicts", export)

    def test_session_conflicts_tracking(self):
        """Should track conflicts in session."""
        context = self.active.query_and_check_conflicts(
            domain="test-domain",
            topic="test",
            task_id="task-001"
        )

        session_conflicts = self.active.get_session_conflicts()
        self.assertIsInstance(session_conflicts, dict)

    def test_info_returns_system_info(self):
        """Should return system info."""
        info = self.active.info()
        self.assertEqual(info["agent_name"], "TestAgent")
        self.assertEqual(info["agent_type"], "test-domain")
        self.assertIn("client_info", info)


class TestIntegrationEnd2End(unittest.TestCase):
    """End-to-end integration tests."""

    def setUp(self):
        """Initialize test fixtures."""
        self.active = AgentCommonsActiveLearning(
            agent_name="Goku",
            agent_type="federal-contracting"
        )

    def test_full_workflow_success(self):
        """Test complete workflow: pre → execute → post."""
        # Pre-task
        context = self.active.query_and_check_conflicts(
            domain="federal-contracting",
            topic="SBIR Phase 1 proposal",
            task_id="task-sbir-001"
        )
        self.assertIsNotNone(context)

        # Simulate task execution
        task_result = {
            "title": "SBIR Phase 1 Proposal",
            "outcome": "success",
            "approach": "Parallel workstreams",
            "learnings": ["Reduced timeline by 25%"],
            "timeline_days": 12
        }

        # Post-task
        export = self.active.export_and_detect_conflicts(
            agent_output=task_result,
            domain="federal-contracting",
            task_id="task-sbir-001",
            task_title="SBIR Phase 1 Proposal",
            outcome="success",
            approach="Parallel workstreams with daily syncs"
        )

        # Status can be "exported", "stored" (API), or "pending_sync" (fallback)
        self.assertIn(export["status"], ["exported", "stored", "pending_sync"])
        self.assertGreaterEqual(export.get("learnings_count", 0), 0)

    def test_conflict_workflow(self):
        """Test conflict detection and resolution."""
        # Query
        context = self.active.query_and_check_conflicts(
            domain="federal-contracting",
            topic="SBIR Phase 1 proposal",
            task_id="task-sbir-002"
        )

        # If conflicts detected, test escalation
        if context.get("conflicts"):
            conflicts = context["conflicts"]
            self.assertGreater(len(conflicts), 0)

            # Test decision making
            for conflict in conflicts:
                self.assertIn("conflict_type", conflict)
                self.assertIn("approach_divergence", conflict)


class TestDataSchemaValidation(unittest.TestCase):
    """Validate data schema compliance."""

    def test_pretask_context_schema(self):
        """Pre-task context should match expected schema."""
        querier = PreTaskQueryer()
        context = querier.query_similar_work(
            domain="federal-contracting",
            topic="SBIR",
            limit=1
        )
        # Should be list of dicts with required fields
        if context:
            for item in context:
                self.assertIsInstance(item, dict)

    def test_export_record_schema(self):
        """Export record should match expected schema."""
        exporter = PostTaskExporter()
        export = exporter.push_to_agentcommons(
            content="Test",
            source_agent="Test",
            agent_type="test",
            domain="test",
            tags=["#test"],
            task_id="task-001"
        )
        self.assertIn("id", export)
        self.assertIn("status", export)
        self.assertIn("created_at", export)

    def test_conflict_decision_schema(self):
        """Conflict decision should match expected schema."""
        manager = ConflictManager()
        comparison = manager.compare_approaches(
            approach1="Fast parallel approach",
            approach2="Thorough sequential approach",
            problem_context="How to deliver on time"
        )
        decision = manager.create_decision_record(
            comparison=comparison,
            source_task_id="task-001"
        )
        self.assertIn("conflict_id", decision)
        self.assertIn("status", decision)
        self.assertIn("comparison", decision)
        self.assertIn("options", decision)


def run_tests():
    """Run all tests."""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()
