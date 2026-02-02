# Changelog

All notable changes to the OpenIntent SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.5] - 2026-02-02

### Fixed

- **IntentStatus Enum**: Aligned SDK with protocol spec
  - Now uses: `draft`, `active`, `blocked`, `completed`, `abandoned`
  - Added missing `DRAFT` and `ABANDONED` statuses
  - Removed deprecated `CANCELLED` (use `ABANDONED` instead)
  - Fixes "ValueError: 'draft' is not a valid IntentStatus" when using SDK with servers

- **EventType Enum**: Aligned SDK with all server event types
  - Renamed `CREATED` → `INTENT_CREATED` (value: `intent_created`)
  - Renamed `STATE_UPDATED` → `STATE_PATCHED` (value: `state_patched`)
  - Added: `DEPENDENCY_ADDED`, `DEPENDENCY_REMOVED` (RFC-0002)
  - Added: `ATTACHMENT_ADDED` (RFC-0005)
  - Added: `PORTFOLIO_CREATED`, `ADDED_TO_PORTFOLIO`, `REMOVED_FROM_PORTFOLIO` (RFC-0007)
  - Added: `FAILURE_RECORDED` (RFC-0010)
  - Legacy aliases `CREATED` and `STATE_UPDATED` preserved for backward compatibility

- **LeaseStatus Enum**: Added missing `REVOKED` status

- **Intent Model**: 
  - Changed `constraints` from `list[str]` to `dict[str, Any]` to match server spec
  - Added `created_by` and `confidence` fields to match server response

## [0.4.4] - 2026-02-02

### Fixed

- **Intent Creation**: Client now sends `created_by` field (using `agent_id`) when creating intents
- **Server Compatibility**: Server now accepts optional `created_by` field, defaulting to API key
- **Demo Script**: Fixed 422 validation errors in `/try` demo by ensuring proper authentication

## [0.4.0] - 2026-02-01

### Added

- **Built-in OpenIntent Server** (`server/` module)
  - FastAPI-based server implementing all 8 RFCs
  - SQLite by default (zero-config), PostgreSQL support
  - CLI entry point: `openintent-server`
  - Module entry point: `python -m openintent.server`
  - Programmatic access via `OpenIntentServer` class

- **Server Features**
  - Complete Intent CRUD with optimistic concurrency
  - Append-only event log
  - Agent assignment and lease management
  - Portfolio management with memberships
  - Attachments, cost tracking, retry policies
  - SSE subscriptions for real-time updates
  - Governance (arbitration and decisions)
  - OpenAPI documentation at `/docs`
  - Protocol discovery at `/.well-known/openintent.json`

- **Server Configuration**
  - `ServerConfig` dataclass for all settings
  - Environment variable support
  - Configurable API keys, CORS, logging

- **New Installation Options**
  - `pip install openintent[server]` - Server dependencies
  - `pip install openintent[all]` - Everything included

### Changed

- Updated description to "Python SDK and Server for the OpenIntent Coordination Protocol"
- Development status upgraded to Beta
- Version bump to 0.4.0

## [0.3.0] - 2026-02-01

### Added

- **High-Level Agent Abstractions** (`agents.py` module)
  - `@Agent` decorator for minimal-boilerplate agent creation
  - `Coordinator` class for portfolio-based multi-agent orchestration
  - `Worker` class for ultra-minimal single-purpose agents
  - `BaseAgent` class for custom agent implementations

- **Declarative Event Handlers**
  - `@on_assignment` - Called when agent is assigned to an intent
  - `@on_complete` - Called when an intent completes
  - `@on_lease_available(scope)` - Called when a scope lease becomes available
  - `@on_state_change(keys)` - Called when intent state changes
  - `@on_event(type)` - Called for specific event types
  - `@on_all_complete` - Called when all portfolio intents complete

- **Portfolio DSL**
  - `PortfolioSpec` - Declarative portfolio definition
  - `IntentSpec` - Intent specification with `depends_on` for dependencies
  - Automatic topological sorting of intent dependencies
  - Automatic intent creation and agent assignment

- **Agent Configuration**
  - `AgentConfig` dataclass for configuration
  - Auto-subscribe to SSE events
  - Auto-patch state from handler return values
  - Auto-complete intents after successful processing

- **New Examples**
  - `examples/agents/research_agent.py` - Decorator-based agent
  - `examples/agents/coordinator.py` - Portfolio orchestration
  - `examples/agents/worker.py` - Minimal worker pattern
  - `examples/agents/README.md` - Comprehensive documentation

### Changed

- Version bump to 0.3.0

## [0.2.0] - 2026-02-01

### Added

- **Real-Time SSE Streaming** (`streaming.py` module)
  - `SSEStream` - Iterator-based SSE event streaming
  - `SSESubscription` - Background thread event processing
  - `EventQueue` - Queue-based non-blocking event consumption
  - `SSEEvent` and `SSEEventType` models
  - Three subscription levels: intent, portfolio, agent

- **Provider Adapters** (`adapters/` directory)
  - `OpenAIAdapter` - Wraps OpenAI clients with automatic event logging
  - `AnthropicAdapter` - Wraps Anthropic clients with automatic event logging
  - `AdapterConfig` - Configuration for adapter behavior
  - Automatic LLM request, tool call, and stream logging

- **LLM Integration Events**
  - `TOOL_CALL_STARTED`, `TOOL_CALL_COMPLETED`, `TOOL_CALL_FAILED`
  - `LLM_REQUEST_STARTED`, `LLM_REQUEST_COMPLETED`, `LLM_REQUEST_FAILED`
  - `STREAM_STARTED`, `STREAM_CHUNK`, `STREAM_COMPLETED`, `STREAM_CANCELLED`

- **New Models**
  - `ToolCallPayload` - Tool call event data
  - `LLMRequestPayload` - LLM request event data
  - `StreamState`, `StreamStatus` - Streaming state tracking

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
