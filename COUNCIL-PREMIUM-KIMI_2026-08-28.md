# COUNCIL-PREMIUM-KIMI_2026-08-28 — Simplification + Cross-Domain Wildcard

**Date:** 28.08.2026 · **Mode:** discovery only, nothing implemented
**Inputs compressed (not echoed):** COUNCIL-ORCH-RELIABILITY, COUNCIL-STRUCTURAL-MEMORY, COUNCIL-DRIFT-WILDCARD, COUNCIL-CROSSCRIT-B, COUNCIL-CROSSCRIT-C, BASIC-MEMORY-RELIABILITY_2026-08-27.
**Path note:** the evidence file lives at `.agents\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` (nested `.agents`), not at the path the prompt gave. That doubled directory is itself a live specimen of Issue 4/6-class drift.

**Thesis:** on a single-user single box with ~1.8 GB free, *every* proposal that adds a resident process, a registry, a scheduler, or a VM is a net negative regardless of elegance. The box's scarcest resource is not RAM — it is **the number of moving parts the owner can hold in his head while RAM is low**. Complexity is not merely *a* root cause; it is the multiplier on all six issues. The correct posture is: **policy paragraphs and kernel primitives beat controllers; deleting call sites beats guarding them.**

---

## 1. Per-issue smallest-fix table

| # | Issue | Smallest reversible fix (10% effort / 90% value) | What the other councils proposed that is over-engineered here |
|---|---|---|---|
| 1 | RAM mass-cancellation | **One policy paragraph in AGENTS.md:** no new Task while free RAM < 8 GB (G-4/G-26 already say this — enforce, don't instrument); **never relaunch a "canceled" agent without a liveness check** (`Get-Process` + `~/.cursor/subagents/` mtime). Zero code. | AIMD `cwnd` controller, admission-probe hooks, Job Objects, pagefile tuning, fleet supervisors. All deferred or rejected by Council A itself; the policy paragraph is the entire Rank-1 REC minus the "AIMD later" tail. |
| 2 | Dead-but-alive agents | Same paragraph, second clause: **canceled ≠ dead; one writer per checkout.** The liveness check in #1 *is* the fix. Kernel lock (`LockFileEx`) helper only if the policy is observed being ignored — 15 lines, deletable. | JSON registries (rejected as SoT by A), agent-mail heartbeats as truth (advisory only), always-isolate-in-worktree (RAM multiplier), OTP supervision trees. |
| 3 | Cyber-safeguard blocks | **Delete the call site:** harness sweeps are not an agent job. `Get-ChildItem -Name` / Glob-of-names cannot trip a classifier, cannot double-edit, costs no tokens. Plus: sanitize chat titles (free). | Exclusion manifests (rot), CVP applications (don't propagate to Cursor subagents — documented), vendor-routing of dual-use reads (safeguard shopping, correctly vetoed), framing tricks. |
| 4 | Home-as-workspace doubling | **Behavioral, not technical:** pin and open a dedicated root (`~\projects`). Do **not** touch `~/.cursor/mcp.json` — the 27.08 receipt proves the duplicate scope is *harmless* and removing the entry kills User scope for every other workspace. **UNVERIFIED:** the actual RAM cost of the double-load has never been measured; the fix is justified by correctness/confusion, not by a measured RAM saving. | NTFS junction reorgs (backup/recursion hazards, killed by CROSSCRIT-B), "delete global mcp.json" (fragile hack, killed by the evidence doc itself). |
| 5 | basic-memory flapping | **Already fixed 27.08** (catalog evicted from vault, warm-up grace re-stamped, per-launch stderr capture). The smallest fix is *don't regress*: keep the **>100 KB machine-generated-files-out-of-the-vault** policy + pointer-note pattern. Retract the permanent vector-disable (CROSSCRIT-B and -C both killed it — root cause was one 1,482-chunk entity, not embeddings per se). 48-h A/B only if strikes recur. | Permanent vector disable (feature amputation for a sizing bug), WSL2+systemd offload (vmmem draws from the same starved host RAM — killed by both cross-crits), Job-Object caps (changes "system bogs" to "daemon insta-crashes"), off-box Pi (real but high-effort; keep as the *only* legitimate offload if guards fail). |
| 6 | Silent bridge loss | **Make the one known silent skip loud.** `sync_local_bridge_mcp.py` currently prints `skip: bridge MCP file missing` and returns success — change that one path to emit `DRIFT:WARN [CRITICAL]` (and optionally non-zero under an opt-in env var). Then append 3–5 CRITICAL-only assertions to the *end* of the existing `sync_shared_state.ps1` (bridge file exists, `.claude\skills` is a link, `agents.json` parses, basic-memory/agent-mail present in Codex+Claude configs). No new file, no daemon, no extension. | The full four-severity / six-runtime drift matrix (MEDIUM/INFO tiers are alert-fatigue generators — Skeptic and CROSSCRIT-B both flagged), VS Code status-bar extension (maintenance burden, ignorable), tray toasts, strict-mode-by-default. |

---

## 2. Delete / consolidate list

**Delete (proposals, habits, or code paths):**

1. **Local fan-out as the default parallel strategy** — the boldest deletion, and it is a *habit*, not code. Council A's Skeptic is right and the cross-crits converged: at this box's RAM the correct local concurrency is **parent + at most 1 worker**; parallelism is owner-invoked Cloud (G-27) or serial. Every controller proposed (AIMD, bulkheads, quotas) exists to manage a stampede that policy can simply not start. *Delete the stampede, not the symptoms.*
2. **Agent-run harness sweeps** — replaced by a name-only script. Deletes Issue 3's entire failure class and shrinks Issue 1's demand side.
3. **WSL2+systemd offload** — killed twice in round 2; delete from consideration on this box. Revisit only off-box (separate hardware), which is the only true RAM offload.
4. **Permanent vector-disable** — killed by the 27.08 root-cause receipt. Delete from the option set; keep the size guard.
5. **JSON registries / heartbeat files as liveness SoT** — they are Issue 2 wearing a trench coat (stale under exactly the RAM pressure they police). Kernel lock or nothing.
6. **`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` as an Issue-1 fix** — wrong runtime (Cursor IDE Tasks ignore it); at most optional Claude Code hygiene.
7. **NtSuspendProcess freezer, Job-Object-the-IDE, pagefile-as-policy** — already rejected by Council A; record as permanently dead so they stop being re-proposed.

**Consolidate (fold into what exists):**

- All admission + liveness ideas (A's lease, C's token contract) → **one lockfile convention**, not three mechanisms.
- Drift-check → **append to `sync_shared_state.ps1`** (existing dispatcher); do not create a verifier binary, a health service, or a status extension.
- "Don't start heavy things when RAM is low" → **one shared threshold** (G-4's 8 GB) reused by Tasks, embedding, and sweeps — not three flap-controllers with three watermarks.
- Sweep allowlist/denylist → one positive allowlist (`.agents/scripts`, `.agents/hooks`, `AGENTS.md`); denylist secondary.

---

## 3. The wildcard: a **stateless thermostat over kernel truth** (control theory, minus the controller)

**The borrow:** industrial control's simplest regulator is not the PID loop — it is the **thermostat**: a binary mode evaluated *at the moment of decision* against a physical sensor, with no model, no state, no tuning. Every proposal so far (AIMD, error budgets, supervision trees) smuggles in a controller with memory. On this box, memory = state files = staleness = Issue 2.

**The mechanism:** every "should I start something heavy?" decision point (Task spawn, subagent resume, basic-memory embedding batch, harness sweep) evaluates exactly two *stateless kernel truths* at decision time:

1. **Commit remaining** (performance counter `\Memory\Committed Bytes` vs `Commit Limit` — the Windows-correct metric Council A identified, ~50 ms to read, no allocation spike), and
2. **The heavy-slot lock** (`LockFileEx`, non-blocking try) on a single `heavy-slot.lock` file.

Rule: if commit headroom is below the G-4-derived floor **or** the slot is held → decline/queue-in-parent's-head (K8s Pending semantics); never retry-storm, never twin.

**Why this dissolves ≥2 issues (actually 3.5):**

- **Issue 1 (mass cancel):** admission happens *before* the stampede, at the decision point, with no daemon to feed.
- **Issue 2 (dead-but-alive):** the lock is the liveness truth — kernel releases it on process death, so "held" = alive, "free" = dead, and PID reuse is irrelevant. The same artifact is the mutex and the admission ticket (Council A's escalated idea; CROSSCRIT-B and -C both kept it).
- **Issue 5 (flapping):** the basic-memory launcher — a spawn we own — checks the same slot before starting an embedding batch; an oversized-entity stall can no longer coincide with a fan-out. (Requires basic-memory cooperation; config-level feasibility **UNVERIFIED** — worst case it applies only to agent spawns, which is still 2 issues.)
- **Issue 6 (partial):** one artifact (`heavy-slot.lock` + the threshold) defines "safe to proceed," shrinking the drift surface a verifier must watch.

**The genuinely novel twist vs. the other councils:** hysteresis without state. A classic Schmitt trigger needs to remember its last mode (a state file → staleness). Here **the lock itself is the memory of the system**: while a heavy task runs, it holds the slot, so the "don't start" decision does not depend on a flickering RAM reading at all. The free-RAM sensor only matters for the *first* admission; mutual exclusion carries the system through the noisy middle. Two thresholds collapse into one threshold + one lock. No flap, no grace windows, no markers, nothing to fsync.

**RAM stress-test verdict: SURVIVES.**

- Resident cost: **zero** — no daemon, no watcher, no registry. The entire mechanism is a counter read + a `LockFileEx` attempt at decision time (both fail cheap).
- Under thrash (H2 conditions): the counter read is a paged-in kernel structure, not a working-set allocation; it cannot be the straw that trips the box. Worst case it under-admits — the safe direction, and the correct feeling at 1.8 GB free.
- Failure mode: counter read fails → fail-open per the verification doctrine, but log `ADMIT:UNVERIFIED` so the failure is visible (unlike today's silent skips).
- What it does **not** survive: agents that don't call the check. It is a convention, not an enforcement boundary — same limitation as every policy on this box, which is why the lock (not the counter) must be the load-bearing half. If a hook point for Cursor Task spawns exists (**UNVERIFIED** — Council A flagged this), wire the check there; if not, policy + lock still beats every alternative on the table.
- Anti-overfit: no scheduler, no queue, no DAG, no resident process — stays below CROSSCRIT-C's "second orchestrator" line by construction.

**CHALLENGES STANDING DECISION:** none. It honors G-4/G-26/G-27/G-36/G-68, adds no runtime, no SaaS, no vector DB. It *operationalizes* existing locks rather than revising them.

---

## 4. Ranked top 5 leanest actions

1. **One AGENTS.md policy paragraph:** no new Task while free < 8 GB; canceled ≠ dead — `Get-Process` + `~/.cursor/subagents/` mtime before any relaunch; one writer per checkout. *(Fixes 1+2. Zero code, fully reversible, effective today.)*
2. **Delete agent-run harness sweeps** — replace with name-only `Get-ChildItem`/Glob; sanitize chat titles. *(Fixes 3 by removing the call site; also shrinks Issue 1's demand.)*
3. **Pin a dedicated workspace root (`~\projects`) and stop opening `~`** — no `mcp.json` surgery (the duplicate is proven harmless; the entry is load-bearing for other workspaces). *(Fixes 4; behavioral, reversible by reopening home.)*
4. **Don't regress basic-memory:** keep vectors ON, enforce the >100 KB vault size policy + pointer notes; monitor the now-captured `daemon-*.err.log` for `Vector sync oversized entity`. *(Fixes 5 — the repair already landed 27.08; this is a guardrail, not a build.)*
5. **Make the silent skip loud:** flip `sync_local_bridge_mcp.py`'s missing-bridge skip to `DRIFT:WARN [CRITICAL]` + append 3–5 CRITICAL-only assertions to the end of `sync_shared_state.ps1`. *(Fixes 6. One existing file, no new surface.)*

The thermostat+lock (wildcard) is **#6 — conditional**: build the 15-line lock helper only if receipts show the policy paragraph being ignored. Policy first, mechanism on evidence.

---

## 5. Return

- **Smallest-fix set:** policy paragraph (1+2) · script-not-agent sweeps (3) · dedicated workspace root, no mcp.json edits (4) · size-policy guardrail on an already-repaired daemon (5) · one loud sentinel in an existing script (6). Total new code across all six issues: **~15 lines, all optional.**
- **Boldest deletion:** local fan-out as a strategy — delete the stampede, not its symptoms. Runner-up: agent-run sweeps (deletes an entire failure class).
- **Wildcard:** the stateless thermostat over kernel truth — one commit-headroom threshold + one `LockFileEx` heavy-slot, where the lock *is* the system's memory, giving hysteresis with zero state. Dissolves Issues 1, 2, 5 (partially 6); survives the RAM stress-test because it is resident-free and fails in the safe direction.
- **Confidence: 0.72.** High on the deletions and the policy-first ordering (converged across all three round-1 councils and both cross-crits). Lower on (a) the unmeasured RAM cost of the mcp.json double-load (**UNVERIFIED**), (b) a blockable Cursor Task-spawn hook existing at all (**UNVERIFIED**), and (c) basic-memory honoring an external slot check (**UNVERIFIED**). The causal story of the original 8 cancels remains H2/H3/H5 — still not disk-verified; the policy set is robust to all three.
