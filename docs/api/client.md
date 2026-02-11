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
        - create_child_intent
        - update_state
        - set_status
        - log_event
        - get_events
        - acquire_lease
        - release_lease
        - get_leases
        - renew_lease
        - lease
        - request_arbitration
        - record_decision
        - get_decisions
        - assign_agent
        - unassign_agent
        - create_portfolio
        - get_portfolio
        - list_portfolios
        - update_portfolio_status
        - add_intent_to_portfolio
        - remove_intent_from_portfolio
        - get_portfolio_intents
        - subscribe
        - log_llm_request_started
        - log_llm_request_completed
        - log_llm_request_failed
        - log_tool_call_started
        - log_tool_call_completed
        - log_tool_call_failed
        - invoke_tool
        - discover

## AsyncOpenIntentClient

The asynchronous client for async applications, with full RFC 0012-0017 support.

::: openintent.client.AsyncOpenIntentClient
    options:
      show_source: false
      members:
        - __init__
        - create_intent
        - get_intent
        - update_state
        - log_event
        - subscribe
        - create_task
        - get_task
        - list_tasks
        - update_task
        - create_plan
        - get_plan
        - list_plans
        - update_plan
        - create_coordinator_lease
        - get_coordinator_lease
        - list_coordinator_leases
        - coordinator_heartbeat
        - create_decision_record
        - list_decision_records
        - create_vault
        - get_vault
        - create_credential
        - get_credential
        - create_tool_grant
        - get_tool_grant
        - list_agent_grants
        - revoke_grant
        - record_invocation
        - list_invocations
        - create_memory
        - get_memory
        - list_memory
        - update_memory
        - delete_memory
        - register_agent
        - get_agent_record
        - list_agents
        - agent_heartbeat
        - update_agent_status
        - create_trigger
        - get_trigger
        - list_triggers
        - update_trigger
        - fire_trigger
        - delete_trigger
        - invoke_tool
        - close
