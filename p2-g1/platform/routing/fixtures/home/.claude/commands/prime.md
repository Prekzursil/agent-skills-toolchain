---
description: Load relevant knowledge base facts into context before starting work
---

# BEADS Prime

**CRITICAL**: Run this command at the START of any investigation, planning, or implementation work to load relevant knowledge into your context.

## When to Use

- Starting work on a GitHub Issue
- Beginning investigation/research
- Before writing a plan
- Before implementing changes
- When switching to a new area of the codebase

## How It Works

This command queries the BEADS knowledge base for facts relevant to your current context and injects them into the conversation, ensuring you:

1. Follow established patterns and rules
2. Avoid known gotchas and pitfalls
3. Make decisions aligned with architectural choices
4. Don't repeat mistakes that have been learned from

## Usage

### Quick Prime (Most Common)

For general context with automatic detection:

```bash
bd prime
```

### Prime for Specific Files

When working on specific files:

```bash
bd prime --files "src/lib/services/**/*.ts" "src/api/routes/**/*.ts"
