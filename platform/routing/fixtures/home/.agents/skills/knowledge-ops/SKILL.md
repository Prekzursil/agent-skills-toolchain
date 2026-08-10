---
name: knowledge-ops
description: Knowledge base management, ingestion, sync, and retrieval across multiple storage layers (local files, MCP memory, vector stores, Git repos). Use when the user wants to save, organize, sync, deduplicate, or search across their knowledge systems.
origin: ECC
---

# Knowledge Operations

Manage a multi-layered knowledge system for ingesting, organizing, syncing, and retrieving knowledge across multiple stores.

Prefer the live workspace model:
- code work lives in the real cloned repos
- active execution context lives in GitHub, Linear, and repo-local working-context files
- broader human-facing notes can live in a non-repo context/archive folder
- durable cross-machine memory belongs in the knowledge base, not in a shadow repo workspace

## When to Activate

- User wants to save information to their knowledge base
- Ingesting documents, conversations, or data into structured storage
- Syncing knowledge across systems (local files, MCP memory, Supabase, Git repos)
- Deduplicating or organizing existing knowledge
- User says "save this to KB", "sync knowledge", "what do I know about X", "ingest this", "update the knowledge base"
- Any knowledge management task beyond simple memory recall

## Knowledge Architecture

### Layer 1: Active execution truth
- **Sources:** GitHub issues, PRs, discussions, release notes, Linear issues/projects/docs
- **Use for:** the current operational state of the work
- **Rule:** if something affects an active engineering plan, roadmap, rollout, or release, prefer putting it here first

### Layer 2: Claude Code Memory (Quick Access)
- **Path:** `~/.claude/projects/*/memory/`
- **Format:** Markdown files with frontmatter
- **Types:** user preferences, feedback, project context, reference
- **Use for:** quick-access context that persists across conversations

### Layer 3: MCP Memory Server (Structured Knowledge Graph)
### Layer 4: Knowledge base repo / durable document store
### Layer 5: External Data Store (Supabase, PostgreSQL, etc.)
### Layer 6: Local context/archive folder
### Ingestion Workflow
### 1. Classify
### 2. Deduplicate
### 3. Store
### 4. Index
