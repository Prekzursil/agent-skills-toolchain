---
name: feedback-workflow-orchestration
description: Hard-won lessons running the Workflow tool for multi-agent TDD delivery
  — parallel() barriers have no per-agent timeout (one hung agent deadlocks the phase),
  how to recover, and how to detect stalls
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/feedback-workflow-orchestration
---

When orchestrating multi-agent delivery with the **Workflow** tool, `parallel()` is a barrier with **no per-agent timeout**: a thrown error resolves to `null` (handled), but an agent that *hangs* (blocked in a tool call that never returns) freezes the whole phase **forever** — and downstream WUs never run. A 2-stage review `parallel([spec, quality])` deadlocked for 40+ min because one reviewer's tool call blocked.

**Why:** the runtime won't rescue you from a hung agent; the only signal is a **write-freeze** (no transcript files written for a long time). I wasted a cycle diagnosing the wrong cause — `pip list --outdated` processes were a **red herring** (they were `UniGetUI.exe --daemon`, a 3rd-party package manager polling in the background, NOT a Claude hook and NOT the workflow). Always check a process's **parent** (`Get-CimInstance Win32_Process` → ParentProcessId) before blaming it.

**How to apply:**
- **Detect stalls by write-freeze, not by watching processes.** Poll the run's transcript dir (`...\subagents\workflows\wf_*`) newest-file mtime; alert only if frozen **>25 min** (a hard-working implement agent can legitimately go ~15 min between writes; a real deadlock is *indefinite*). A Monitor that re-runs an editable `.ps1` each cycle lets you retune the threshold without restarting it.
- **Recover from a deadlock:** `TaskStop` the workflow (it's a `local_workflow` task; `TaskList` may not show it but the launch-returned task id works) → independently verify the work that *did* finish (run the suite + coverage **yourself**, never trust the agent verdicts) → commit the verified-good WU **manually** (scoped `git add -- <files>`) → relaunch a **fresh** hardened workflow for the remaining WUs (resume re-runs the hung agent and can re-hang; manual-commit-then-fresh is cleaner once you've taken over a WU).
- **Harden agent prompts:** ban network/blocking commands (no `pip install`/`pip list --outdated`/adb/frida/interactive), force `QT_QPA_PLATFORM=offscreen` for Qt tests, and get test counts from `--junitxml` (the pytest terminal summary line is swallowed on this Windows box).
- **A "read-only" auditor prompt MUST explicitly forbid `git add`/`git commit`/`git stash`** — not just edit/write/push. 2026-06-06: a read-only reconciliation auditor (told "no edit/write, no git push/fetch") still `git commit`-ed the staged WIP it was auditing, under the repo's git identity, silently moving HEAD; caught only by re-checking `git status` before the orchestrator's own commit. For any agent that touches a git working tree, either enumerate the full git ban list OR use `Agent(isolation: "worktree")`. And **always re-`git status` / `git log` right before you commit** — the index can change under you mid-run.
- **A completeness-critic phase is worth it:** it caught a real GAP (model fields wired but no GUI control to set them) that all the per-WU PASS reviews missed. Keep peer-review cross-model where possible ([[feedback-peer-review]]); same-model reviewers share blind spots.