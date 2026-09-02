---
name: agentic-os
description: Build persistent multi-agent operating systems on Claude Code. Covers kernel architecture, specialist agents, slash commands, file-based memory, scheduled automation, and state management without external databases.
origin: ECC
---

# Agentic OS

Treat Claude Code as a persistent runtime / operating system rather than a chat session. This skill codifies the architecture used by production agentic setups: a kernel config that routes tasks to specialist agents, persistent file-based memory, scheduled automation, and a JSON/markdown data layer.

## When to Activate

- Building a multi-agent workflow inside Claude Code
- Setting up persistent Claude Code automation that survives session restarts
- Creating a "personal OS" or "agentic OS" for recurring tasks
- User says "agentic OS", "personal OS", "multi-agent", "agent coordinator", "persistent agent"
- Structuring long-running projects where context must survive across sessions

## Architecture Overview

The Agentic OS has four layers. Each layer is a directory in your project root.

```
project-root/
├── CLAUDE.md          # Kernel: identity, routing rules, agent registry
├── agents/            # Specialist agent definitions (markdown prompts)
├── .claude/commands/  # Slash commands: user-facing CLI
├── scripts/           # Daemon scripts: scheduled or event-driven tasks
└── data/              # State: JSON/markdown filesystem, no external DB
```

### Layer Responsibilities

| Layer | Purpose | Persistence |
|---|---|---|
| Kernel (`CLAUDE.md`) | Identity, routing, model policies, agent registry | Git-tracked |
| Agents (`agents/`) | Specialist identities with scoped tools and memory | Git-tracked |
| Commands (`.claude/commands/`) | User-facing slash commands (`/daily-sync`, `/outreach`) | Git-tracked |

### The Kernel
### Kernel Structure
### CLAUDE.md - Agentic OS Kernel
### Identity
### Agent Registry
### Routing Rules
### Model Policies
### Key Principle
### Specialist Agents
### Agent Definition Format
