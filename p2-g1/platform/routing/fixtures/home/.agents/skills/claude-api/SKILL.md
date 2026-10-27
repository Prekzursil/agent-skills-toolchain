---
name: claude-api
description: Anthropic Claude API patterns for Python and TypeScript. Covers Messages API, streaming, tool use, vision, extended thinking, batches, prompt caching, and Claude Agent SDK. Use when building applications with the Claude API or Anthropic SDKs.
origin: ECC
---

# Claude API

Build applications with the Anthropic Claude API and SDKs.

## When to Activate

- Building applications that call the Claude API
- Code imports `anthropic` (Python) or `@anthropic-ai/sdk` (TypeScript)
- User asks about Claude API patterns, tool use, streaming, or vision
- Implementing agent workflows with Claude Agent SDK
- Optimizing API costs, token usage, or latency

## Model Selection

| Model | ID | Best For |
|-------|-----|----------|
| Opus 4.1 | `claude-opus-4-1` | Complex reasoning, architecture, research |
| Sonnet 4 | `claude-sonnet-4-0` | Balanced coding, most development tasks |
| Haiku 3.5 | `claude-3-5-haiku-latest` | Fast responses, high-volume, cost-sensitive |

Default to Sonnet 4 unless the task requires deep reasoning (Opus) or speed/cost optimization (Haiku). For production, prefer pinned snapshot IDs over aliases.

## Python SDK

### Installation

```bash
pip install anthropic
```

### Basic Message

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

message = client.messages.create(
    model="claude-sonnet-4-0",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Explain async/await in Python"}
    ]
)
print(message.content[0].text)
```

### Streaming

```python
with client.messages.stream(
    model="claude-sonnet-4-0",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a haiku about coding"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

### System Prompt
### TypeScript SDK
### Installation
### Basic Message
### Streaming
### Tool Use
### Handle tool use response
