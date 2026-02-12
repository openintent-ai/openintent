#!/usr/bin/env python3
"""
Incident Response Example - Intent Graphs (RFC-0002)

This example demonstrates how to use Intent Graphs for coordinating
a production incident response across multiple agents.

The graph structure:
    "Resolve Production Outage" (parent)
    ├── "Diagnose Root Cause"
    ├── "Customer Communication" (parallel, no dependencies)
    ├── "Implement Hotfix" (depends_on: Diagnose)
    ├── "Deploy Fix" (depends_on: Diagnose, Implement)
    ├── "Verify Resolution" (depends_on: Deploy)
    └── "Post-Mortem" (depends_on: ALL above)

This showcases:
- Parent-child intent hierarchies
- Parallel execution (Communication runs independently)
- Sequential dependencies (can't fix what you haven't diagnosed)
- Multi-dependency gates (Deploy needs both diagnosis AND fix ready)
- Aggregate completion tracking
"""

from openintent import IntentStatus, OpenIntentClient


def create_incident_response_graph_sync(client: OpenIntentClient, incident_title: str) -> dict:
    """
    Create an incident response intent graph using the synchronous client.

    Returns dict with all created intents for reference.
    """
    parent = client.create_intent(
        title=incident_title,
        description="Critical: API returning 500 errors. Multiple customers affected.",
    )
    print(f"Created parent intent: {parent.id} - {parent.title}")

    diagnose = client.create_child_intent(
        parent_id=parent.id,
        title="Diagnose Root Cause",
        description="Identify what caused the outage",
    )
    print(f"  Created child: {diagnose.id} - {diagnose.title}")

    communicate = client.create_child_intent(
        parent_id=parent.id,
        title="Customer Communication",
        description="Update status page and notify affected customers",
    )
    print(f"  Created child: {communicate.id} - {communicate.title} (parallel)")

    hotfix = client.create_child_intent(
        parent_id=parent.id,
        title="Implement Hotfix",
        description="Write and test the fix",
        depends_on=[diagnose.id],
    )
    print(f"  Created child: {hotfix.id} - {hotfix.title} (depends on: Diagnose)")

    deploy = client.create_child_intent(
        parent_id=parent.id,
        title="Deploy Fix",
        description="Deploy the hotfix to production",
        depends_on=[diagnose.id, hotfix.id],
    )
    print(f"  Created child: {deploy.id} - {deploy.title} (depends on: Diagnose, Implement)")

    verify = client.create_child_intent(
        parent_id=parent.id,
        title="Verify Resolution",
        description="Confirm the fix resolved the issue",
        depends_on=[deploy.id],
    )
    print(f"  Created child: {verify.id} - {verify.title} (depends on: Deploy)")

    postmortem = client.create_child_intent(
        parent_id=parent.id,
        title="Post-Mortem",
        description="Document incident timeline and lessons learned",
        depends_on=[diagnose.id, communicate.id, hotfix.id, deploy.id, verify.id],
    )
    print(f"  Created child: {postmortem.id} - {postmortem.title} (depends on: ALL)")

    return {
        "parent": parent,
        "diagnose": diagnose,
        "communicate": communicate,
        "hotfix": hotfix,
        "deploy": deploy,
        "verify": verify,
        "postmortem": postmortem,
    }


def show_graph_status(client: OpenIntentClient, parent_id: str):
    """Display the current state of the intent graph."""
    graph = client.get_intent_graph(parent_id)

    print("\n" + "=" * 60)
    print("INCIDENT RESPONSE GRAPH STATUS")
    print("=" * 60)

    agg = graph.get("aggregate_status", {})
    print(f"\nTotal intents: {agg.get('total', 0)}")
    print(f"Completion: {agg.get('completion_percentage', 0)}%")
    print(f"By status: {agg.get('by_status', {})}")

    print("\nNodes:")
    for node in graph.get("nodes", []):
        deps = node.get("depends_on", [])
        dep_str = f" (deps: {len(deps)})" if deps else ""
        print(f"  [{node['status']:10}] {node['title']}{dep_str}")

    print("\nReady intents (no blocking deps):")
    ready = client.get_ready_intents(parent_id)
    for r in ready:
        print(f"  - {r.title}")

    print("\nBlocked intents (waiting on deps):")
    blocked = client.get_blocked_intents(parent_id)
    for b in blocked:
        print(f"  - {b.title}")


def simulate_incident_resolution(client: OpenIntentClient, intents: dict):
    """
    Simulate resolving the incident by completing tasks in dependency order.
    """
    print("\n" + "=" * 60)
    print("SIMULATING INCIDENT RESOLUTION")
    print("=" * 60)

    diagnose = intents["diagnose"]
    print("\nStep 1: Diagnosing root cause...")
    diagnose = client.update_state(
        diagnose.id,
        diagnose.version,
        {
            "root_cause": "Database connection pool exhausted",
            "affected_services": ["api-gateway", "user-service"],
        },
    )
    diagnose = client.set_status(diagnose.id, diagnose.version, IntentStatus.COMPLETED)
    print(f"  Completed: {diagnose.title}")

    communicate = intents["communicate"]
    print("\nStep 2: Customer communication (parallel)...")
    communicate = client.update_state(
        communicate.id,
        communicate.version,
        {
            "status_page_updated": True,
            "customers_notified": 150,
        },
    )
    communicate = client.set_status(communicate.id, communicate.version, IntentStatus.COMPLETED)
    print(f"  Completed: {communicate.title}")

    hotfix = intents["hotfix"]
    print("\nStep 3: Implementing hotfix...")
    hotfix = client.get_intent(hotfix.id)
    hotfix = client.update_state(
        hotfix.id,
        hotfix.version,
        {
            "fix_description": "Increased connection pool size and added retry logic",
            "tests_passed": True,
        },
    )
    hotfix = client.set_status(hotfix.id, hotfix.version, IntentStatus.COMPLETED)
    print(f"  Completed: {hotfix.title}")

    deploy = intents["deploy"]
    print("\nStep 4: Deploying fix...")
    deploy = client.get_intent(deploy.id)
    deploy = client.update_state(
        deploy.id,
        deploy.version,
        {
            "deployment_id": "deploy-20240201-001",
            "rollback_available": True,
        },
    )
    deploy = client.set_status(deploy.id, deploy.version, IntentStatus.COMPLETED)
    print(f"  Completed: {deploy.title}")

    verify = intents["verify"]
    print("\nStep 5: Verifying resolution...")
    verify = client.get_intent(verify.id)
    verify = client.update_state(
        verify.id,
        verify.version,
        {
            "error_rate": "0.01%",
            "latency_p99": "45ms",
            "verified_by": "on-call-engineer",
        },
    )
    verify = client.set_status(verify.id, verify.version, IntentStatus.COMPLETED)
    print(f"  Completed: {verify.title}")

    postmortem = intents["postmortem"]
    print("\nStep 6: Writing post-mortem...")
    postmortem = client.get_intent(postmortem.id)
    postmortem = client.update_state(
        postmortem.id,
        postmortem.version,
        {
            "incident_start": "2024-02-01T14:30:00Z",
            "incident_end": "2024-02-01T15:45:00Z",
            "duration_minutes": 75,
            "action_items": [
                "Add connection pool metrics to dashboard",
                "Set up alerting for pool exhaustion",
                "Review retry logic in all services",
            ],
        },
    )
    postmortem = client.set_status(postmortem.id, postmortem.version, IntentStatus.COMPLETED)
    print(f"  Completed: {postmortem.title}")

    parent = intents["parent"]
    print("\nStep 7: Marking parent complete...")
    parent = client.get_intent(parent.id)
    parent = client.set_status(parent.id, parent.version, IntentStatus.COMPLETED)
    print(f"  Completed: {parent.title}")


def main():
    """Run the incident response example."""
    client = OpenIntentClient(
        base_url="http://localhost:8000",
        api_key="incident-response-demo",
        agent_id="incident-coordinator",
    )

    print("=" * 60)
    print("INCIDENT RESPONSE - INTENT GRAPHS EXAMPLE")
    print("=" * 60)
    print()

    intents = create_incident_response_graph_sync(
        client, "Resolve Production Outage: API 500 Errors"
    )

    show_graph_status(client, intents["parent"].id)

    simulate_incident_resolution(client, intents)

    show_graph_status(client, intents["parent"].id)

    print("\n" + "=" * 60)
    print("INCIDENT RESOLVED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
