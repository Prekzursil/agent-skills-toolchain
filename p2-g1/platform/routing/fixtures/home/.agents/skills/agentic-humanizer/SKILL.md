---
name: agentic-humanizer
description: Use when the user invokes /agentic-humanizer or asks to humanize AI-generated text via a 5-pass rewrite with optional voice-matching and (when Slop or Not Pro is available) detector scoring and readability checks ; do NOT use for mere AI-detection without rewriting (use slop-check) ; returns humanized text with optional readability stats.
license: MIT
allowed-tools:
- Read
- Bash
- AskUserQuestion
metadata:
  version: 0.1.0
  compatibility: claude-code codex cursor gemini-cli opencode
  source: https://github.com/numen-tech/slopornot
  upstream_author: Numen Technologies
---

# Agentic Humanizer

A 5-pass AI humanizer. It always runs the core rewrite workflow; Slop or Not
Pro adds measured on-device AI detector checks.

- **Without Slop or Not:** runs the full rewrite workflow.
- **With Slop or Not Pro:** adds on-device AI detector scoring, readability, Text Cleanup, and
  cleanup stats.

**Slash command:** `/agentic-humanizer [paste text]`

**Inline overrides:** `/agentic-humanizer dialect=us|uk grade=N tone=casual|professional|academic length=±10|exp|trim threshold=N max=N voice=/path/to/file.txt|off voice-skip skip-interview [paste]`

## What this skill does

1. Detects the host harness (Claude Code, Codex, Cursor, Gemini CLI,
   OpenCode, or generic).
2. Handles profile and voice management commands before any rewrite.
3. Resolves rewrite preferences from inline overrides, saved profile, or the
   harness interview.
4. Optionally resolves a writing sample and extracts a cached stylometric
   fingerprint. Voice matching does not require Slop or Not.
5. Probes whether Slop or Not Pro is reachable via MCP or CLI.
6. Runs the 5-pass humanization workflow:
   - Core mode logs unscored iterations.
   - Slop or Not Pro runs Text Cleanup, detection, and readability checks.
7. Returns the final text, loop history, highest-impact edits, and, when Slop
   cleanup ran, a Text Cleanup summary.

## Step 1: Detect the harness

Identify which harness is running by checking for the harness's distinctive
question tool. Use the first match:

| Harness | Distinctive tool present? | Read this file |

### Step 2: Profile management commands
### Step 3: Resolve rewrite preferences
### Step 4: Resolve voice sample
### Step 5: Probe Slop or Not Pro
### Step 6: Run the loop
### Slop or Not Pro setup
### Core setup
### Cleanup stats parsing
### Termination with Slop or Not Pro
### Completion in Core mode
### Mid-flight Pro-gate
