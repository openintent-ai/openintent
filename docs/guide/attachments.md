---
title: Attachments
---

# Attachments

Attachments allow agents and users to associate files, documents, and binary data with intents. Defined in [RFC-0005](../rfcs/0005-attachments.md).

## Adding Attachments

```python
# Attach a file to an intent
attachment = client.add_attachment(
    intent_id=intent.id,
    filename="analysis_report.pdf",
    content_type="application/pdf",
    data=open("report.pdf", "rb").read(),
    metadata={"author": "research-agent", "version": "1.0"}
)

print(f"Attachment {attachment.id}: {attachment.filename}")
```

### Supported Content Types

Attachments accept any content type. Common examples:

| Content Type | Use Case |
|-------------|----------|
| `application/pdf` | Reports, documents |
| `application/json` | Structured data, configs |
| `text/plain` | Logs, notes |
| `text/csv` | Data exports |
| `image/png` | Charts, screenshots |

## Listing Attachments

```python
# List all attachments for an intent
attachments = client.list_attachments(intent.id)

for att in attachments:
    print(f"{att.filename} ({att.content_type}, {att.size_bytes} bytes)")
```

## Retrieving Attachment Data

```python
# Get attachment metadata
attachment = client.get_attachment(intent.id, attachment_id)

# Download the content
data = client.download_attachment(intent.id, attachment_id)

with open(f"downloaded_{attachment.filename}", "wb") as f:
    f.write(data)
```

## Using Attachments in Agents

```python
from openintent.agents import Agent, on_assignment

@Agent("report-generator")
class ReportAgent:

    @on_assignment
    async def handle(self, intent):
        # Generate a report
        report = generate_report(intent.state)

        # Attach it to the intent
        await self.client.add_attachment(
            intent_id=intent.id,
            filename="report.pdf",
            content_type="application/pdf",
            data=report,
            metadata={"generated_by": "report-generator"}
        )

        return {"report_generated": True}
```

## Attachment Metadata

Every attachment carries metadata for discoverability:

```python
attachment = client.add_attachment(
    intent_id=intent.id,
    filename="results.json",
    content_type="application/json",
    data=json.dumps(results).encode(),
    metadata={
        "source": "analysis-pipeline",
        "row_count": len(results),
        "schema_version": "2.0"
    }
)
```

!!! tip "Integration with Agent Memory"
    Attachments integrate with [Agent Memory](memory.md) (RFC-0015). Agents can reference attachment IDs in memory entries for cross-task context.

## Next Steps

- [Events](events.md) — Attachment events are logged automatically
- [Subscriptions & Streaming](subscriptions.md) — Get notified when attachments are added
