---
title: Installation
---

# Installation

## Requirements

- **Python 3.10** or higher
- **pip** or **poetry** for package management

## Install the SDK

=== "Minimal"

    ```bash
    pip install openintent
    ```

=== "With Server"

    ```bash
    pip install openintent[server]
    ```

    Includes the built-in FastAPI server implementing all 20 RFCs.

=== "Everything"

    ```bash
    pip install openintent[all]
    ```

    Includes all LLM adapters and the server.

!!! tip "Recommended for first-time users"
    Start with `pip install openintent[server]` so you can run a local server and explore the SDK immediately.

## LLM Adapters

Install only the adapters you need:

| Provider | Package | Models |
|----------|---------|--------|
| OpenAI | `openintent[openai]` | GPT-4o, GPT-4, GPT-3.5 |
| Anthropic | `openintent[anthropic]` | Claude 3.5, Claude 3 |
| Google Gemini | `openintent[gemini]` | Gemini Pro, Gemini Ultra |
| xAI Grok | `openintent[grok]` | Grok-1 |
| DeepSeek | `openintent[deepseek]` | DeepSeek Chat |
| Azure OpenAI | `openintent[azure]` | Azure-hosted GPT models |
| OpenRouter | `openintent[openrouter]` | 200+ models via unified API |

```bash
# Install specific adapters
pip install openintent[openai,anthropic]

# Or all adapters
pip install openintent[all-adapters]
```

## Verify Installation

```python
import openintent
print(openintent.__version__)  # 0.8.0
```

## Development Installation

!!! note "For contributors"
    Clone the repository and install in development mode with all extras:

    ```bash
    git clone https://github.com/openintent-ai/openintent.git
    cd openintent
    pip install -e ".[dev,all]"
    ```

    Run the test suite:

    ```bash
    pytest tests/ -v
    ```

## Next Steps

<div class="oi-features" style="margin-top: 1em;">
  <div class="oi-feature">
    <div class="oi-feature__title">Quick Start</div>
    <p class="oi-feature__desc">Create your first intent and coordinate agents in under a minute.</p>
    <a href="../quickstart/" class="oi-feature__link">Get started</a>
  </div>
  <div class="oi-feature">
    <div class="oi-feature__title">Configuration</div>
    <p class="oi-feature__desc">Advanced client configuration options, authentication, and environment variables.</p>
    <a href="../configuration/" class="oi-feature__link">Configure</a>
  </div>
</div>
