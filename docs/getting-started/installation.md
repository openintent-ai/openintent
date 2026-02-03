# Installation

## Requirements

- Python 3.10 or higher
- pip or poetry for package management

## Basic Installation

Install the core client library:

```bash
pip install openintent
```

## Installation Options

The SDK uses optional dependencies to keep the core package lightweight:

### With Built-in Server

```bash
pip install openintent[server]
```

Includes FastAPI server implementing all 8 RFCs. Run with `openintent-server`.

### With LLM Adapters

Install only the adapters you need:

```bash
# OpenAI GPT models
pip install openintent[openai]

# Anthropic Claude models
pip install openintent[anthropic]

# Google Gemini models
pip install openintent[gemini]

# xAI Grok models
pip install openintent[grok]

# DeepSeek models
pip install openintent[deepseek]

# All adapters
pip install openintent[all-adapters]
```

### Full Installation

Install everything:

```bash
pip install openintent[all]
```

## Verify Installation

```python
import openintent
print(openintent.__version__)
```

## Development Installation

For contributing to the SDK:

```bash
git clone https://github.com/openintent-ai/openintent.git
cd openintent
pip install -e ".[dev,all]"
```

## Next Steps

- [Quick Start](quickstart.md) - Create your first intent
- [Configuration](configuration.md) - Configure the client
