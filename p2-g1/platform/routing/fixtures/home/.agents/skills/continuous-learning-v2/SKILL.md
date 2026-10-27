---
name: continuous-learning-v2
description: Instinct-based learning system that observes sessions via hooks, creates atomic instincts with confidence scoring, and evolves them into skills/commands/agents. v2.1 adds project-scoped instincts to prevent cross-project contamination.
origin: ECC
version: 2.1.0
---

# Continuous Learning v2.1 - Instinct
-Based Architecture

An advanced learning system that turns your Claude Code sessions into reusable knowledge through atomic "instincts" - small learned behaviors with confidence scoring.

**v2.1** adds **project-scoped instincts** — React patterns stay in your React project, Python conventions stay in your Python project, and universal patterns (like "always validate input") are shared globally.

## When to Activate

- Setting up automatic learning from Claude Code sessions
- Configuring instinct-based behavior extraction via hooks
- Tuning confidence thresholds for learned behaviors
- Reviewing, exporting, or importing instinct libraries
- Evolving instincts into full skills, commands, or agents
- Managing project-scoped vs global instincts
- Promoting instincts from project to global scope

## What's New in v2.1

| Feature | v2.0 | v2.1 |
|---------|------|------|
| Storage | Global (~/.claude/homunculus/) | Project-scoped (projects/<hash>/) |
| Scope | All instincts apply everywhere | Project-scoped + global |
| Detection | None | git remote URL / repo path |
| Promotion | N/A | Project → global when seen in 2+ projects |
| Commands | 4 (status/evolve/export/import) | 6 (+promote/projects) |
| Cross-project | Contamination risk | Isolated by default |

## What's New in v2 (vs v1)

| Feature | v1 | v2 |
|---------|----|----|
| Observation | Stop hook (session end) | PreToolUse/PostToolUse (100% reliable) |
| Analysis | Main context | Background agent (Haiku) |

### The Instinct Model
### Prefer Functional Style
### Action
### Evidence
### How It Works
### Project Detection
### Quick Start
### 1. Enable Observation Hooks
### 2. Initialize Directory Structure
### Global directories
