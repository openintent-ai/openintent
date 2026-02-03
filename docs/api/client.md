# Client API Reference

## OpenIntentClient

The synchronous client for interacting with an OpenIntent server.

::: openintent.client.OpenIntentClient
    options:
      show_source: false
      members:
        - __init__
        - create_intent
        - get_intent
        - list_intents
        - patch_state
        - update_state
        - complete_intent
        - abandon_intent
        - log_event
        - get_events
        - acquire_lease
        - renew_lease
        - release_lease
        - list_leases
        - request_arbitration
        - record_decision
        - subscribe
        - log_llm_request_started
        - log_llm_request_completed
        - log_llm_request_failed
        - log_tool_call_started
        - log_tool_call_completed
        - log_tool_call_failed

## AsyncOpenIntentClient

The asynchronous client for async applications.

::: openintent.client.AsyncOpenIntentClient
    options:
      show_source: false
      members:
        - __init__
        - create_intent
        - get_intent
        - patch_state
        - log_event
        - subscribe
