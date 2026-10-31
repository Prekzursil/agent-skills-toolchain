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
  **`return_exceptions=True` is not a licence to swallow.** It converts *every*
  failure into a list element, not just the cancellation you expected, so a bare
  `await asyncio.gather(task, return_exceptions=True)` statement also hides an
  unrelated `RuntimeError("cleanup failed")` and a shutdown that actually failed
  reports success — the exact outcome `common/coding-style.md` forbids ("Never
  silently swallow errors"). Bind the result and re-raise anything you did not
  expect; keep `except <ExceptionType>: pass` narrow for the same reason:

  ```python
  for outcome in await asyncio.gather(*tasks, return_exceptions=True):
      if isinstance(outcome, BaseException) and not isinstance(
          outcome, asyncio.CancelledError
      ):
          raise outcome
  ```
- SonarCloud `typescript:S3735` flags `void asyncCall()` as unnecessary. If the
  callee handles its own errors internally, drop the `void` prefix — a bare call
  is fine when `no-floating-promises` isn't enabled. Don't reach for `void` as
  a "discard a promise" idiom on Sonar-linted projects.
