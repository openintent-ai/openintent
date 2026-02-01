# Changelog

All notable changes to the OpenIntent SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-01

### Added

- Initial release of OpenIntent SDK for Python
- Synchronous client (`OpenIntentClient`)
- Asynchronous client (`AsyncOpenIntentClient`) with full feature parity
- Full Intent CRUD operations (RFC-0001)
- State management with optimistic concurrency control via `If-Match` headers
- Append-only event logging for audit trails (RFC-0002)
- Lease-based scope ownership with acquire, renew, and release (RFC-0003)
- Governance endpoints: arbitration requests and decisions (RFC-0004)
- File attachments with base64 encoding (RFC-0005)
- Webhook subscriptions for real-time updates (RFC-0006)
- Cost tracking with summaries by agent and type (RFC-0009)
- Retry policies and failure recording (RFC-0010)
- Portfolio management for grouping related intents
- Agent assignment and management
- Protocol discovery via `.well-known/openintent.json`
- Context manager support for automatic lease cleanup
- Comprehensive input validation module (`validation.py`)
- Type-safe models using dataclasses
- OpenAI multi-agent coordination example
- Streaming with background intent updates example
- Authentication patterns example
- Basic usage example
- Unit tests for models and validation

### Models

- `Intent` - Core intent object with state, constraints, and versioning
- `IntentState` - Flexible key-value state container
- `IntentEvent` - Immutable audit log entry
- `IntentLease` - Scope ownership lease with expiration
- `ArbitrationRequest` - Governance arbitration request
- `Decision` - Governance decision record
- `Attachment` - File attachment with metadata
- `Subscription` - Webhook subscription configuration
- `CostRecord` - Cost tracking entry
- `CostSummary` - Aggregated cost statistics
- `RetryPolicy` - Retry configuration
- `Failure` - Failure record for retry tracking
- `Portfolio` - Intent grouping container
- `PortfolioIntent` - Portfolio membership with role and priority

### Validation Helpers

- `validate_required` - Check for required fields
- `validate_string_length` - Enforce string length limits
- `validate_positive_int` - Ensure positive integers
- `validate_non_negative` - Ensure non-negative numbers
- `validate_uuid` - UUID format validation
- `validate_url` - URL format validation
- `validate_scope` - Scope identifier validation
- `validate_agent_id` - Agent ID format validation
- `validate_intent_create` - Composite intent creation validator
- `validate_lease_acquire` - Composite lease acquisition validator
- `validate_cost_record` - Composite cost record validator
- `validate_subscription` - Composite subscription validator

### Exceptions

- `OpenIntentError` - Base exception for all SDK errors
- `ConflictError` - Version conflict (409)
- `NotFoundError` - Resource not found (404)
- `LeaseConflictError` - Lease collision (409)
- `ValidationError` - Request validation failure (400)
- `InputValidationError` - Client-side input validation (inherits from ValidationError)
