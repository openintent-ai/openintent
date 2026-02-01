#!/usr/bin/env python3
"""
OpenIntent SDK - Basic Usage Example

This example demonstrates the fundamental operations of the OpenIntent SDK.

Prerequisites:
    pip install openintent

Usage:
    export OPENINTENT_API_URL=http://localhost:5000
    export OPENINTENT_API_KEY=dev-user-key
    python basic_usage.py
"""

import os

from openintent import (
    ConflictError,
    EventType,
    IntentStatus,
    OpenIntentClient,
)


def main():
    # Configuration
    base_url = os.getenv("OPENINTENT_API_URL", "http://localhost:5000")
    api_key = os.getenv("OPENINTENT_API_KEY", "dev-user-key")

    # Initialize client
    with OpenIntentClient(
        base_url=base_url, api_key=api_key, agent_id="example-agent"
    ) as client:

        # 1. Discover protocol capabilities
        print("1. Discovering protocol...")
        try:
            discovery = client.discover()
            print(f"   Protocol version: {discovery.get('version', 'unknown')}")
        except Exception as e:
            print(f"   Discovery not available: {e}")

        # 2. Create an intent
        print("\n2. Creating intent...")
        intent = client.create_intent(
            title="Example Research Task",
            description="Demonstrate OpenIntent SDK capabilities",
            constraints=[
                "Must complete within reasonable time",
                "Log all significant activities",
            ],
            initial_state={
                "phase": "initialization",
                "progress": 0.0,
            },
        )
        print(f"   Created intent: {intent.id}")
        print(f"   Version: {intent.version}")
        print(f"   Status: {intent.status.value}")

        # 3. Update state with optimistic concurrency
        print("\n3. Updating state...")
        try:
            intent = client.update_state(
                intent.id,
                intent.version,
                {
                    "phase": "in_progress",
                    "progress": 0.25,
                    "current_step": "data_collection",
                },
            )
            print(f"   State updated, new version: {intent.version}")
        except ConflictError as e:
            print(f"   Conflict! Current version: {e.current_version}")

        # 4. Log events
        print("\n4. Logging events...")
        event = client.log_event(
            intent.id,
            EventType.COMMENT,
            {
                "message": "Starting data collection phase",
                "details": {"items_to_process": 100},
            },
        )
        print(f"   Event logged: {event.id}")

        # 5. Acquire and release lease
        print("\n5. Working with leases...")
        with client.lease(intent.id, "data-processing", duration_seconds=60) as lease:
            print(f"   Lease acquired: {lease.id}")
            print(f"   Scope: {lease.scope}")
            print(f"   Expires: {lease.expires_at}")

            # Simulate work
            intent = client.get_intent(intent.id)
            intent = client.update_state(intent.id, intent.version, {"progress": 0.5})
            print("   Work done, progress: 50%")
        print("   Lease released")

        # 6. List all leases
        print("\n6. Checking active leases...")
        leases = client.get_leases(intent.id)
        print(f"   Active leases: {len(leases)}")

        # 7. Get event history
        print("\n7. Retrieving event history...")
        events = client.get_events(intent.id, limit=10)
        print(f"   Found {len(events)} events:")
        for e in events:
            print(f"   - [{e.event_type.value}] {e.payload.get('message', 'N/A')[:50]}")

        # 8. Complete the intent
        print("\n8. Completing intent...")
        intent = client.get_intent(intent.id)
        intent = client.update_state(
            intent.id, intent.version, {"phase": "completed", "progress": 1.0}
        )
        intent = client.set_status(intent.id, intent.version, IntentStatus.COMPLETED)
        print(f"   Intent completed: {intent.status.value}")

        # 9. Final state
        print("\n9. Final state:")
        final_intent = client.get_intent(intent.id)
        for key, value in final_intent.state.to_dict().items():
            print(f"   {key}: {value}")

        print("\nDone!")


if __name__ == "__main__":
    main()
