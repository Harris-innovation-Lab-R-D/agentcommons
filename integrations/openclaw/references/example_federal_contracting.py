"""
Example: Goku (Federal Contracting Agent) Integration with AgentCommons

Shows how Goku queries institutional memory for federal contracting patterns,
SBIR strategies, and proposal competitiveness.
"""

from agentcommons_client import AgentCommonsClient


def goku_startup():
    """Initialize AgentCommons client for Goku."""
    client = AgentCommonsClient()
    print(f"[Goku] AgentCommons initialized: {client.info()['backend_type']}")
    return client


def goku_pre_proposal_research(client: AgentCommonsClient, opportunity_id: str):
    """
    Pre-proposal research: query institutional memory for similar opportunities.
    """
    print(f"\n[Goku] Researching opportunity {opportunity_id}...")

    # 1. Get past SBIR proposals with similar scope
    sbir_memories = client.query_by_similarity(
        "SBIR Phase 1 proposal strategy for advanced technology",
        agent_types=["Goku"],
        date_range=("2026-01-01", None),  # Recent only
        limit=5
    )
    print(f"  Found {len(sbir_memories)} past SBIR insights:")
    for mem in sbir_memories:
        print(f"    - [{mem['relevance_score']:.2f}] {mem['content'][:80]}")

    # 2. Query by specific tag: federal contracting lessons
    fed_lessons = client.query_by_tag(
        "#federal-contracting",
        agent_types=["Goku"],
        limit=3
    )
    print(f"  Found {len(fed_lessons)} federal contracting lessons:")
    for mem in fed_lessons:
        print(f"    - {mem['content'][:80]}")

    # 3. Cross-check: what does institutional memory say about Win Probability?
    win_prob_intel = client.query_by_tag(
        "#win-probability",
        limit=3
    )
    print(f"  Win probability intel: {len(win_prob_intel)} memories")

    return {
        "sbir_context": sbir_memories,
        "fed_lessons": fed_lessons,
        "win_prob_intel": win_prob_intel
    }


def goku_proposal_section_drafting(client: AgentCommonsClient, section: str):
    """
    While drafting proposal sections, query related memories for patterns.
    """
    print(f"\n[Goku] Drafting proposal section: {section}")

    # Map section type to relevant queries
    queries = {
        "technical_approach": "Technical approach for federal proposals",
        "past_performance": "Past performance in federal contracting",
        "management_plan": "Management plans for SBIR Phase 1",
        "cost_narrative": "Cost justification and labor analysis",
    }

    topic = queries.get(section, section)
    results = client.query_by_similarity(topic, limit=5)

    print(f"  Retrieved {len(results)} related memories for {section}:")
    for mem in results:
        print(f"    - [{mem['relevance_score']:.3f}] {mem['content'][:100]}")

    return results


def goku_post_win_analysis(client: AgentCommonsClient, opportunity_id: str, win: bool):
    """
    After win/loss, capture lessons and query similar past outcomes.
    """
    print(f"\n[Goku] Post-award analysis for {opportunity_id} ({'WIN' if win else 'LOSS'})")

    # Query similar past outcomes
    similar_tag = "#federal-contracting" if win else "#federal-contracting-loss"
    similar = client.query_by_tag(similar_tag, limit=3)

    print(f"  Found {len(similar)} similar past outcomes:")
    for mem in similar:
        print(f"    - {mem['content'][:80]}")

    # Would normally save new memories to AgentCommons here
    return similar


def batch_competitive_intelligence(client: AgentCommonsClient):
    """
    Batch query for competitive intelligence across multiple topics.
    """
    print("\n[Goku] Batch competitive intelligence query...")

    topics = [
        "GSA schedule pricing strategy",
        "Incumbent competitor patterns in federal contracting",
        "SBIR Phase 2 teaming requirements",
        "DoD contracting requirements and timelines",
    ]

    batch_results = client.query_batch(topics, limit=3)

    for topic, memories in batch_results.items():
        print(f"\n  {topic}:")
        for mem in memories:
            print(f"    - [{mem.get('relevance_score', 0):.2f}] {mem['content'][:80]}")

    return batch_results


if __name__ == "__main__":
    # Simulate Goku workflow
    client = goku_startup()

    # Pre-proposal research
    context = goku_pre_proposal_research(client, "OPP-2026-001")

    # Section drafting
    tech_approach = goku_proposal_section_drafting(client, "technical_approach")
    cost_narrative = goku_proposal_section_drafting(client, "cost_narrative")

    # Post-win analysis
    post_win = goku_post_win_analysis(client, "OPP-2026-001", win=True)

    # Batch intel
    batch = batch_competitive_intelligence(client)

    # Cache stats
    print(f"\n[Goku] Cache stats: {client.cache_stats()}")
