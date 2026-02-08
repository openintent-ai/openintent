# Leasing & Concurrency

Agents acquire leases before working on intents. Leases prevent conflicts and enable automatic recovery.

## Acquiring a Lease (Imperative)

```python
from openintent import OpenIntentClient

client = OpenIntentClient(
    base_url="http://localhost:8000",
    agent_id="worker-1"
)

intent = client.get_intent(intent_id)

# Acquire a lease (exclusive access for 120 seconds)
lease = client.acquire_lease(
    intent_id=intent.id,
    ttl_seconds=120
)

print(f"Lease ID: {lease.id}")
print(f"Expires: {lease.expires_at}")

# Do work while holding the lease...
client.patch_state(intent.id, {"status": "in_progress"})

# Renew if you need more time
client.renew_lease(lease.id, ttl_seconds=120)

# Release when done
client.release_lease(lease.id)
```

## Lease Contention

When two agents try to lease the same intent, the second gets a conflict:

```python
# Agent A acquires the lease
lease_a = client_a.acquire_lease(intent_id=intent.id, ttl_seconds=60)

# Agent B tries — gets rejected
try:
    lease_b = client_b.acquire_lease(intent_id=intent.id, ttl_seconds=60)
except ConflictError as e:
    print(f"Intent already leased by {e.current_holder}")
    # Wait or pick another intent
```

## Automatic Heartbeats with @Agent

The `@Agent` decorator handles leasing automatically:

```python
from openintent.agents import Agent, on_assignment

@Agent("reliable-worker", auto_heartbeat=True)
class ReliableWorker:

    @on_assignment
    async def handle(self, intent):
        # Lease is acquired automatically before this runs
        # Heartbeat keeps the lease alive during long work
        await self.do_long_task(intent)
        return {"status": "done"}
        # Lease is released automatically after return
```

## Optimistic Concurrency on State

```python
# Fetch current version
intent = client.get_intent(intent_id)

# Update with version check
try:
    client.patch_state(
        intent.id,
        {"progress": 50},
        expected_version=intent.version
    )
except ConflictError:
    # Another agent modified the intent
    intent = client.get_intent(intent_id)  # Re-fetch
    client.patch_state(
        intent.id,
        {"progress": 50},
        expected_version=intent.version  # Retry with fresh version
    )
```

## Coordinator Leases

Coordinators also use leases to prevent split-brain scenarios:

```python
# Only one coordinator can manage a portfolio at a time
coord_lease = client.acquire_coordinator_lease(
    portfolio_id=portfolio.id,
    ttl_seconds=600
)

# If the coordinator crashes, the lease expires and
# another coordinator can take over (failover)
```

## YAML Workflow with Retry on Lease Failure

```yaml
openintent: "1.0"
info:
  name: "Resilient Pipeline"

workflow:
  fetch:
    title: "Fetch Data"
    assign: fetcher
    retry:
      max_attempts: 3
      backoff: exponential
      base_delay_seconds: 2

  process:
    title: "Process Data"
    assign: processor
    depends_on: [fetch]
    retry:
      max_attempts: 5
      backoff: linear
      base_delay_seconds: 1
```
