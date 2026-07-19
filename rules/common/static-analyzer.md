---
paths:
  - "**/*.py"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# Static-Analyzer Gotchas

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
