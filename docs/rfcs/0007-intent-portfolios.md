# RFC-0007: Intent Portfolios v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md), [RFC-0003 (Governance)](./0003-agent-leasing.md)

---

## Abstract

This RFC formalizes Intent Portfolios as organizational containers for multi-intent coordination. While RFC-0004 introduced the basic portfolio concept, this RFC clarifies the portfolio's role as an organizational boundary with no execution semantics — distinct from Plans (RFC-0012) which handle execution strategy.

## Motivation

As the protocol evolved, the relationship between Portfolios, Intent Graphs, and Plans needed clarification:

- **Portfolios** group related intents for visibility and shared governance
- **Intent Graphs** (RFC-0002) express structural dependencies between intents
- **Plans** (RFC-0012) define execution strategy with conditionals, checkpoints, and rollback

A portfolio is analogous to a project folder — it organizes work but doesn't dictate how work is executed.

## Clarified Semantics

### What Portfolios Do

- Group related intents under a single namespace
- Provide aggregate status across all member intents
- Apply shared governance policies (budgets, deadlines, constraints)
- Enable portfolio-level subscriptions (RFC-0006)
- Scope coordinator leases (RFC-0013) to a set of related intents

### What Portfolios Do NOT Do

- Define execution order (that's Intent Graphs / Plans)
- Manage task decomposition (that's RFC-0012)
- Control agent assignment (that's leasing, RFC-0003)

## Portfolio as Namespace

Portfolios serve as namespaces for organizing work:

```json
{
  "id": "portfolio_01HABC",
  "name": "Q1 Product Launch",
  "namespace": "product-launch-q1",
  "intents": [
    { "intent_id": "intent_01", "role": "primary" },
    { "intent_id": "intent_02", "role": "member" },
    { "intent_id": "intent_03", "role": "member" }
  ],
  "governance": {
    "budget_limit_cents": 100000,
    "deadline": "2026-03-31T00:00:00Z",
    "require_all_completed": true
  }
}
```

## Cross-RFC Interactions

| RFC | Interaction |
|-----|------------|
| RFC-0001 (Intents) | Portfolios contain intents |
| RFC-0002 (Graphs) | Intents within a portfolio can form graphs |
| RFC-0006 (Subscriptions) | Subscribe to all events within a portfolio |
| RFC-0009 (Costs) | Aggregate cost tracking across portfolio intents |
| RFC-0012 (Planning) | Plans can scope to portfolio intents |
| RFC-0013 (Coordinators) | Coordinator lease can scope to a portfolio |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/portfolios` | Create a new portfolio |
| `GET` | `/v1/portfolios` | List portfolios |
| `GET` | `/v1/portfolios/{id}` | Get portfolio with aggregate status |
| `PATCH` | `/v1/portfolios/{id}` | Update portfolio metadata |
| `POST` | `/v1/portfolios/{id}/intents` | Add intent to portfolio |
| `DELETE` | `/v1/portfolios/{id}/intents/{intentId}` | Remove intent |
| `GET` | `/v1/portfolios/{id}/costs` | Aggregate costs across portfolio |
