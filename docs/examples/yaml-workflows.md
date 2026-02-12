# YAML Workflow Specification

Declarative multi-agent workflows covering all 20 RFCs — dependencies, permissions, retry, cost, memory, triggers, planning, and governance.

## Minimal Workflow

```yaml
openintent: "1.0"
info:
  name: "Hello World"

workflow:
  greet:
    title: "Say Hello"
    assign: greeter
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("hello.yaml")
wf.run()
```

## Sequential Pipeline

```yaml
openintent: "1.0"
info:
  name: "ETL Pipeline"

workflow:
  extract:
    title: "Extract Data"
    assign: extractor
    initial_state:
      source: "s3://data/raw"

  transform:
    title: "Transform Data"
    assign: transformer
    depends_on: [extract]
    constraints:
      - "Normalize dates to ISO 8601"
      - "Remove duplicates"

  load:
    title: "Load to Warehouse"
    assign: loader
    depends_on: [transform]
```

## Parallel Fan-Out

```yaml
openintent: "1.0"
info:
  name: "Multi-Source Research"

workflow:
  web_search:
    title: "Web Search"
    assign: web-researcher

  paper_search:
    title: "Academic Papers"
    assign: paper-researcher

  patent_search:
    title: "Patent Search"
    assign: patent-researcher

  synthesize:
    title: "Synthesize Findings"
    assign: synthesizer
    depends_on: [web_search, paper_search, patent_search]
```

## Full-Featured Workflow

Combining permissions, coordinator, retry, cost, memory, triggers, planning, and agents:

```yaml
openintent: "1.0"
info:
  name: "Compliance Review Pipeline"
  version: "2.0"

permissions:
  policy: restricted
  default: read
  allow:
    - agent: compliance-team
      actions: [read, write, approve]
    - agent: legal-team
      actions: [read, approve]
    - agent: engineering
      actions: [read, write]
  delegate:
    enabled: true
    max_depth: 2

coordinator:
  id: compliance-lead
  strategy: sequential
  guardrails:
    - type: budget
      max_cost_usd: 100.0
    - type: timeout
      max_seconds: 7200
    - type: approval
      require_for: [final_sign_off]
      min_approvals: 2

plan:
  strategy: hierarchical
  max_depth: 3

memory:
  default_scope: episodic
  max_entries: 1000
  ttl_seconds: 2592000  # 30 days

agents:
  - id: doc-scanner
    role_id: scanner
    capacity: 10
    auto_heartbeat: true
  - id: risk-assessor
    role_id: assessor
    capacity: 5
    auto_heartbeat: true

tools:
  - name: document_ocr
    description: "Extract text from scanned documents"
  - name: risk_model
    description: "Run compliance risk model"

triggers:
  - name: new_document
    type: webhook
    payload_transform:
      title: "Review: {{ payload.document_name }}"
      assign: doc-scanner
  - name: weekly_summary
    type: schedule
    schedule: "0 9 * * 1"
    intent_template:
      title: "Weekly Compliance Summary"
      assign: compliance-lead

workflow:
  scan_documents:
    title: "Scan & OCR Documents"
    assign: scanner
    tools: [document_ocr]
    retry:
      max_attempts: 3
      backoff: exponential
      base_delay_seconds: 5

  risk_assessment:
    title: "Risk Assessment"
    assign: assessor
    depends_on: [scan_documents]
    tools: [risk_model]
    cost:
      budget_usd: 20.0
    memory:
      scope: episodic
      tags: [risk, assessment]

  legal_review:
    title: "Legal Review"
    assign: legal-team
    depends_on: [risk_assessment]

  remediation:
    title: "Remediation Plan"
    assign: engineering
    depends_on: [legal_review]
    plan:
      tasks:
        - title: "Identify gaps"
        - title: "Create fix plan"
          depends_on: ["Identify gaps"]
        - title: "Implement fixes"
          depends_on: ["Create fix plan"]

  final_sign_off:
    title: "Final Approval"
    assign: [compliance-team, legal-team]
    depends_on: [remediation]
```

```python
from openintent.workflow import load_workflow

wf = load_workflow("compliance_review.yaml")

# Inspect before running
print(f"Workflow: {wf.info.name}")
print(f"Steps: {len(wf.workflow)}")
print(f"Triggers: {len(wf.triggers)}")
print(f"Tools: {len(wf.tools)}")

wf.run()
```

## Unified Permissions Shorthand

The `permissions` field supports shorthand forms:

```yaml
# Open access
permissions: open

# Private (creator only)
permissions: private

# Allow list
permissions: [agent-a, agent-b, agent-c]

# Full object form (shown above)
permissions:
  policy: restricted
  default: read
  allow:
    - agent: agent-a
      actions: [read, write]
```

## Loading and Validating Workflows

```python
from openintent.workflow import load_workflow, validate_workflow

# Validate without running
errors = validate_workflow("my_workflow.yaml")
if errors:
    for err in errors:
        print(f"Validation error: {err}")
else:
    wf = load_workflow("my_workflow.yaml")
    wf.run()
```
