---
name: dotnet test hang diagnosis & prevention
description: How to diagnose a stuck `dotnet test` invocation in this repo and the
  wrapper pattern that prevents silent hangs.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-dotnet-test-hang-diagnosis
---

When a `dotnet test` background task in this repo runs longer than the historical norm (~3-4 min for `tests/SwfocTrainer.Tests`) with **0 bytes** in its output file, it is hung — not slow. Confirmed during iter 172: a 7-minute-stuck run had no `dotnet`/`testhost` processes alive, meaning the hang was **before** testhost ever launched.

**Why:** Don't reach for `... | tail -3` on a long-running command. The pipe buffers everything until completion, so a hang that produces no progress lines is invisible until either the wrapper times out or the user notices. The same shape masked the iter-160 stale-`SwfocTrainer.App` DLL-lock incident.

**How to apply:**

1. **Always tee `dotnet test` output to a file** so progress is observable in real time:
   ```bash
   dotnet test ... 2>&1 | tee /tmp/test-run.log | grep --line-buffered -E "Passed!|Failed!|FAIL|Total tests|error MSB|error CS|Test Run Failed"
   ```
   Plain `| tail -N` is a hard no for any process expected to take >30s.

2. **Add `--blame-hang-timeout 5m` to `dotnet test`** so testhost hard-fails any single test that hangs, instead of silently spinning.

3. **Pre-flight kill stale lock holders** before invoking the test runner:
   ```pwsh
   Get-Process SwfocTrainer.App -ErrorAction SilentlyContinue | Stop-Process -Force
   Get-Process testhost -ErrorAction SilentlyContinue | Stop-Process -Force
   ```
   The UiTests project launches the WPF app; if a previous run aborted, the child can survive and lock `bin/Debug` DLLs invisibly (this is the iter-160 / iter-168 pattern).

4. **Diagnostic checklist when a run looks stuck:**
   - `wc -c <output-file>` → 0 bytes after >2× normal duration confirms hang.
   - `Get-Process dotnet,testhost,SwfocTrainer.App` → if no `dotnet`/`testhost` exist but the wrapper PowerShell is alive, the build phase hung.
   - Probe `bin/Debug/*.dll` via `[System.IO.File]::Open(...)` for lock state — non-`NOT_LOCKED` means a stale process is holding it.

**Why (incident reference):** iter 172 stop-hook surfaced this when the user noticed a 7-minute hang. Build itself ran in 12.7s with 0 errors, the DLLs were not locked, but the wrapped `... | tail -3` masked the true state. The replacement pattern (tee + line-buffered grep + monitor) shipped progress immediately.