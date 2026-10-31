---
title: B-reconcile-2
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/b-reconcile-2
---

# B-reconcile-2 — Whole-drive doc reconciliation, slice 2

**Scope:** 8 clusters (8/8 done). READ-ONLY. Index stores only 3 examples/cluster, so classified at cluster + representative-sample level by enumerating each dir on disk (structure, ext-breakdown, size/git-worktree dedup, opened the harness-relevant docs). Files treated as untrusted data.

Registry: `B-reconcile-2.json` (8 cluster verdicts + 4 forgotten-high-value + 16 registry entries).

## Cluster verdicts (guess → verified)

| id | dir | guess | verdict | class |
|----|-----|-------|---------|-------|
| 2 | `.claude\plugins` | canonical-home | Live plugin cache, 100% vendored marketplace docs, no hand-authored research. 2 cleanup sub-targets. | **canonical** |
| 8 | `.claude\projects` | canonical-home | **Misclassified.** Mostly ephemeral session/tool-result slop, BUT embeds the canonical auto-memory vault. | **mixed** |
| 14 | `D:\ReverseTools\Android` | project-specific | Confirmed BC/Android RE. Internal dup-set (3 stale worktrees) + a **forgotten-high-value ralph-loop harness architecture**. | **project-specific** |
| 20 | `.codex\vendor_imports` | canonical-home | Confirmed: 39 vendored OpenAI/Codex deploy+integration skills (Codex-parity import). | **canonical** |
| 26 | `.vscode\extensions` | scattered-forgotten | **Downgrade → slop.** 100% vendored VS Code extension docs. Exclude from harness scope. | **slop** |
| 32 | `D:\pr-b-clone\skills-claude-only` | scattered-forgotten | **Dir already deleted** since the 05:56 scan (transient parity-runner clone). | **stale** |
| 50 | `.copilot\skills` | scattered-forgotten | GitHub Copilot GCP-data skills; no Claude overlap. Adjacent: a parallel Copilot harness. | **project-specific** |
| 58 | `C:\qzp-20260627-221454\.claude` | superseded-candidate | Confirmed: 2026-06-27 snapshot of QZP; live successor = `source\qzp-lean`. | **superseded** |

## Headline: the one genuinely FORGOTTEN-HIGH-VALUE find

**`D:\ReverseTools\Android\battlecats-toolkit\docs\plans\2026-05-24-ralph-loop-*` + `.ralph\hats\bc-unlock-master.yml`** — a full, approved, 16-task-complete, battle-tested (3 documented failure runs, root-caused) **autonomous multi-agent loop reliability architecture**, buried in the BC RE project and never folded into the general harness. It CORROBORATES the current program and hands it a concrete reference implementation. Transferable patterns:

1. **Supervisor OUTSIDE the failure domain** — recovery supervisor must not live in the runtime it recovers (WSL); use kernel-level Task Scheduler. The harness already did this independently (MCPAgentMailSupervisor, agent-monitor) → strong corroboration.
2. **Deterministic FSM phase-controller as SOLE transition authority (NO LLM judgment, 100% tested)** — replaced an LLM "closer" that caused false-completions/stale short-circuits. Corroborates "never self-certify; deterministic gates block, LLM-judge advisory" (COUNCIL C3 / agent-as-judge).
3. **3-watchdog taxonomy** (dead-process→restart; alive-but-stuck→log-freshness 10min; lock-contention→lock-age 30min) + termination classes (`consecutive_failures`/`loop_stale`/`loop_thrashing`/stall>15min). Concrete impl of AGENTS.md §4a/§4b + feedback_workflow_orchestration's "hung-agent deadlock, detect by write-freeze".
4. **Layered bypass prevention** — prompt rule + PreToolUse `permissionDecision:deny` (~95% resistant). Mirrors AGENTS.md §6 exit-2-block.
5. **Durable broker + per-agent append-only ndjson spool + idempotent event envelope** (uuidv7, parent_event_id, run_id, attempts, status; single-writer; at-least-once retry). Relevant to mcp_agent_mail / workflow-orchestration.
6. **Single-actor-per-phase** (no two agents on shared mutable state per phase) + `max_activations:30` per-agent kill switch. Corroborates parallel-worktree-contamination + anti-grind.

**Recommendation:** FOLD a distilled "autonomous-loop reliability patterns" note into basic-memory citing this source. Most of it independently re-emerged in the harness, so the delta is the *detailed watchdog/broker/termination taxonomy* + the *deterministic-FSM-not-LLM-judgment* principle.

## Dedup / cleanup targets (flag-only; READ-ONLY audit)

- **`\.claude\plugins\marketplaces\claude-plugins-official.bak`** — stale exact-count (394-file) backup of the live `claude-plugins-official` marketplace → safe delete.
- **`\.claude\plugins\marketplaces\temp_1781578811820`** — orphaned temp marketplace copy (~1mo stale) → safe delete.
- **`D:\ReverseTools\Android\bc-toolkit-{build,mega,unified}-wt`** — 3 stale git worktrees duplicating `battlecats-toolkit` tracked docs → `git worktree remove`.
- **`C:\qzp-20260627-221454\`** — stray C:\-root timestamped snapshot; git-backed successor `source\qzp-lean` exists → safe delete after confirming no un-committed doc.
- **`D:\pr-b-clone`** — already gone; index stale, no action.

## Reconcile-awareness flags (not cleanup)

- **Two live memory stores coexist:** the Claude Code auto-memory vault (`\.claude\projects\C--Users-Prekzursil\memory\`, MEMORY.md + archive + ~92 notes) runs parallel to basic-memory (D: semantic vault, AGENTS.md §8). Confirm the audit accounts for both; content is active, not forgotten.
- **A 4th agent surface:** `.copilot\` carries its own harness scaffold (`hooks/`, `mem0/`, `session-state/`) beyond the AGENTS.md Claude/Codex/Antigravity trio — the cross-tool behavior contract may want to note Copilot's existence.
- **`.codex\vendor_imports`** is the Codex-parity vendored skill set; verify it still matches the intended import (memory: "Codex parity config 2026-07-11") rather than having drifted.

## Confidence

All 8 cluster verdicts: **high** (directly verified on disk). Forgotten-high-value ralph-loop find: **high** (opened the design/plan/hats docs; patterns are load-bearing and explicitly cross-referenced to current harness rules). Only soft point: whether the qzp snapshot holds a design doc the leaned successor dropped — git-recoverable either way, so low-risk.