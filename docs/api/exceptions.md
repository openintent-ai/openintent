# Exceptions API Reference

Custom exceptions for the OpenIntent SDK.

## Base Exceptions

::: openintent.exceptions.OpenIntentError
    options:
      show_source: false

::: openintent.exceptions.APIError
    options:
      show_source: false

## HTTP Errors

::: openintent.exceptions.NotFoundError
    options:
      show_source: false

::: openintent.exceptions.ConflictError
    options:
      show_source: false

::: openintent.exceptions.ValidationError
    options:
      show_source: false

::: openintent.exceptions.AuthenticationError
    options:
      show_source: false

## Usage

```python
from openintent import OpenIntentClient
from openintent.exceptions import ConflictError, NotFoundError

client = OpenIntentClient(base_url="...", agent_id="...")

try:
    client.patch_state(intent_id, {"key": "value"})
except ConflictError:
    # Version mismatch - need to refresh and retry
    intent = client.get_intent(intent_id)
    client.patch_state(intent_id, {"key": "value"})
except NotFoundError:
    # Intent doesn't exist
    print("Intent not found")
```
