# Council: Agent-orchestration reliability (Cluster A)

**Date:** 28.08.2026 · **Host:** Miky, Windows, ~31.6 GB RAM with chronic ~1.8 GB free
**Mode:** discovery / decision only — nothing implemented, no config edits
**Grill modes used:** expansion + red-team + simplification + prioritization
**Council:** Architect · Skeptic · Pragmatist · Critic · Security · Chief-of-Staff · Wildcard/Creative
**Method note:** voices were written **in-process and independently first**, then one adversarial cross-round. The council skill's "launch fresh subagents" step was **deliberately not taken** — spawning 4–6 council workers to debate "don't spawn 4–6 workers" would re-enact Issue 1 and violate G-36 (one `cursor-agent` process). Anti-anchoring is preserved by recording the Architect position *before* the other voices, and by keeping raw dissent visible.

**Confidence in this memo: 0.68.** Highest uncertainty is the *causal mechanism* of "mass cancellation" (see Premise check). Recommendations that do not depend on that mechanism are more robust than those that do.

---

## Premise check (read this first)

The prompt says launching 4–5 heavy subagents with ~1.8 GB free causes "the OS/harness to kill them en masse." That sentence conflates three different machines:

| Hypothesis | What would be true | Evidence |
|---|---|---|
| **H1. Windows OOM-killed them** | NT has a Linux-style OOM killer | **FALSE.** Windows does not overcommit the way Linux does and **has no OOM killer**. When commit charge hits the commit limit, *allocations fail*; processes crash only if they treat `malloc`/`VirtualAlloc` as infallible. `[A.corrob x2.2011+]` Russinovich *Pushing the Limits of Windows: Virtual Memory*; Schöner 2024 *Running out of memory*. |
| **H2. Thrash-watchdog / IPC death** | Working-set trim + pagefile I/O makes agents so slow the harness marks them canceled while the process is still alive | **PLAUSIBLE and matches Issue 2.** Working-set trim is automatic and does not reduce commit charge. SuperUser / Russinovich: Available RAM ≠ commit headroom. |
| **H3. Harness batch abort / composer-index loss** | Parent UI drops the composer record (`composer not found` / `Background composer not found` / `No resource accessor found for composer`) while the child keeps writing | **DOCUMENTED as a Cursor failure class**, not proven for today's 8 cancels. Cursor forum: local→cloud handoff `Background composer not found`; post-update `No resource accessor found for composer: <uuid>`. Resume-by-id is a *composer/session index* lookup, not a process liveness probe. |
| **H4. Cyber-safeguard kill** | Anthropic real-time classifier aborts the *API turn*; local process may linger | **DOCUMENTED** for Opus/Sonnet. Anthropic Help Center; Claude Code issues #65574, #84352 (subagent dispatch often **does not inherit** CVP exemption). |
| **H5. Retry storm** | Parent sees "canceled" → relaunches N copies → RAM/commit/IPC collapse → more cancels | **INFERRED** from Issues 1+2 together. Classic SRE retry-amplification. Not disk-verified for today's incident. **UNVERIFIED.** |

**Council consensus on the premise:** do not build an "anti-OOM-killer." Build (a) **admission/backpressure** so we never stampede, (b) **liveness truth** so we never relaunch a living writer, (c) **scope hygiene** so Claude workers are not classifier-killed mid-sweep. A static "cap at 4–6" treats a number, not a control loop.

**Windows metric trap:** `Available MBytes ≈ 1.8 GB` is *physical* headroom. The thing that makes allocations fail is **commit charge vs commit limit** (RAM + pagefile). An admission gate that only reads Available MBytes can both over-admit (commit exhausted, RAM looks fine) and under-admit (RAM trimmed, commit plenty). `[A.corrob x2]` Russinovich; SuperUser commit-charge threads.

---

## Grounded facts (tooling / APIs)

Claims below are cited. Anything not corroborated is tagged **UNVERIFIED**.

### Cursor (IDE Task tool)

- Subagents can run **foreground** (block) or **background** (return immediately). Parallel launch = multiple Task calls in one parent message. Source: [Cursor subagents docs](https://cursor.com/docs/subagents).
- **No documented user-settable concurrent-subagent cap** analogous to Claude Code's env var. Forum reports a **batch-and-wait of ~4** (next batch waits for the *entire* previous batch). `[B.corrob x2.2026]` Cursor forum thread *Parallel subagents: next batch waits…*; Cursor official docs only say "run simultaneously" — the "4" is **community-observed, not an official knob**. **UNVERIFIED as a hard product limit.**
- Default: subagents **share the parent's checkout**. Isolation is opt-in: each subagent can get a **git worktree** (same machine) or a **cloud VM**. Source: same docs, *Isolated project copies*.
- **Cloud subagents** run on their own VM/branch; local MCP servers are **not** inherited (team config at cursor.com/agents instead). Source: same docs.
- Resume: each execution returns an **agent ID**; `resume` continues that conversation. Background output dir: `~/.cursor/subagents/`. Source: same docs.
- Resume is **buggy / index-fragile**: model on resume can fall back to parent; `resume: "self"` is rejected; local→cloud handoff can 404 as **Background composer not found**. `[B.corrob x2.2026]` Cursor forum threads. **"Composer not found" while a process still edits is consistent with UI/index ≠ OS process.**
- G-36 lock (**1 `cursor-agent` CLI process**) is **not** the same axis as IDE Task subagents. Do not silently relax G-36; do not pretend G-36 already caps IDE Tasks.

### Claude Code (separate runtime)

- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` default **20** since v2.1.217; extras **fail with `Concurrent subagent limit reached`** and the error tells Claude **not to retry**. `[A.corrob x2.2026]` [env-vars](https://code.claude.com/docs/en/env-vars); [sub-agents § concurrent limit](https://code.claude.com/docs/en/sub-agents#concurrent-subagent-limit).
- **Resume of a finished subagent takes a fresh slot without checking the limit** — resumes can push the running count *past* the cap. Same official page. This is a load-bearing footgun for Issue 1+2.
- `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` was **removed in v2.1.224** (now a no-op). Same env-vars page. Older blog posts still citing "200 per session" are stale.
- Setting the Claude Code env var **does not bind Cursor IDE Task launches**. Different products.

### Windows Job Objects / locks

- `SetInformationJobObject` + `JOB_OBJECT_LIMIT_JOB_MEMORY` / `PROCESS_MEMORY` **fails later allocations**; it does **not** reclaim already-committed memory. `AssignProcessToJobObject` does not retroactively account memory allocated before join. `[A.corrob x2]` [JOBOBJECT_EXTENDED_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information); StackOverflow / MSDN `AssignProcessToJobObject` remarks.
- **Notification** limits (`JobObjectNotificationLimitInformation`) can signal without hard-killing. Same MSDN family.
- Kernel-backed liveness: Unix `flock`/`fcntl` F_WRLCK; Windows **`LockFileEx(LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY)`**. Kernel releases the lock when the owning handle/process dies (including `TerminateProcess`). PID-only files are vulnerable to **PID reuse**. `[A.corrob x2]` [LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex); daemon lockfile literature (`fcntl`/`flock` + PID).

### Agent-mail (already on this box, `:8812`)

- `register_agent` bumps `last_active_ts` (social heartbeat, **not** OS liveness).
- `file_reservation_paths` = **advisory** leases (TTL ≥ 60s, glob conflicts). Server-side enforcement is for mail-archive paths; **code-repo enforcement is the pre-commit guard**, i.e. not kernel-mandatory for arbitrary source trees.
- `whois` is a profile lookup, not a process probe.

### Anthropic cyber safeguards

- Real-time classifier on **Opus and Sonnet only**. Two buckets: *prohibited* (never liftable via CVP) and *high-risk dual-use* (CVP may lift). `[A.corrob x2]` [Anthropic Help Center](https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude-opus-and-sonnet) (two URLs, same article).
- **Cursor is a third-party platform.** CVP: "Not all platforms participate… reach out to your platform." Applying CVP on claude.ai **does not reliably propagate to Cursor/Claude Code subagent API calls**. `[B.corrob x2.2026]` Help Center "third-party platform" row; GitHub `anthropics/claude-code#84352` (CVP on parent, default safeguard on Task spawn).
- False-positive blocks can **halt a whole fan-out with no resume**, tokens already billed. `#65574`.

### Congestion-control analog (for Issue 1)

- TCP **AIMD**: add ~1 MSS per RTT in congestion avoidance; **halve** `cwnd` on loss. `[A.corrob x2]` RFC 5681; RFC 2581/2001 lineage.
- Kubernetes **ResourceQuota** rejects at admission when quota is gone (Pending vs crash). `[A.corrob x2]` Kubernetes ResourceQuota docs; KEP-5465 (deferred quota — admit intent, bind later). The lesson: **queue, don't kill**.

### Standing locks that bound this cluster

- G-4: success metric is **≥8 GB free RAM for a week**.
- G-26: `agent worker start` forbidden while free RAM < 8 GB.
- G-27: local `--print` cap 1; **Cloud Agents sanctioned for long/parallel work, per-job owner invocation**.
- G-36: **one** `cursor-agent` process.
- G-68: background/headless agents **never commit**.
- Anti-overfit: no 2nd orchestration runtime / vector-DB / observability SaaS / trained critic / OpenRouter MCP / LiteLLM unless flagged **CHALLENGES STANDING DECISION**.

---

## Independent voices (round 1 — written before cross-rebuttal)

### Architect (initial position, recorded first)

**Issue 1.** Replace the static 4–6 cap with a **feedback controller**: concurrency `cwnd` starts at 1 under <8 GB free, +1 after a clean completion, ×0.5 on cancel/IPC-loss, floor 1. Gate on **commit remaining first, Available MBytes second**, with **hysteresis** (launch only above a high watermark; pause below a low one) so we do not flap with Cluster B's daemon. Do **not** Job-Object the Cursor Electron tree — we do not own spawn, and hard memory limits turn allocation failures into crashes. A 20-line PreToolUse/policy check is a **probe**, not an orchestration runtime.

**Issue 2.** Harness status is a rumor. Truth = **kernel lock + PID + `Get-Process`**. Before any relaunch: if the lock is held or the PID is alive, **do not spawn a twin**. Collision safety by construction: **one mutating agent per worktree**; parallel mutants use Cursor's native isolated worktrees (or cloud VMs). Agent-mail reservations are the courtesy layer, not the mutex.

**Issue 3.** Harness-wide sweeps must be **Glob-of-names, never Read-of-bodies** on dual-use trees. Standing prefix denylist. Sanitize titles. Do not CVP-shop a Cursor third-party path. Do not "route around" the classifier by feeding the same exploit-adjacent bodies to another model — that is policy evasion, not hygiene.

**Main risk of this path:** we might under-parallelize and the owner feels the box is "idle" while `cwnd=1`. That is the correct feeling at 1.8 GB free.

### Skeptic

**Position:** The problem is not concurrency knobs. The problem is **fan-out as a default personality**. Eight canceled workers is what you get when the orchestrator treats "more agents" as "more progress" on a machine whose G-4 metric is 8 GB free and whose current free is 1.8 GB.

**Reasoning:**

- Windows did not "kill a fleet." Something *declared* them dead. Issue 2 is the same bug as Issue 1.
- Claude Code's native cap is 20 — useless here, and **resumes bypass it**. Cursor has **no official cap**. Setting `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=2` is cargo-cult if today's deaths were IDE Tasks.
- Simplest credible alternative: **zero extra writers**. Parent does Glob/name inventory. One worker if implementation is required. Cloud only when the owner types it (G-27).

**Risk:** the owner has a multi-agent identity and will ignore "just don't." Then the static cap comes back as a backdoor fan-out.

**Surprise:** Cluster B (home-as-workspace doubling MCP mounts) may dominate RAM more than the 5th subagent. Admission control without that fix is a leaky bucket under a bigger tap.

### Pragmatist

**Position:** Ship **policy in AGENTS.md today**, code later if the policy is obeyed and still fails. Four rules: (1) if free < 4 GB, no new Task; (2) max **2** in-flight Tasks, **1** writer; (3) before relaunch, `Get-Process` + read `~/.cursor/subagents/` mtime + agent-mail `whois`; (4) harness sweeps = Glob names, exclude `hexstrike|malware|exploit|jailbreak|frida|ghidra|ida` path prefixes.

**Reasoning:**

- File reservations already exist. Use them. Isolated worktrees already exist. Ask for them when two writers are actually needed.
- Job Objects, fleet supervisors, and AIMD daemons are next-quarter toys. Retry-storm stop is a paragraph.
- G-27 already bought Cloud for parallel. Use it **when the owner invokes**, don't build a private k8s.

**Risk:** policy that agents don't read is wallpaper. Today's workers already ignore G-36's spirit.

**Surprise:** `~/.cursor/subagents/` is an official progress surface the parent is not using before relaunch. Free.

### Critic

**Position:** Every clever control loop has a failure mode that **recreates zombies**.

**Reasoning:**

- JSON heartbeats and semaphore files go stale under the exact RAM pressure they are meant to police (transcript-flush lag is already doctrine). A "live" registry that wasn't fsynced is Issue 2 with extra steps.
- Job-Objecting Cursor's tree will crash Electron when a child allocates; notification jobs we cannot attach to children we didn't spawn.
- Isolated worktrees **double** working sets — they *add* RAM cost to buy merge-safety. On 1.8 GB free that is a footgun.
- Cloud subagents lose local MCP (Cluster C's entire subject). Silent offload = silent bridge loss.
- Agent-mail `:8812` as the liveness bus dies when RAM dies. Circular.
- Exclusion manifests rot; a new `cyberstrike` folder appears tomorrow; Claude still eats a jailbreak-titled session.

**Risk:** we "fix" cancellation by making agents immortal (no abort path), then the double-editor is guaranteed.

**Surprise:** Claude Code **resume bypasses the concurrent cap**. If anyone copies Claude Code's resume pattern into Cursor, Issue 1 gets a second turbocharger.

### Security

**Position:** Issue 3 is not a UX annoyance. **Do not weaken, jailbreak, or vendor-shop the classifier.** Issue 2's living "dead" agent is an **unsupervised writer** — a safety incident, not just a git incident.

**Reasoning:**

- Dual-use *reads of exploit/malware skill bodies* during a "harness inventory" are exactly the high-risk class the classifier is for. Name-only inventory is legitimate; body-read is dual-use.
- CVP is for verified defensive *offensive-tooling* work. A sweep of skill folders is not that. Cursor may not even participate.
- Routing the same bodies to Codex/Grok to "keep the sweep productive" is **safeguard shopping**. Different vendors, still dual-use content, still on this disk. Allow only **filename lists**.
- Advisory file reservations are not a security boundary. Two writers on one tree is a data-integrity fail.

**Risk:** an exclusion manifest that is implemented as "skip security skills" also skips the owner's *legitimate* RE work when he actually wants it — so the denylist must be **sweep-scoped**, not global.

**Surprise:** **session titles** with `exploit`/`jailbreak`/`malware` are a self-inflicted classifier feature. Rename chats. Cheap. No standing-decision conflict.

### Chief-of-Staff

**Position:** Sequence for the owner, not a platform.

1. **Stop the bleed today:** no fan-out while free < 8 GB (align G-4/G-26); no relaunch without a process check; no RE-folder Reads in sweeps; no "jailbreak" in titles.
2. **Diagnose this week's 8 cancels:** H2 vs H3 vs H4. One incident receipt (PIDs, commit charge, whether `~/.cursor/subagents/` kept growing after "canceled").
3. **Only then** a tiny admission hook if policy is ignored.
4. Do not wait on Cluster B/C to start (1). Do not invent a supervisor that Cluster C then has to drift-check.

**Risk:** Cluster A builds a fleet supervisor, Cluster B moves the workspace, Cluster C adds a bridge watcher — three new moving parts on a box whose problem is too many moving parts.

**Surprise:** G-27 already decided Cloud is the parallel off-ramp. The missing owner question is "will you click Cloud for the next 5-way council, or do you want local serial?" Not "should we invent Kueue."

### Wildcard / Creative

**Position:** Steal from congestion control, biology, and batch systems — **not** from "another agent runtime."

**Non-obvious options (steelman):**

1. **Control variable is commit remaining, not Available MBytes.** (Windows truth.)
2. **AIMD `cwnd`** for in-flight agents, with **slow-start** after idle (RFC 5681 analog). Cancel = loss.
3. **Bulkheads:** three pools with separate budgets — *readonly explore*, *mutating edit*, *research/MCP-heavy*. A research stampede must not consume the sole writer slot.
4. **Hysteresis / Schmitt trigger** shared with Cluster B: launch >6 GB, pause <3 GB (numbers illustrative). Prevents flap.
5. **Apoptosis / sporulation:** on low watermark, agents **checkpoint to disk and exit** instead of being declared canceled while still writing. Cooperative yield.
6. **Treat "canceled" as SIGSTOP, not SIGKILL.** Frozen-or-alive check; resume the same ID; never twin.
7. **K8s Pending, not CrashLoop:** admission returns "queued" to the parent (don't retry). Parent's next turn sees the queue.
8. **Quorum sensing:** a RAM-seconds lease file; no lease, no launch. Kernel lock = the autoinducer.
9. **One serial merge node, N cloud mutants.** Local box is git-merge + owner; parallel lives on Cursor Cloud VMs (already paid product). Local RAM is for the IDE, not the fleet.
10. **Don't use agents for harness sweeps at all.** A 15-line Python/`Get-ChildItem -Name` inventory is immune to cyber-safeguards, cheaper than any exclusion manifest, and cannot double-edit.
11. **NtSuspendProcess freezer** (Windows analog of cgroup freezer) for low-priority agents — **probably a trap** (MCP timeouts, deadlock). Listed to be killed in red-team.
12. **Pagefile as shock absorber vs fail-fast.** More pagefile raises commit limit (fewer allocation failures) but worsens thrash (more H2 timeouts). **Must diagnose H1 vs H2 first.**

**Risk:** falling in love with AIMD and shipping a daemon. The creative core fits in a policy paragraph plus one lockfile.

---

## Adversarial cross-round (one round)

| Attack | Rebuttal / revision |
|---|---|
| **Skeptic → Architect:** AIMD still assumes fan-out is good. At 1.8 GB the correct `cwnd` is 0 extra writers. | Architect **accepts for current RAM**. AIMD's floor under G-4-failing conditions is **1 total agent (the parent)**. `cwnd` only climbs after G-4 holds. The algorithm is for *after* recovery, not *instead of* serial. |
| **Critic → Pragmatist:** "Check a JSON semaphore" is Issue 2. | Pragmatist **revises:** the mutex must be **`LockFileEx`**, not JSON. JSON may *annotate* (agent id, worktree, purpose). Kernel lock is truth. |
| **Security → Wildcard "route dual-use reads to Codex/Grok":** safeguard shopping. | Wildcard **retreats.** Filename/Glob inventory on *any* model is fine. Body-reads of exploit/malware/hexstrike skills during a *harness sweep* are out, all vendors. Owner-initiated RE work is a different task with a different title and a human at the wheel. |
| **Critic → Architect Job Objects (implicit leftover):** | All voices **reject** Job Objects on the Cursor process tree. Cluster B may still Job-Object **basic-memory** because they own that spawn — different process, don't nest it inside Cursor's job. |
| **Chief-of-Staff → Wildcard supervisor:** new runtime / new always-on. | Wildcard **draws the line:** a PreToolUse/policy check + lockfile is a **kubelet-style probe**, not Temporal/LangGraph. If it schedules DAGs, owns the agent loop, or stays resident as a daemon, it has crossed into a 2nd orchestration runtime (**anti-overfit, do not**). |
| **Skeptic → Cloud offload:** G-27 says per-job **owner** invocation; auto-offload challenges a lock. | Architect **revises:** recommend **owner-invoked** Cloud for parallel clusters (already standing). Do **not** auto-`environment=cloud` from a parent. Flag any silent offload as **CHALLENGES G-27**. |
| **Critic → isolated worktrees:** they cost RAM. | Architect **agrees.** Isolation is for **≥2 writers**, which we should almost never have locally. Prefer 1 local writer; isolation or Cloud only when parallelism is actually required. |
| **Security → exclusion manifest rot:** | Pragmatist **adds:** prefer a **positive sweep allowlist** (e.g. `.agents/scripts`, `.agents/hooks`, `AGENTS.md`) plus a small denylist for known dual-use skill prefixes. Allowlist doesn't rot as fast. |
| **Architect → Claude Code env cap as the fix:** | Skeptic **wins.** Wrong runtime. Optional hygiene for Claude Code sessions (`=2`) but **not** the Issue 1 fix for Cursor IDE. |
| **Wildcard apoptosis vs Security unsupervised writer:** | If an agent is told to yield, it must **release the kernel lock** on the way out. A yield that keeps the lock is a deadlock; a yield that doesn't check the lock is a twin. |

**Consensus after the fight:**

- Stop retry-storm and extra writers **today** (policy).
- Liveness = kernel lock + PID, harness status is rumor.
- Sweeps = names, not bodies; titles matter.
- AIMD/hysteresis is the *medium-term* local controller, floor 0 extra at current RAM.
- Cloud is the *parallel* controller, owner-invoked (G-27).
- No new daemon, no Job-Object-on-Cursor, no CVP-for-inventory, no classifier bypass.

---

## Issue 1 — Mass cancellation under RAM pressure

**Baseline to beat:** naive cap at 4–6 concurrent subagents.

### Ranked options

| Rank | Option | Tradeoffs | Value×effort | Reversibility | Notes |
|---|---|---|---|---|---|
| **1 REC** | **Serial-under-pressure + AIMD later + retry-storm ban.** While free RAM < 8 GB (G-4) or Available < ~4 GB: **no new Task**. `cwnd` floor = 0 extra. After G-4 holds: start `cwnd=1`, +1 on clean finish, ×0.5 on cancel, cap well below 4. Gate on **commit remaining** then Available MBytes, **hysteresis** (two thresholds). Parent must **not relaunch** a canceled id without Issue 2's liveness check. | Slower parallelism until the box recovers. Agents may ignore policy (same as today). AIMD numbers need one week of receipts. | **High × Low** (policy now); Med×Med if a later 20-line probe script | Full (policy paragraph). Script optional and deletable. | Not a daemon. Not a 2nd runtime. |
| 2 | **Static cap = 2** (not 4–6) aligned with G-26/G-36 spirit; 1 writer + 0–1 readonly. | Still a magic number; over-admits if each Task is huge; under-uses Cloud. Better than 4–6, worse than a control loop. | High × Very low | Full | Acceptable **interim** if AIMD feels too cute. Dissent: Skeptic says even 2 is greed. |
| 3 | **Owner-invoked Cursor Cloud subagents** for any job that wanted 4–5 local workers. Local parent stays serial. | Loses local MCP (Cluster C); secrets/MCP surface is team-config; G-27 already allows this **per-job owner**. Latency, cost, and "not on my disk" feel. | High × Low (product exists) | Full (don't click Cloud) | **Does not challenge G-27** if owner-invoked. Challenges G-27 if the parent auto-sets `environment=cloud`. |
| 4 | **Tiny admission probe** (script/hook): read `\Memory\Available MBytes` **and** commit charge/limit, count kernel locks, refuse Task. No queue daemon — parent sees refusal and waits. | Hooks may not exist/fire for Cursor Task the way Claude `PreToolUse` does. **UNVERIFIED** whether Cursor exposes a blockable Task-spawn hook. Failure-open required (doctrine). | High × Med | High (delete hook) | Only if policy is ignored. Don't start here. |
| 5 | **`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=2`** | Correct product, wrong process — **Cursor IDE Tasks ignore it**. Resume can still exceed it on Claude Code. | Low × Very low (wrong target) | Full | Optional hygiene for Claude Code sessions only. |
| 6 | **Windows Job Object on Cursor.exe / agent children** | Hard limits → allocation failure → crash (H1 induced). Can't attach to children we didn't create. Notification-only jobs need a watcher (new always-on). | Negative × High | Med | **Reject** for Cursor. (Cluster B wrapping *basic-memory* is a different spawn they own.) |
| 7 | **NtSuspendProcess / freezer** for overflow agents | MCP timeouts, deadlocks, "frozen but holding locks," looks canceled to the parent. | Negative × Med | Med | Wildcard listed it to kill it. **Reject.** |
| 8 | **Pagefile grow or shrink** | Grow: higher commit limit, more thrash (hurts H2). Shrink: fail-fast allocations (hurts if H1). | Unknown × Low | Full | **Diagnose H1 vs H2 first.** Do not tune blind. |
| 9 | **Fleet supervisor daemon / k8s-on-the-box / jobmon-as-orchestrator** | 2nd orchestration runtime. Cluster C drift surface. RAM cost of the watcher. Anti-overfit. | Negative × High | Low | **Reject** unless someone writes a compelling CHALLENGES brief. This memo does not. |
| 10 | **Skeptic pure: never fan out on this box** | Maximum reliability, minimum throughput. Conflicts with "multi-agent partner" identity; Cloud is the escape hatch. | High reliability × Low | Full | **Strongest dissent** to Rank 1's "AIMD later." |

### Recommended pick (Issue 1)

**Rank 1:** ban extra Tasks while G-4 is failing; ban relaunch-without-liveness; use AIMD+hysteresis+commit-charge *after* RAM recovers; Cloud for real parallelism (owner click, G-27).

**Strongest dissent (Skeptic):** AIMD is a delayed permission slip to stampede again. Permanent local `cwnd=0` extra, Cloud or serial forever, until the *machine* is bigger — not until a counter says 8 GB for a week.

**Value×effort of REC:** High × Low. **Reversibility:** full.

---

## Issue 2 — "Dead" agents that are still alive + unsafe concurrent editors

### Ranked options

| Rank | Option | Tradeoffs | Value×effort | Reversibility |
|---|---|---|---|---|
| **1 REC** | **Liveness = kernel lock + PID + `Get-Process`.** Each mutating agent acquires `LockFileEx` on a per-worktree (or per-shard) lockfile, writes PID+agent-id as *annotation*, keeps the handle open. Relaunch protocol: try non-blocking lock; if fail, **the twin is alive — resume or wait, never spawn.** If lock succeeds, previous holder is dead even if JSON says live (kernel released it). Composer-not-found **does not** mean dead. | Requires agents to actually take the lock (policy + maybe a 15-line helper). PID reuse is neutralized by the lock, not by the PID. Lock on a network FS would be wrong — keep it local NTFS. | **High × Low–Med** | Full (stop taking locks) |
| 2 | **Treat canceled as suspend.** Never relaunch by default. Inspect `~/.cursor/subagents/` mtime, process list, lock. Resume-by-id if the composer index still has it; if index is gone but process lives, **do not start a second editor** — notify owner. | Resume API is fragile (`composer not found`, model-on-resume bugs). May leave orphans until owner kills them. Needs a documented kill path (`Stop-Process` by PID from the lockfile). | High × Low | Full |
| 3 | **Collision safety: 1 local writer.** If two edit jobs: Cursor **isolated worktrees** or Cloud VMs; parent merges. Never two Tasks on the shared checkout. | Worktrees cost disk + some RAM (Critic). Merge conflicts still exist but are git's problem, not silent overwrite. | High × Low (docs already support "ask for isolation") | Full |
| 4 | **Agent-mail `file_reservation_paths` + `register_agent` heartbeat** | Already built. **Advisory.** `:8812` may be down under RAM. Complements Rank 1, does not replace it. `last_active_ts` can be stale (flush lag). | Med × Very low (use existing tools) | Full |
| 5 | **JSON registry of running agents** (central file, no kernel lock) | Exactly the stale-file bug. Transcript-flush lag doctrine. | Low × Low | Full | **Reject as SoT.** OK as a *display* sidecar. |
| 6 | **`tasklist` / WMI of `node` children without a lock** | PID reuse; Cursor has many node processes; false live/false dead. | Low × Low | Full | Probe only, never SoT. |
| 7 | **Always isolate every subagent in a worktree** | RAM/disk multiplier on a starved box. Makes Issue 1 worse. | Negative locally × Med | Full | Use **selectively**, not as default. |

### Recommended pick (Issue 2)

**Rank 1 + 2 + 3 as a bundle:** kernel lock is SoT; canceled ≠ dead; one writer per checkout; isolation/Cloud only when a second writer is real.

**Strongest dissent (Critic):** a lock protocol agents forget is theater; the only robust fix is **never two Tasks**, which is Skeptic's Issue 1 again. Also: an agent that crashes without closing handles relies on OS lock release — Microsoft notes unlock after process exit can take time (`LockFileEx` remarks). Brief windows of "lock held after death" will cause false "still alive" and block relaunch. Mitigate with PID check: lock held AND pid dead → wait-and-retry, don't spawn immediately.

**Composer-not-found:** treat as **index loss**, not process death. Check OS + lock + `~/.cursor/subagents/`. `[B.corrob x2.2026]` Cursor forum composer-not-found classes.

---

## Issue 3 — Cyber-safeguard blocks on harness-wide sweeps

### Ranked options

| Rank | Option | Tradeoffs | Value×effort | Reversibility |
|---|---|---|---|---|
| **1 REC** | **Sweep without agents, or with Glob-names only.** Allowlist the trees a harness sweep may touch (hooks, scripts, `AGENTS.md`, non-RE skills). **Denylist prefixes** for dual-use skill folders (`hexstrike`, `malware`, `exploit`, `jailbreak`, `frida`, `ghidra`, `ida`, `cyberstrike`, `gtfobins`, `hacktricks`, …). **Never Read skill bodies** in those trees during a sweep. Inventory = filenames + `SKILL.md` titles via Glob, not contents. Sanitize **chat titles** (no exploit/jailbreak/malware). | Incomplete inventory of RE skills (by design). Owner must run a *separate, titled, human-driven* session for real RE work. Denylist will miss a newly cloned folder until updated — hence allowlist-primary. | **High × Very low** | Full |
| 2 | **Don't spawn sweep workers at all.** Parent (or a 15-line `Get-ChildItem`) lists names. Immune to Opus/Sonnet classifier on that turn. | Less "agentic." Fine. | High × Very low | Full | Simplification-mode winner. Compatible with Rank 1. |
| 3 | **Framing as inventory-by-name** when a worker is unavoidable | Helps, not a guarantee. Classifier is real-time on content, not just the system prompt. Session title + file contents both count. | Med × Very low | Full | Necessary but insufficient alone. |
| 4 | **Route dual-use *filename* lists to Grok/Codex** (non-Opus/Sonnet) | Extra hop. Still don't Read bodies. Does **not** bypass policy if we keep to names. Using them to Read exploit bodies = **safeguard shopping** (Security veto). | Low–Med × Low | Full | Allowed for **names only**. |
| 5 | **Apply to Anthropic CVP** | Cursor = third-party; may not participate. CVP often **does not propagate to Task/subagent API**. Inventory work is a weak CVP use case. Prohibited class never lifts. Identity verification. | Low for *this* issue × Med | Low (org-tied) | Not the sweep fix. Revisit only if the owner does **ongoing dual-use RE** on Claude and hits legitimate defensive blocks. |
| 6 | **Disable / jailbreak / prompt-around the safeguard** | Violates Anthropic usage policy and owner ethics. | Forbidden | n/a | **Reject.** |
| 7 | **Move RE skill trees out of the Cursor workspace** (pairs with Cluster B dedicated workspace root) | Sweep never sees them; RE work opens a different folder. Reduces accidental Reads *and* classifier context. | High × Med (depends on Cluster B) | Med | Flag as **interaction**, not a Cluster A solo. |

### Recommended pick (Issue 3)

**Rank 1 + 2:** allowlisted, name-only, preferably **no worker**. Titles cleaned. Bodies of dual-use skills are out of band.

**Strongest dissent (expansion-minded Wildcard, weakened in cross-round):** "productive harness sweep" means *reading* skill bodies to detect drift. Name-only will miss a skill whose filename is innocent and whose body is dual-use. **Answer:** that miss is acceptable for a *standing* sweep; a human-titled RE audit is the place to Read bodies, on a runtime and with a purpose that match the work — not as a background cluster.

**Do not** recommend Codex/Grok as a stealth Read path.

---

## Creative / non-obvious options (expansion + better-ideas)

Worth keeping even if not the REC:

1. **AIMD `cwnd` on agent slots with slow-start after idle** — best cross-domain import. Escalate as the local controller *after* G-4 recovers. (RFC 5681 analog.)
2. **Control on commit remaining, not Available MBytes** — Windows-correct; most RAM dashboards are wrong. Escalate as a measurement change even if AIMD is deferred.
3. **Bulkheads (writer / explore / research pools)** — prevents a Firecrawl-heavy research Task from stealing the only safe writer slot.
4. **Canceled = SIGSTOP** — cultural change: inspect, resume, or kill-by-PID; never twin.
5. **Harness sweeps are not an agent job** — `Get-ChildItem -Name` cannot trip cyber safeguards or double-edit. Highest simplification win across Issues 1+3.
6. **Local serial merge node + Cloud mutants** — architecture, not a new runtime. Already standing (G-27) if owner-invoked.
7. **Shared Schmitt trigger with Cluster B** — one hysteresis policy for "don't start heavy things," covering Tasks *and* basic-memory embedding.
8. **Quorum-sensing RAM-seconds lease via `LockFileEx`** — the same file can be Issue 1's admission ticket *and* Issue 2's mutex. One artifact, two problems. **This is the creative idea to escalate** (see Return).
9. **K8s Pending semantics** — a refused Task is queued in the parent's head, not retried. Encode in the prompt: "if you cannot lock, wait a turn; do not spawn."
10. **Explicitly rejected creatives:** NtSuspendProcess freezer; Job-Object-the-IDE; pagefile-as-policy-without-diagnosis; 2nd orchestrator; classifier bypass via vendor shopping.

---

## Cross-cluster interactions (flags only)

### Cluster B — home-as-workspace + basic-memory flap

- **Helps Issue 1 a lot.** Double MCP mounts + 358-skill listings are a RAM tax. Admission control without shrinking the workspace is a bucket under a firehose. Skeptic's strongest external dependency.
- **Shared hysteresis:** whatever Cluster B does for "don't embed when RAM is low" should use the **same watermarks** Cluster A uses for "don't Task." Two independent flap-controllers will beat each other.
- **Job Objects:** Cluster B wrapping **basic-memory** (they own spawn) is coherent. Cluster A wrapping **Cursor.exe** is not. Do not combine into one job.
- **Issue 3:** a dedicated workspace root that **does not include** RE/security skill trees makes accidental dual-use Reads rarer. Cluster A still needs the sweep allowlist because skills also live under `~/.claude/skills` via sync.
- **basic-memory down** (Cluster B) means this council could not persist to the vault; receipts stay in `.agents/` and the project folder.

### Cluster C — sync-time drift-check for lost runtime bridges + "better architecture"

- If Cluster A adds **any** new always-on (supervisor, notification-job watcher, extra HTTP port), Cluster C's drift-check surface grows. **Reason not to add one.**
- Cloud offload (Issue 1 Rank 3) **is** a different MCP plane — Cluster C's "lost bridge" problem in another costume. Owner-invoked Cloud must expect **local MCP not present**.
- Wildcard "fundamentally better architecture" in C may propose leaving this box. Cluster A's Cloud-mutants / serial-merge-node is the **local-compatible** version of that idea. Align rather than both inventing runtimes.
- Agent-mail `:8812` as liveness (Issue 2 Rank 4) is a **bridge**. If Cluster C finds it flapping, do not make it SoT (we already didn't).

---

## Challenges to standing decisions

Only items that actually push a lock. Most recs **honor** the locks.

| Item | Status |
|---|---|
| **Static cap at 4–6** | **Challenge the heuristic, not a numbered G-lock.** Replace with serial-under-pressure + AIMD after G-4. |
| **G-27 Cloud Agents** | **Do not challenge** if owner-invoked. **Would challenge** if parents auto-`environment=cloud`. This memo does **not** recommend silent offload. |
| **G-36 cap 1 `cursor-agent`** | **Do not relax.** Clarify it does not cap IDE Tasks; IDE Tasks get their own RAM rule. |
| **"Run everything on this box"** | Implicit habit, not a G-number. **Soft challenge:** parallel work belongs on Cloud (already G-27) or in serial. Not a new SaaS. |
| **Anti-overfit (no 2nd orchestration runtime / vector-DB / observability SaaS / trained critic / OpenRouter MCP / LiteLLM)** | **Honored.** Probe + lockfile ≠ runtime. Explicitly rejected: jobmon-as-orchestrator, k8s, LiteLLM, new critic model. |
| **G-18 Hexstrike deny-list (reaper)** | Orthogonal (process-reaper vs classifier). Don't confuse "reaper may kill hexstrike dupes at D21" with "sweeps may Read hexstrike skills." |
| **Cluster B's "disable basic-memory vectors"** | Not our lock; if they do it, Issue 1 headroom improves. No challenge from A. |

**No CHALLENGES STANDING DECISION flag is raised for a new runtime.** The only habit to revisit is **local fan-out as the default parallel strategy** — G-27 already named the alternative.

---

## Grill-mode residues (not owner questions — already EVPI-gated as "investigate not ask")

- **Expansion:** sweeps-as-scripts, Cloud mutants, bulkheads, shared hysteresis with B.
- **Red-team:** stale JSON, Job-Object crashes, worktree RAM tax, CVP non-propagation, resume-bypasses-cap, retry storm, classifier shopping.
- **Simplification:** no workers for sweeps; one writer; policy before hooks.
- **Prioritization:** (1) stop relaunch/stampede/RE-Reads today, (2) diagnose H2/H3/H4 on the next incident, (3) AIMD after G-4, (4) optional hook only if policy is ignored.

One incident receipt still worth capturing next time (not a blocker for the recs): PID list, commit charge vs limit, whether `~/.cursor/subagents/` grew after "canceled", and whether the abort string was cyber-safeguard vs composer-not-found vs silent.

---

## Sources

1. [Cursor Subagents](https://cursor.com/docs/subagents) — official; isolation, cloud, resume, `~/.cursor/subagents/`.
2. [Cursor Worktrees](https://cursor.com/docs/configuration/worktrees) — official.
3. [Cursor Cloud Agents](https://cursor.com/docs/cloud-agent) — official.
4. [Cursor forum: parallel subagents batch-and-wait](https://forum.cursor.com/t/parallel-subagents-next-batch-waits-for-entire-previous-batch-to-finish/152681) — community; ~4 batch **UNVERIFIED** as hard limit.
5. [Cursor forum: Background composer not found](https://forum.cursor.com/t/agents-window-local-cloud-handoff-fails-for-gitlab-background-composer-not-found-cloud-native-works-on-web/165803).
6. [Cursor forum: No resource accessor found for composer](https://forum.cursor.com/t/updated-cursor-and-now-its-not-working/166777).
7. [Cursor forum: subagent resume model bug](https://forum.cursor.com/t/subagent-resume-runs-an-incorrect-model/160590).
8. [Claude Code sub-agents — concurrent limit](https://code.claude.com/docs/en/sub-agents#concurrent-subagent-limit) — default 20; resume can exceed.
9. [Claude Code env-vars](https://code.claude.com/docs/en/env-vars) — `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`; per-session cap removed v2.1.224.
10. [GitHub anthropics/claude-code#80082](https://github.com/anthropics/claude-code/issues/80082) — docs gap on concurrent cap (now documented).
11. [JOBOBJECT_EXTENDED_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).
12. [JOBOBJECT_NOTIFICATION_LIMIT_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_notification_limit_information).
13. [QueryInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject).
14. [LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex) — locks released on process termination (delay possible).
15. [Russinovich — Pushing the Limits of Windows: Virtual Memory](https://learn.microsoft.com/en-us/archive/blogs/markrussinovich/pushing-the-limits-of-windows-virtual-memory) — commit charge vs RAM.
16. [Schöner 2024 — Running out of memory](https://blog.s-schoener.com/2024-02-01-ooms/) — NT no OOM killer vs Linux.
17. SuperUser: [commit charge vs available RAM](https://superuser.com/questions/943175/windows-says-ram-ran-out-while-there-is-still-4-gb-of-physical-memory-available).
18. [Anthropic real-time cyber safeguards](https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude-opus-and-sonnet).
19. [Claude Code #84352](https://github.com/anthropics/claude-code/issues/84352) — CVP not propagating to subagent dispatch.
20. [Claude Code #65574](https://github.com/anthropics/claude-code/issues/65574) — false-positive halt, no resume.
21. [RFC 5681 TCP Congestion Control](https://www.rfc-editor.org/rfc/rfc5681.html) — AIMD.
22. [Kubernetes ResourceQuota](https://kubernetes.io/docs/concepts/policy/resource-quotas/).
23. Owner lock record: `~/Cowork/output/grill-proposed-answers_2026-08-27.md` (G-4, G-26, G-27, G-36, G-68).
24. Agent-mail tool descriptors in-session (`register_agent`, `file_reservation_paths`, `whois`) — local MCP `:8812`.

**Providers:** WebSearch, WebFetch, Firecrawl search, Microsoft Learn, Claude Code docs, Cursor docs, RFC, Kubernetes docs. **basic-memory MCP:** down at council time (namespace error) — vault persist skipped. **Cursor-native concurrent cap:** not found in official docs.

---

## Return (executive)

| Issue | Top recommended option | Strongest dissent |
|---|---|---|
| **1 Mass cancel** | No extra Tasks while G-4 fails; no relaunch without liveness; AIMD+hysteresis+**commit-charge** after recovery; Cloud only owner-invoked (G-27). | Permanent local `cwnd=0` extra — never fan out on this box. |
| **2 Dead-alive + collisions** | `LockFileEx` + PID as SoT; canceled ≠ dead; one writer per checkout; isolate/Cloud only for a true second writer. | Don't bother with locks — never two Tasks. Resume APIs are too broken to be a control plane. |
| **3 Cyber blocks** | Allowlisted name-only inventory; preferably **no sweep worker**; never Read dual-use skill bodies in sweeps; clean titles. | Name-only misses stealth dual-use files; (vetoed) vendor-shop Reads. |

**Most creative idea worth escalating:** one **RAM-seconds lease file** with a kernel exclusive lock — the same artifact is Issue 1's admission ticket and Issue 2's mutex (quorum-sensing + `LockFileEx`). No daemon.

**Standing decision to revisit:** the **habit of local fan-out** as the parallel strategy (not G-36, not anti-overfit). G-27 already named Cloud; this cluster says use it or go serial. Do **not** revisit G-36 downward. Do **not** introduce a 2nd orchestration runtime.

**Confidence: 0.68** — recs that are policy-shaped are high-confidence; the causal story of today's 8 cancels is still H2/H3/H5 **UNVERIFIED**.
