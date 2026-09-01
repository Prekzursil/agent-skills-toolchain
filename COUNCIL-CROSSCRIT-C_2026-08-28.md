# COUNCIL-CROSSCRIT-C_2026-08-28 (Round 2 — Cross-critique, Wildcard/Drift)
**Mode:** Discovery only (conceptual adjudication).  
**Inputs read:**  
- `C:\Users\Prekzursil\.agents\COUNCIL-ORCH-RELIABILITY_2026-08-28.md`  
- `C:\Users\Prekzursil\.agents\COUNCIL-STRUCTURAL-MEMORY_2026-08-28.md`  
- `C:\Users\Prekzursil\.agents\COUNCIL-DRIFT-WILDCARD_2026-08-28.md`  
- `C:\Users\Prekzursil\.agents\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` (note: was not at the path in the prompt)

This is a deliberately adversarial synthesis: it tries to **kill** attractive proposals by stress-testing them against observed failure modes on this box (RAM pressure, stale client state, retry amplification, WSL VM restarts, and oversized-entity vector stalls). Survivors are preserved as **bold alternatives** with explicit minimal contracts.

---

## Executive verdict (one paragraph)
Treat “offload to WSL+systemd” as a **likely false offload on this machine** (vmmem is still host RAM/commit; P2 observed WSL restarts under pressure). Keep the proven Windows Scheduled Tasks supervision pattern for `basic-memory` and solve semantic-memory stalls via **oversized-entity/file-size guards** (already evidenced) rather than permanent vector disable. Unify concurrency safety and “dead-but-alive” truth with a **kernel-lock + token-lease** micro‑contract that cannot schedule or queue (so it doesn’t become a second orchestrator). Fix workspace duplication with a **dedicated workspace root** (junction is optional, but not default). For drift/health, pick exactly one **CRITICAL** sentinel that is un-ignorable and low-noise, and put strict-mode behind opt‑in plus grace windows.

---

## 1) WSL+systemd vs repaired Windows Tasks
### Kill attempt on “WSL is offload”
**Why offload is probably false here:**
- **WSL2 memory is not “other RAM.”** It is accounted against the Windows host via `vmmem` (host commit/working set). Under low free RAM, WSL competes with the IDE; it does not escape the bottleneck.
- You already observed **WSL VM restarts under pressure** (P2). That is a *worse* failure mode than a supervised Windows task: it can nuke both services simultaneously and create ambiguous client states.
- The most acute reliability failures in the evidence are not “lack of systemd,” they’re:
  - **oversized-entity embedding stalls** (1,482 chunks for a 378 KB catalog) starving the MCP surface (`Vector sync oversized entity detected... shard_count=6`) and triggering kill loops, and
  - supervision timeouts killing slow warmups (2.5–4 minutes bind) until the launcher was fixed.
  These are workload/guard/timeout issues, not “Windows cannot supervise.”

**Counterpoint (what WSL *could* still buy):** a cgroup cap can stop `basic-memory` from taking more than \(X\) GB. But on a host already near the cliff, that cap mostly changes who dies first. With observed WSL restarts, this is too risky to treat as primary.

### Adjudication
- **REJECT (as primary on-box strategy):** “Move always-on services into WSL+systemd” *for this machine now*.
- **KEEP (Windows-native):** repaired **Scheduled Tasks + watchdog + launcher** model is already present and demonstrably recoverable. The fix path is guards + evidence capture, not OS migration.

### Real alternative if WSL is rejected
**Alternative A (off-box, real offload):** host `basic-memory` on a separate low-power box (mini‑PC / Raspberry Pi-class if performance permits) or a small always-on home server, keep data local to your LAN, and point MCP to that IP/port. This is the only “offload” that truly escapes host RAM contention.

**Alternative B (process-isolated on Windows):** keep Tasks, and (optionally) wrap only the `basic-memory` daemon in a **Windows Job Object** memory cap (because you own that spawn) to bound blast radius. Do **not** job‑object Cursor/Electron.

### Threshold to reconsider WSL+systemd
Reconsider WSL+systemd only if **all** are true for ≥7 days:
- host free RAM is consistently **> 8 GB** (G‑4 success window), *and*
- WSL has an enforced memory limit (e.g., 1–2 GB) and **no VM restarts**, *and*
- Windows Tasks supervision remains unstable **after** oversized-entity guards + warmup fixes, *and*
- the services’ failure mode is “Windows plumbing” rather than “workload starvation.”

---

## 2) Permanent vector-disable vs conditional degradation vs file-size guard
### Evidence that kills “permanent vector-disable”
The `BASIC-MEMORY-RELIABILITY_2026-08-27.md` receipt demonstrates a concrete mechanism:
- A single **oversized generated catalog** created **1,482 embedding chunks** and caused “bound but HTTP unresponsive” strikes, kill/restart loops, and degraded availability.
- The fix that restored stability was **not** disabling semantic search. It was:
  - moving the oversized artifact **out of the vault** and leaving a small pointer note,
  - improving warmup tolerance and stderr capture.

So “disable vectors permanently” is solving the wrong layer (feature removal) when the failure is “one pathological entity can starve the event loop.”

### Adjudication
- **REJECT:** permanent vector-disable as the default posture (violates your requirement that semantic memory must survive).
- **KEEP (primary):** **file-size / chunk-count guard** + pointer-note pattern (already proven).
- **KEEP (secondary):** **conditional degradation** (pause vector sync under low resources/backlog) *only if it preserves semantic search on existing vectors* and never blocks plain-text ingestion.

### Minimal conceptual contract (no implementation)
**Oversized-entity policy (guardrail):**
- If a single entity exceeds a threshold (bytes OR chunk count), it becomes **non-vectorized by policy**:
  - store a small note in the vault with metadata + link/path to the external artifact,
  - keep FTS working, keep semantic on normal notes,
  - keep a durable log line: `OVERSIZE_ENTITY_SKIPPED`.

**Conditional degrade (resource-aware):**
- When commit remaining / free RAM is below a low watermark, semantic operations switch to **write-behind** (queue) or “skip re-embed” while still answering via existing vectors + FTS. This protects semantic memory while preventing stalls.

---

## 3) RAM-seconds lease + PID/kernel lock — smallest viable contract
### Kill attempt: “this becomes a second orchestrator”
It becomes a second orchestrator if it:
- queues work, reorders work, retries work on its own, or owns DAG state.

### Minimal contract that stays *below* “orchestrator”
**Smallest viable control-plane contract (conceptual):**

1) **Writer mutex (truth of life):** one per mutable target (worktree / vault / shared file).  
   - Mechanism: kernel-held exclusive lock (`LockFileEx`) on a lockfile.
   - Annotation: inside the file, best-effort JSON with `pid`, `agent_id`, `started_ts`, `purpose`, `grace_deadline_ts`.
   - Truth: the **lock**, not the JSON.

2) **Capacity tokens (RAM-seconds lease) without a daemon:**  
   - Represent \(N\) “heavy slots” as **\(N\) separate lockfiles** (e.g., `slot-0.lock ... slot-(N-1).lock`).
   - A task is allowed to start heavy work iff it can acquire one slot lock **and** the writer mutex if mutating.
   - No queue: if it cannot acquire, it must **return/decline** (human or parent chooses when to try again).  

3) **Grace + stale safety:**  
   - Grace windows are recorded only as annotations; the lock is the boundary.
   - If a lock is held but the PID is dead, treat it as “recent death” and **wait‑then‑retry**, not “spawn a twin.”

This contract solves:
- Issue 1 (admission: heavy slots),
- Issue 2 (dead‑but‑alive truth: writer mutex),
- and reduces Issue 6 blast radius (a single artifact defines “safe to proceed”)  
**without** a scheduler, daemon, or second runtime.

---

## 4) Dedicated workspace migration vs junction
### Ground truth from inputs
- The duplication bug is specifically: opening `C:\Users\Prekzursil` as workspace root causes Cursor to load `C:\Users\Prekzursil\.cursor\mcp.json` twice (User scope + project scope), producing confusing “red vs green” surfaces and wasting RAM.

### Adjudication
- **KEEP (default):** dedicated workspace root migration (behavioral change).
- **MODIFY (optional convenience):** junction workspace as a *bridge strategy*, not the default.
- **REJECT:** “delete global `.cursor\mcp.json`” (breaks other workspaces; high fragility).

### Why dedicated root wins (even if junctions exist)
- It eliminates **duplicate MCP scope** at the root cause: Cursor’s “project config” is no longer identical to the “user config.”
- It reduces accidental broad scans and index churn (home dir is huge, high‑churn).
- It avoids path-casing weirdness: multiple spellings (`C:\...` vs `c:\...`) and junction-resolved paths can create “same target, different string” duplicates in configs and tooling.

### Junction risks (the parts that break quietly)
- **Loop hazards:** if you junction a parent into a child (directly or via two links), recursive operations can explode.
- **Duplicate identity hazards:** tools that don’t canonicalize paths may treat junction paths as distinct trees (double-indexing, double-watch, duplicate MCP “project” loads if you accidentally open the wrong root).
- **User convenience:** junctions can reduce friction, but only if you keep them minimal and one-way.

**Bold alternative that survives:** **Dedicated workspace root + a few carefully curated junctions into it** (for convenience), provided the workspace root itself is *not* home and junctions are non-recursive and non-overlapping.

---

## 5) Drift check + health surface (one low-noise, un-ignorable signal)
### Single signal (un-ignorable, low-noise)
Use exactly one sentinel line as the “you cannot miss this” signal:
- **`DRIFT:CRITICAL`** — emitted *only* when a contract-breaking condition exists post-sync (examples: Claude local bridge file missing; `.claude\skills` stopped being a link; shared vault missing; `agents.json` unreadable).

Everything else is not allowed to look like paging:
- `DRIFT:WARN` for non-critical mismatches,
- `DRIFT:OK` for successes,
- and a short end banner: `End Drift Check (critical=X warn=Y)`.

### Strict-mode conditions
Strict mode must be opt-in and must not create new “false red” under RAM pressure:
- **Default:** never changes exit code; it only prints `DRIFT:*` lines.
- **Strict mode (`AGENTS_DRIFT_STRICT=1`):** fails only if **`DRIFT:CRITICAL` persists across two consecutive runs**, to avoid one-off transient states and transcript/IO lag.

### Grace windows (avoid flapping into strict failures)
- **After sync:** ignore `DRIFT:CRITICAL` for the first **60 seconds** only if the condition is known to race with file materialization (e.g., junction creation). If it’s “missing file,” do not grace it unless there is a credible in-flight creation step.
- **After boot/logon:** allow a **5-minute** grace window before strict-mode can fail, because services can warm up and filesystem links can materialize late on this machine under pressure.

### What should never page (must stay WARN/INFO)
- **Port reachability** for `basic-memory` / `agent-mail` during warmup or known flapping windows (this box has multi-minute warmups). Reachability is useful as context but too noisy to be “critical.”
- **Optional runtime configs** that aren’t under an explicit sync contract (avoid “warn because we don’t know”).
- Any “health surface” that requires network calls, recursion, or starting processes (those become failure sources).

**Bold alternative that survives:** **End-of-sync “Bridge Drift Check” that is purely read-only and emits one `DRIFT:CRITICAL` sentinel** (plus warnings), with strict mode opt‑in + persistence requirement.

---

## 6) New synthesis (not stated explicitly in Round‑1): “Artifact quarantine + pointer notes”
### The synthesis
Adopt a single behavioral policy that spans both the workspace and semantic memory:

**Quarantine large / machine-generated / high-churn artifacts outside both (a) the Cursor workspace root and (b) the `basic-memory` vault, and replace them with small pointer notes that are safe to index and embed.**

### Why this solves ≥3 issues without a new daemon
- **Solves Issue 2 (semantic stalls):** prevents oversized-entity embedding backlogs by construction (the proven mechanism).
- **Solves Issue 3 (cyber-safeguard blocks):** background “inventory” work never needs to Read dual-use or giant generated bodies; it can enumerate pointer notes and filenames only.
- **Helps Issue 1 (mass cancellations):** reduces RAM pressure from indexing, scanning, and embedding large artifacts; fewer heavy bursts means fewer retry-storm triggers.
- **Helps Issue 4 (workspace duplication):** pairs naturally with a dedicated workspace root; the “quarantine” can live outside the workspace and be linked deliberately when needed.

This is not “disable features,” and it doesn’t require a resident supervisor—just a placement rule and pointer discipline.

**Bold alternative that survives:** **Pointer-note discipline as the default way to reference large generated catalogs/logs/artifacts** (keep semantic memory intact for *notes*, not for giant generated dumps).

---

## KEEP / MODIFY / REJECT matrix (Round‑2 adjudication)
| Proposal / Option | Verdict | Why (adversarial summary) |
|---|---|---|
| **WSL+systemd local control plane (on this box)** | **REJECT** | Likely false offload (`vmmem` is host RAM/commit), plus observed WSL restarts under pressure create a worse failure domain than supervised Windows tasks. |
| **Windows Scheduled Tasks supervision for `basic-memory` (watchdog+launcher)** | **KEEP** | Already exists and was hardened; failures were workload guards + warmup timeouts, not “Windows cannot supervise.” |
| Job Objects on Cursor/Electron process tree | **REJECT** | You don’t own the spawn tree; hard limits convert pressure into crashes and add complexity. |
| Job Objects *only* around `basic-memory` (owned spawn) | **MODIFY** | Potential blast-radius limiter, but must not become a “kill loop”; only after guards/pointers, and only as containment. |
| Permanent vector-disable / reranker-disable | **REJECT** | Violates “semantic memory must survive.” Evidence shows the root cause was oversized entities, not semantics per se. |
| **Oversized-entity / file-size guard + pointer notes** | **KEEP** | Proven effective; preserves semantic memory for normal notes while preventing pathological stalls. |
| Conditional degradation (pause vector sync under low resources) | **MODIFY** | Acceptable only if it never blocks text ingestion and never permanently sacrifices semantics—must be reversible and transparent. |
| **Kernel lock (`LockFileEx`) as liveness truth** | **KEEP** | Solves dead-but-alive/twin-writer risk without needing a daemon or trusting stale JSON. |
| **Tokenized “heavy slots” via \(N\) lockfiles (RAM-seconds lease)** | **KEEP (with constraints)** | Minimal admission control without queueing; becomes “orchestrator” only if it schedules/retries. |
| Dedicated workspace root migration | **KEEP** | Cleanest fix for duplicated MCP scope and reduces RAM waste. |
| Junction workspace for convenience | **MODIFY** | Useful only as a curated bridge; risks loops and duplicate identities if used broadly. |
| Remove global `.cursor\mcp.json` | **REJECT** | Breaks MCP everywhere else; a fragile local hack. |
| End-of-sync drift check with `DRIFT:CRITICAL` sentinel | **KEEP** | Cheap, read-only, low noise; directly targets silent bridge loss. |
| Always-on supervisor tree / new daemonized control plane | **REJECT (for now)** | Net complexity + RAM tax; violates the “don’t add more moving parts” principle under chronic memory pressure. |

---

## Ranked 5 actions (highest leverage first; no implementation here)
1) **Adopt dedicated workspace root** as the default open folder; reserve home-root opens for emergencies only.  
2) **Codify “artifact quarantine + pointer notes”** for large/generated artifacts (workspace + vault), using the already-proven pattern from the session catalog incident.  
3) **Define the micro‑contract:** kernel writer lock + \(N\) heavy-slot locks; forbid queueing/retries inside the contract.  
4) **Define drift health as one sentinel:** `DRIFT:CRITICAL` post‑sync for contract breaks, with strict mode opt‑in + persistence + grace windows.  
5) **Document the WSL reconsideration threshold** explicitly so it doesn’t resurface as a default “offload” myth.

---

## Top surviving architecture (Round‑2)
**Windows-native supervised services + pointer-note discipline + dedicated workspace root + kernel-lock micro‑contract + read-only drift sentinel.**

This architecture is intentionally “boring”:
- it reduces RAM pressure rather than relocating it,
- it preserves semantic memory by avoiding pathological inputs,
- it prevents twin writers without building a scheduler,
- it makes drift impossible to miss without turning health into a noisy pager.

---

## Bold idea killed (and why)
**Killed:** **WSL+systemd as the primary local control plane.**  
**Why:** On this machine it’s likely a *false offload* (host RAM/commit via `vmmem`) with a worse failure domain (observed VM restarts). The evidence shows we can get most benefits (supervision, stability) via Windows tasks + guards, and “real offload” requires off-box resources, not WSL.

---

## Confidence
**0.74** overall. High confidence on rejecting “permanent vector-disable” (evidence contradicts) and rejecting WSL-as-offload (constraints + observed restarts). Medium confidence on the exact strict-mode/grace windows (tuning depends on how often sync runs and boot-time link materialization behaves under RAM pressure).
