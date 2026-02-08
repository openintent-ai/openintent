# RFC-0004: Intent Portfolios v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md), [RFC-0002 (Intent Graphs)](./0002-intent-graphs.md)

---

## Abstract

This RFC defines Intent Portfolios — collections of related intents that enable multi-intent coordination, aggregate status tracking, and shared governance policies for complex workflows spanning multiple goals.

## Motivation

Real-world workflows often involve multiple intents that must be coordinated together:

- **Travel planning:** Flight, hotel, and activity intents share constraints and deadlines
- **Product launches:** Marketing, development, and QA intents need synchronized completion
- **Research projects:** Literature review, data collection, and analysis intents depend on each other
- **Complex orders:** Multi-item requests where partial completion is tracked

Portfolios provide a container for grouping these intents with shared policies and aggregate visibility.

## Data Model

### Portfolio Object

```json
{
  "id": "uuid",
  "name": "Paris Trip 2024",
  "description": "Complete planning for Paris vacation",
  "created_by": "user@example.com",
  "status": "active | completed | abandoned",
  "governance_policy": {
    "require_all_completed": true,
    "allow_partial_completion": false,
    "auto_complete_threshold": null,
    "shared_constraints": { "budget": 5000 }
  },
  "aggregate_status": {
    "total": 5,
    "by_status": {
      "completed": 3,
      "active": 1,
      "blocked": 1
    },
    "completion_percentage": 60
  }
}
```

## Membership Roles

**primary**
:   The main intent that defines the portfolio's overall goal. A portfolio should have exactly one primary.

**member**
:   Standard member intent that contributes to the portfolio's completion.

**dependency**
:   An intent that must complete before others can proceed. Used for sequencing.

## Governance Policies

Portfolios can define governance policies that apply to all member intents:

- `require_all_completed` — Portfolio only completes when all intents are completed
- `allow_partial_completion` — Portfolio can succeed with some failed intents
- `auto_complete_threshold` — Percentage of completed intents to auto-complete portfolio
- `shared_constraints` — Constraints inherited by all member intents

## Endpoints

### Portfolio CRUD

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/portfolios` | Create a new portfolio |
| `GET` | `/v1/portfolios` | List portfolios (with optional filters) |
| `GET` | `/v1/portfolios/{id}` | Get portfolio with aggregate status |
| `PATCH` | `/v1/portfolios/{id}/status` | Update portfolio status |

### Membership Management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/portfolios/{id}/intents` | Add intent to portfolio |
| `GET` | `/v1/portfolios/{id}/intents` | List portfolio intents with status |
| `DELETE` | `/v1/portfolios/{id}/intents/{intentId}` | Remove intent from portfolio |
| `GET` | `/v1/intents/{id}/portfolios` | List portfolios containing an intent |

## Use Cases

### Multi-Agent Coordination

A portfolio allows multiple agents to work on related intents while maintaining visibility of overall progress. Agents can check the portfolio's aggregate status to determine when to proceed with dependent work.

### Parallel Workstreams

For complex requests that decompose into parallel tasks, portfolios track which branches are complete and provide a single point for monitoring overall completion percentage.

### Shared Governance

When multiple intents share the same constraints (e.g., budget limits, deadlines), the portfolio's governance policy can enforce these constraints across all members.

## Example: Travel Planning Portfolio

```bash
# Create a portfolio for a trip
curl -X POST http://localhost:8000/api/v1/portfolios \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-user-key" \
  -d '{
    "name": "Paris Trip 2024",
    "description": "Complete planning for Paris vacation",
    "created_by": "user@example.com",
    "governance_policy": {
      "require_all_completed": true,
      "shared_constraints": { "budget": 5000 }
    }
  }'

# Add intents to the portfolio
curl -X POST http://localhost:8000/api/v1/portfolios/{id}/intents \
  -H "X-API-Key: dev-user-key" \
  -d '{"intent_id": "flight-intent-id", "role": "member", "priority": 100}'

curl -X POST http://localhost:8000/api/v1/portfolios/{id}/intents \
  -H "X-API-Key: dev-user-key" \
  -d '{"intent_id": "hotel-intent-id", "role": "member", "priority": 90}'

# Check aggregate progress
curl http://localhost:8000/api/v1/portfolios/{id} \
  -H "X-API-Key: dev-user-key"
# Returns portfolio with aggregate_status showing completion percentage
```
