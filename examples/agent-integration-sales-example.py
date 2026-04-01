"""
Example: Loki (Sales Agent) Integration with AgentCommons

Shows how Loki queries institutional memory for sales pipeline stages,
prospect qualification patterns, and GTM strategies.
"""

from agentcommons_client import AgentCommonsClient


def loki_startup():
    """Initialize AgentCommons client for Loki."""
    client = AgentCommonsClient()
    print(f"[Loki] AgentCommons initialized: {client.info()['backend_type']}")
    return client


def loki_prospect_qualification(client: AgentCommonsClient, prospect_name: str, industry: str):
    """
    Pre-qualification: query institutional memory for qualification patterns.
    """
    print(f"\n[Loki] Qualifying prospect: {prospect_name} ({industry})")

    # 1. Query by prospect industry + qualification tag
    industry_patterns = client.query_by_similarity(
        f"Prospect qualification in {industry} sector",
        agent_types=["Loki"],
        date_range=("2026-01-01", None),
        limit=5
    )
    print(f"  Found {len(industry_patterns)} qualification patterns for {industry}:")
    for mem in industry_patterns:
        print(f"    - [{mem['relevance_score']:.2f}] {mem['content'][:80]}")

    # 2. Query cross-agent intel: What do federal agents know about this industry?
    fed_intel = client.query_by_tag(
        "#prospect-qualification",
        agent_types=["Goku"],  # Learn from federal contracting perspective
        limit=3
    )
    print(f"  Cross-domain intel from Goku: {len(fed_intel)} memories")

    # 3. Query sales pipeline stage guidance
    pipeline_guidance = client.query_by_tag(
        "#sales-pipeline-qualification",
        limit=3
    )
    print(f"  Pipeline stage guidance: {len(pipeline_guidance)} memories")

    return {
        "industry_patterns": industry_patterns,
        "fed_intel": fed_intel,
        "pipeline_guidance": pipeline_guidance
    }


def loki_gtt_strategy(client: AgentCommonsClient, prospect_name: str, deal_size: str):
    """
    Go-to-market strategy: query past successful GTM playbooks.
    """
    print(f"\n[Loki] Developing GTM strategy for {prospect_name} (${deal_size})")

    # Query similar deal sizes
    gtt_playbooks = client.query_by_similarity(
        f"Go-to-market strategy for {deal_size} enterprise deal",
        agent_types=["Loki"],
        limit=5
    )

    print(f"  Found {len(gtt_playbooks)} GTM playbooks:")
    for mem in gtt_playbooks:
        print(f"    - [{mem['relevance_score']:.3f}] {mem['content'][:100]}")

    # Query by GTM tag for general patterns
    gtt_patterns = client.query_by_tag(
        "#gtt-strategy",
        min_relevance=0.6,
        limit=3
    )

    return gtt_playbooks + gtt_patterns


def loki_proposal_discovery(client: AgentCommonsClient, prospect_name: str, challenge: str):
    """
    Proposal discovery phase: query institutional memory for solution patterns.
    """
    print(f"\n[Loki] Discovery for {prospect_name}: {challenge}")

    # Find past solutions to similar challenges
    solutions = client.query_by_similarity(
        f"Solution approach for {challenge}",
        limit=5
    )

    print(f"  Found {len(solutions)} similar solution patterns:")
    for mem in solutions:
        print(f"    - {mem['content'][:100]}")

    # Query tag-based domain knowledge
    domain_tag = "#solution-architecture" if "architecture" in challenge.lower() else "#product-solution"
    domain_intel = client.query_by_tag(domain_tag, limit=3)

    return solutions + domain_intel


def loki_win_probability_assessment(client: AgentCommonsClient, prospect_name: str):
    """
    Win probability assessment: query past outcomes for similar prospects.
    """
    print(f"\n[Loki] Win probability assessment for {prospect_name}")

    # Query past win/loss outcomes
    past_outcomes = client.query_by_tag(
        "#sales-outcome",
        date_range=("2026-01-01", None),
        limit=5
    )

    print(f"  Found {len(past_outcomes)} past outcome memories:")
    for mem in past_outcomes:
        print(f"    - [{mem.get('metadata', {}).get('outcome', 'unknown')}] {mem['content'][:80]}")

    # Query Goku's Pwin assessments (cross-domain)
    pwin_intel = client.query_by_tag(
        "#win-probability",
        agent_types=["Goku"],
        limit=3
    )

    return past_outcomes + pwin_intel


def loki_batch_pipeline_analysis(client: AgentCommonsClient, prospects: list):
    """
    Batch analyze multiple prospects in pipeline.
    """
    print(f"\n[Loki] Batch analysis for {len(prospects)} pipeline prospects...")

    # Batch query: qualification, GTM, solution patterns
    topics = [
        f"Prospect qualification for {p['industry']}" for p in prospects
    ] + [
        "Sales pipeline stage progression",
        "Go-to-market strategy effectiveness",
        "Proposal win factors"
    ]

    batch_results = client.query_batch(topics[:10], limit=3)

    for topic, memories in batch_results.items():
        print(f"\n  {topic}:")
        for mem in memories:
            print(f"    - [{mem.get('relevance_score', 0):.2f}] {mem['content'][:80]}")

    return batch_results


def loki_deal_stage_progression(client: AgentCommonsClient, prospect_name: str, current_stage: str, target_stage: str):
    """
    Query institutional memory for stage progression guidance.
    """
    print(f"\n[Loki] Stage progression: {prospect_name} ({current_stage} → {target_stage})")

    # Query for stage transition patterns
    transition_pattern = client.query_by_similarity(
        f"Moving sales prospect from {current_stage} to {target_stage}",
        agent_types=["Loki"],
        limit=5
    )

    print(f"  Found {len(transition_pattern)} transition patterns:")
    for mem in transition_pattern:
        print(f"    - [{mem['relevance_score']:.2f}] {mem['content'][:100]}")

    return transition_pattern


if __name__ == "__main__":
    # Simulate Loki workflow
    client = loki_startup()

    # Prospect qualification
    qual_intel = loki_prospect_qualification(client, "Acme Corp", "Technology")

    # GTT strategy
    gtt = loki_gtt_strategy(client, "Acme Corp", "$500K")

    # Proposal discovery
    discovery = loki_proposal_discovery(client, "Acme Corp", "Cloud infrastructure optimization")

    # Win probability
    pwin = loki_win_probability_assessment(client, "Acme Corp")

    # Stage progression
    stage = loki_deal_stage_progression(client, "Acme Corp", "Qualification", "Proposal")

    # Batch analysis
    prospects = [
        {"name": "Prospect A", "industry": "Finance"},
        {"name": "Prospect B", "industry": "Defense"},
    ]
    batch = loki_batch_pipeline_analysis(client, prospects)

    # Cache stats
    print(f"\n[Loki] Cache stats: {client.cache_stats()}")
