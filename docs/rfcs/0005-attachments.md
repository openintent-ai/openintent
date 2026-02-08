# RFC-0005: Attachments & Multi-modality v1.0

**Status:** Proposed  
**Created:** 2026-02-01  
**Authors:** OpenIntent Contributors  
**Requires:** [RFC-0001 (Intents)](./0001-intent-objects.md)

---

## Abstract

This RFC defines support for file attachments on intents, enabling multi-modal workflows involving images, audio, video, documents, and other binary content.

## Motivation

Modern AI agents frequently work with multi-modal content:

- **Vision tasks:** Image analysis, OCR, visual QA
- **Audio processing:** Transcription, voice commands, music analysis
- **Document workflows:** PDF parsing, contract review, data extraction
- **Video understanding:** Content moderation, scene detection, summarization

The protocol must provide a standard mechanism for associating binary content with intents so that agents can exchange rich media as part of structured coordination.

## Data Model

### Attachment Object

```json
{
  "id": "uuid",
  "intent_id": "uuid",
  "filename": "document.pdf",
  "mime_type": "application/pdf",
  "size": 1048576,
  "storage_url": "https://storage.example.com/files/abc123",
  "metadata": {
    "width": null,
    "height": null,
    "duration": null,
    "pages": 24
  },
  "uploaded_by": "agent-id",
  "created_at": "ISO 8601"
}
```

### Supported Metadata

Metadata fields are content-type specific:

| Field | Applies To | Description |
|-------|-----------|-------------|
| `width` | Images, Video | Width in pixels |
| `height` | Images, Video | Height in pixels |
| `duration` | Audio, Video | Duration in seconds |
| `pages` | Documents | Number of pages |
| `encoding` | Audio | Audio encoding format |
| `frame_rate` | Video | Frames per second |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/intents/{id}/attachments` | Add attachment |
| `GET` | `/v1/intents/{id}/attachments` | List attachments |
| `DELETE` | `/v1/intents/{id}/attachments/{attachmentId}` | Remove attachment |

## Example: Image Analysis Workflow

```bash
# Upload an attachment reference
curl -X POST http://localhost:8000/api/v1/intents/{id}/attachments \
  -H "X-API-Key: dev-user-key" \
  -d '{
    "filename": "receipt.jpg",
    "mime_type": "image/jpeg",
    "size": 245000,
    "storage_url": "https://storage.example.com/receipts/r123.jpg",
    "metadata": { "width": 1920, "height": 1080 }
  }'
```

## Storage Considerations

This RFC defines the attachment *metadata* model only. The actual file storage mechanism (S3, GCS, local filesystem, etc.) is left to the implementation. The `storage_url` field provides the indirection needed to support any storage backend.

## Integration with Other RFCs

- **RFC-0015 (Agent Memory):** Memory entries can reference attachments for rich context
- **RFC-0008 (LLM Integration):** Adapters can include attachment content in LLM prompts for multi-modal inference
