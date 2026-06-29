# Global Claude Guidance

@AGENTS.md

## Working Style

- Ask clarifying questions before any long-horizon or ambiguous task: restate your understanding first, and when material ambiguity remains ask 1-3 questions rather than proceeding on assumptions. Front-load this into the first 1-2 actions (not mid-task). Keep the user's whole intent in view — don't fixate on one detail and miss the point.

## Persistent Memory (basic-memory MCP)

A `basic-memory` MCP server provides durable, semantically-searchable memory — a markdown+vector vault on D: holding migrated project notes plus auto-written **compaction checkpoints**. It does NOT auto-load into context; you must query it. This is how context survives compaction: nothing is truly lost because it is re-fetchable.

**Recall (pull) — do this PROACTIVELY, without being asked:**
- Right after a compaction/summary, when resuming work, or whenever the user references prior work/decisions you don't have in context: call `mcp__basic-memory__build_context` (purpose-built to "continue a discussion"), `mcp__basic-memory__search_notes` (semantic), or `mcp__basic-memory__recent_activity` to pull relevant notes BEFORE asking the user to re-explain or proceeding on assumptions.
- To recover what you were mid-task on before a compaction, search for `compaction checkpoint <project>` (those notes are tagged `compaction-checkpoint` and contain the pre-compaction work buffer + recent user intent).

**Capture (push):**
- When you learn something durable (a decision, a fix, a project fact, a user preference), write it with `mcp__basic-memory__write_note` so it survives the next compaction. A PreCompact hook also auto-captures a checkpoint before every compaction, so the live state is always saved even if you forget.

## Static-Analyzer Gotchas

- CodeQL `py/ineffectual-statement` misreads `await <task>` inside `with suppress(...)`:
  rewrite as explicit `try/except ExceptionType: pass` or
  `await asyncio.gather(task, return_exceptions=True)`. The `gather` form also
  silences SonarCloud `python:S7497` (which otherwise demands you re-raise
  `CancelledError` — wrong in a lifespan-cleanup context where you *are* the
  cancellation originator).
- SonarCloud `typescript:S3735` flags `void asyncCall()` as unnecessary. If the
  callee handles its own errors internally, drop the `void` prefix — a bare call
  is fine when `no-floating-promises` isn't enabled. Don't reach for `void` as
  a "discard a promise" idiom on Sonar-linted projects.
