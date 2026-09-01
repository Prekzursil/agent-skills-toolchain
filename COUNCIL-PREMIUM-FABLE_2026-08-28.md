# COUNCIL-PREMIUM-FABLE — Integrated End-to-End Plan (2026-08-28)

**Role:** top-effort INTEGRATOR council (single voice, synthesizing rounds 1–2).
**Mode:** discovery/decision only — nothing implemented, no config edits.
**Inputs read:** COUNCIL-ORCH-RELIABILITY_2026-08-28.md (Cluster A) · COUNCIL-STRUCTURAL-MEMORY_2026-08-28.md (Cluster B) · COUNCIL-DRIFT-WILDCARD_2026-08-28.md (Cluster C) · COUNCIL-CROSSCRIT-B_2026-08-28.md · evidence `\.agents\.agents\BASIC-MEMORY-RELIABILITY_2026-08-27.md` and `\.agents\.agents\HARNESS-AUDIT_2026-08-27.md`.
**Evidence gaps:** CROSSCRIT-A and CROSSCRIT-C do **not exist** on disk (Glob, 28.08) — round 2 only adjudicated Cluster B's territory. Clusters A and C therefore stand un-cross-critiqued; I applied the adversarial pass myself below. Also: the two evidence files are NOT at the advertised `\.agents\` root paths but in the nested `\.agents\.agents\` capture folder — itself a small drift datum for Issue 6.

**Confidence in this plan: 0.75.** Basis at the end.

---

## 0. The integrator's frame: one disease, six symptoms

Ranked per-issue lists hide the structure. The six problems are not six diseases:

- **RAM starvation (~1.8 GB free vs G-4's 8 GB target) is the common upstream amplifier** of Issues 1 (mass cancellation), 2 (thrash-slow agents declared dead), and 5 (daemon warm-ups taking 2.5–4 min, embedding stalls). Evidence: BASIC-MEMORY-RELIABILITY shows *zero* Windows OOM/app-crash events during the 27.08 "crash loop" — the kills were our own supervision timing out against RAM-slowed warm-ups. Cluster A's premise check reached the same conclusion for agents (H2/H3, not H1).
- **Issue 4 (home-as-workspace) is not just a config wart — it is a standing RAM tax and a scope confounder.** Live proof in this very session: the dynamic-tool catalog mounts `project-0-Prekzursil-playwright` *and* `user-playwright` simultaneously — duplicate stdio server processes for every stdio MCP, plus the 358-skill list enumerated twice via `C:`/`c:` casing (HARNESS-AUDIT Findings A+B). Fixing 4 *reduces the amplifier* feeding 1, 2, and 5.
- **Issues 2 and 1 share one missing primitive:** a kernel-truth liveness/admission artifact. Harness status is a rumor; `LockFileEx` is not.
- **Issues 3 and 4 share one geometry fix:** a workspace root that doesn't contain the RE/security skill trees makes accidental dual-use body-reads structurally rarer, on top of the name-only sweep policy.
- **Issue 6 is the detection layer for everything else:** if a bridge dies silently, every other fix degrades invisibly. But its design must be written *after* the workspace decision, or it asserts the wrong contract.

So the plan is: **cut demand-side bleeding today (policy), then shrink baseline RAM consumption (workspace), then add the one enforcement primitive (lease/lock), then stabilize memory with what already works (repaired tasks + size policy), then add detection (drift check).** Everything reversible; nothing always-on added.

---

## 1. Resolving the three live disagreements

### 1a. Issue 5: WSL2+systemd offload vs disable-vector-search vs keep-repaired-Windows-tasks
**Verdict: keep-repaired-Windows-tasks + vault size policy, with disable-vector as a pre-committed fallback lever. WSL2 REJECTED for now.**

- The evidence is dispositive and post-dates both round-1 memos' pessimism: BASIC-MEMORY-RELIABILITY (27.08, ~09:00–09:55) root-caused **both** flap mechanisms — (1) a 378 KB session catalog becoming one 1,482-chunk embedding entity that starved the event loop, and (2) launcher/watchdog killing genuinely-warming daemons whose bind takes 2.5–4 min under load. Both were fixed same day (catalog moved out of vault; bind-wait 60→240 cycles; marker re-stamped per cycle so the watchdog defers). The 10-min stability probe passed on one PID *while* the daemon ran a 7.1-min deletion scan that would previously have read as "hung."
- **WSL2 fails the physics test on this box** (CROSSCRIT-B, endorsed): `vmmem` draws from the same starved 31.6 GB physical pool. Moving the daemon into a VM adds baseline VM overhead and a new failure domain (WSL suspend/networking lifecycle) while creating zero new bytes of RAM. Cluster C's Rank-#1 option was written against the pre-fix picture ("it died silently / forgot to start") — that supervision gap is precisely what the repaired scheduled tasks now cover. WSL2's genuine advantage (cgroup containment, systemd supervision quality) becomes worth revisiting only if (a) G-4 is met (≥8 GB free sustained) so the VM tax is affordable, **and** (b) the repaired Windows tasks still flap. Neither holds today.
- **Disable-vector-search (Cluster B's original REC) is retracted as a default but kept as the fallback**, exactly per CROSSCRIT-B's A/B design: run 48 h with semantic search ON under the size policy (no machine-generated files >~100 KB in `D:\basic-memory`); if "bound but HTTP unresponsive" strikes exceed ~3/day in `basic-memory-supervisor.log`, flip `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED=false` for 48 h and compare. This honors the constraint "preserve semantic memory if at all feasible" while pre-committing the exit ramp so nobody relitigates mid-incident.

### 1b. Issue 4: dedicated workspace root vs NTFS junctions
**Verdict: dedicated workspace root. Junctions REJECTED.**

- Junctions solve the wrong layer: they re-expose home content inside a new root, re-importing recursive-search loops and backup-tool confusion (Cluster B Security dissent, CROSSCRIT-B red-team), and they don't clearly fix the `C:`/`c:` casing double-enumeration (HARNESS-AUDIT Finding B) because the resolved targets are still home paths. They also hand Issue 6's drift check a second class of link invariants to assert forever.
- The dedicated root is the only option all three sources independently converge on (Cluster B REC, CROSSCRIT-B verdict, HARNESS-AUDIT Top-action #1). Practical shape: **don't create a new tree — `~\source\` already exists and holds the real projects** (qzp-lean, democracyos…). The rule is behavioral: *never open `C:\Users\Prekzursil` itself as a workspace root*; open the per-project folder (or a thin `~\projects` aggregator if a multi-repo view is wanted). No Cursor logout is involved — this is a workspace-open habit, not an account change.
- **One real migration cost to plan for (flagged, not solved here):** today the always-applied rules are picked up because `~\CLAUDE.md` / `~\AGENTS.md` sit at the workspace root. After migration, rule loading must come from user-level config or ≤10-line pointer files in each project root (the pattern the harness already uses for Goose/Fabric per HARNESS-AUDIT). This must be verified in ONE pilot project before declaring the migration done — it is the likeliest silent regression, and ironically an Issue-6-shaped one.

### 1c. RAM-seconds lease vs broader health surface
**Verdict: false rivalry — they are different layers. Do the lease (enforcement, Issues 1+2) AND the minimal drift check (detection, Issue 6). Reject the status-bar/tray health widget for now.**

- The lease is the only proposed artifact whose truth survives process death by kernel guarantee: `LockFileEx` is released when the holder dies, even on `TerminateProcess` (Cluster A sources; CROSSCRIT-B "brilliant … eliminates the dead-but-alive JSON stale state"). No JSON registry, heartbeat file, or agent-mail `last_active_ts` has that property under the transcript-flush-lag doctrine.
- The "broader health surface" splits in two: the **end-of-sync Bridge Drift Check** (read-only, `DRIFT:WARN` sentinel, banner) is cheap, targets a *proven* silent-skip (the Claude local-bridge merge returns success when `.claude-runtime\...\local-mcp-bridge\.mcp.json` is missing), and adds no resident process — **keep**. The **status-bar extension / tray toast** is a maintained artifact with alert-fatigue risk that fires only when someone runs something anyway — **defer** (CROSSCRIT-B concurs). Revisit only if drift warnings are demonstrably being missed in sync output.
- One caveat the lease's fans undersell (Cluster A Critic, endorsed): lock release after abnormal death "can take time" per Microsoft's own remarks, and adoption is policy-dependent — an agent that never takes the lock is invisible to it. Hence the lease ships **with** the relaunch protocol (lock-held + PID-dead → wait-and-retry, never twin) and stays paired with the day-0 policy, not as a replacement for it.

---

## 2. The sequenced plan

Ordering logic: **risk-free demand cuts first → baseline-consumption cut second → enforcement primitive third → memory stabilization (mostly done, needs policy + A/B) fourth → detection last** (because its assertions depend on step 2's outcome). Each step is independently shippable and independently reversible; no step requires a later step to be safe.

### S0 — Same-day policy freeze (Issues 1, 2, 3) — DO FIRST
- **What:** One AGENTS.md policy block: (a) **no new Task/fan-out while free RAM < 8 GB** (align G-4/G-26; gate on *commit remaining* first, Available MBytes second, per Cluster A's Windows-metric trap); (b) **canceled ≠ dead** — before any relaunch: `Get-Process` on the recorded PID + `~/.cursor/subagents/` output-mtime check; if either says alive, resume or wait, never spawn a twin; (c) **harness sweeps are name-only** — Glob/`Get-ChildItem -Name` against a positive allowlist (`.agents\scripts`, `.agents\hooks`, `AGENTS.md`, non-RE skills), never Read bodies under dual-use prefixes (`hexstrike|malware|exploit|jailbreak|frida|ghidra|ida|cyberstrike|gtfobins|hacktricks`); (d) **sanitize chat/session titles** (no exploit/jailbreak/malware strings).
- **Solves:** stops the acute bleeding on 1 (retry storms), 2 (twin spawns), 3 (classifier kills) with zero new machinery.
- **Effort:** trivial (one policy edit). **Risk:** agents ignoring policy — the known failure mode; S2 is the enforcement follow-up. **Rollback/reversibility:** revert the paragraph; fully reversible.

### S1 — Workspace-root migration (Issue 4; leverage on 1, 3, 5, 6)
- **What:** stop opening `C:\Users\Prekzursil` as a Cursor workspace. Open per-project roots under `~\source\<project>` (or a thin aggregator folder). Update launch shortcuts. **Pilot on one project first and verify:** rules still load (CLAUDE.md/AGENTS.md pointer strategy), MCP mounts appear once (no `project-0-Prekzursil-*` twins), skill list enumerates once.
- **Solves:** 4 outright (double `mcp.json` scope + `C:`/`c:` skill double-listing — HARNESS-AUDIT Findings A+B). **Reduces** 1/2/5 (kills duplicate stdio MCP processes and double skill enumeration — a permanent RAM/context tax; Cluster A Skeptic: "admission control without this is a leaky bucket under a bigger tap"). **Reduces** 3 (RE skill trees no longer inside the default workspace geometry). **Simplifies** 6 (drift check asserts one unambiguous loading contract).
- **Effort:** low-medium (behavioral + shortcut updates + rules-loading verification). **Risk:** medium — silent loss of always-applied rules or of tooling that assumed home-root paths; mitigated by the one-project pilot. No Cursor logout required. **Rollback:** reopen the home directory as workspace — instant, lossless. **Reversibility:** full.

### S2 — RAM-seconds lease / kernel-lock liveness protocol (Issues 1 + 2)
- **What:** one lockfile artifact per checkout/worktree, held via `LockFileEx(EXCLUSIVE | FAIL_IMMEDIATELY)`, PID + agent-id + purpose as JSON *annotation* (never truth). Protocol: mutating agents acquire before editing; admission = "no lease, no launch"; relaunch = try non-blocking lock → held ⇒ alive (resume/wait), acquired ⇒ predecessor dead regardless of what any status UI says; lock held **and** PID dead ⇒ wait-and-retry (release-delay window), never immediate twin. A ~15-line helper script; **not** a daemon, not a hook yet.
- **Solves:** 1 (admission ticket) and 2 (mutex + kernel-truth liveness) with a single artifact — the highest value-per-artifact idea in all three memos (Cluster A Wildcard #8; CROSSCRIT-B Rank 1).
- **Effort:** low. **Risk:** adoption (policy-dependent until/unless a blocking hook exists — Cursor Task-spawn hookability is UNVERIFIED per Cluster A); lock-release delay after abnormal death (mitigated in-protocol). **Rollback:** delete helper + policy lines. **Reversibility:** full.

### S3 — basic-memory: keep repaired tasks + vault size policy + pre-registered 48h A/B (Issue 5)
- **What:** (a) keep the 27.08-repaired supervision stack exactly as is (`BasicMemory-HTTP-MCP` launcher with 240-cycle bind-wait + marker re-stamp; watchdog two-strike HTTP probe); (b) codify the **vault size policy** — no machine-generated files >~100 KB in `D:\basic-memory`, pointer notes instead (the proven mechanism-1 trigger); (c) run the CROSSCRIT-B A/B: 48 h semantic-ON under the policy, watching `basic-memory-supervisor.log` strikes; >~3 strikes/day ⇒ flip `BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED=false` for a comparison window. (d) **WSL2 offload: rejected** (see §1a) — no CHALLENGES flag needed because we don't do it; revisit condition recorded (G-4 met AND Windows tasks still flapping).
- **Solves:** 5, preserving semantic memory (owner's stated priority) with a pre-committed, evidence-gated fallback instead of a panic switch.
- **Effort:** very low (policy line + observation). **Risk:** low — flap recurrence during normal-note embedding is possible (`batch_size=2` is glacial by design); the A/B is exactly the instrument that catches it. **Rollback:** env flags; everything else already shipped and backed up (`.basic-memory\backups\`). **Reversibility:** full.

### S4 — Bridge Drift Check appended to `sync_shared_state.ps1` (Issue 6; visibility for 5)
- **What:** Cluster C's design, adopted with CROSSCRIT-B's trim: read-only, end-of-run, `DRIFT:WARN`/`DRIFT:OK` sentinel lines + banner, severity-tiered, opt-in strict mode (`AGENTS_DRIFT_STRICT=1`), default exit code unchanged. Priority assertions: **CRITICAL** — Claude local-bridge `.mcp.json` exists/parses/non-empty (the proven silent skip); `.claude\skills` still a link; vault + `agents.json` readable. **HIGH** — `basic-memory`/`agent-mail` present in Codex/Claude/Cursor configs. **MEDIUM** — Cursor 6-server allowlist exact-match; Grok `extra_skill_dirs`/`extra_rule_dirs`. Non-contracted runtimes (Goose/Agy/Fabric) get INFO lines only, to protect signal. **Written after S1 lands** so the Cursor assertions encode the post-migration loading contract, and extended with one new assertion this council earned: root-level receipts land in `\.agents\` proper, not the nested `\.agents\.agents\` capture folder.
- **Solves:** 6 (silent bridge loss becomes loud at every sync); gives 5 a greppable health trail. Status-bar/tray surface deferred (§1c). Supervisor-tree option deferred indefinitely (anti-overfit; only re-open if S3's A/B and S4's warnings show sustained instability the tasks can't hold).
- **Effort:** low-medium (one appended read-only block). **Risk:** alert fatigue if over-asserted — capped by the severity model and the non-contracted-runtime INFO rule. **Rollback:** delete the appended block. **Reversibility:** full.

### Deferred / conditional (explicitly not in the top 5)
- **AIMD concurrency controller** (Cluster A): only after G-4 holds for a week; floor stays 0-extra until then. Cloud parallelism stays owner-invoked per G-27 — never auto-`environment=cloud`.
- **Status-bar health widget; OTP supervisor tree; WSL2 offload:** revisit triggers recorded above.
- **Admission hook (blocking PreToolUse-style):** only if S0's policy is demonstrably ignored after S2 exists; Cursor hookability UNVERIFIED.

---

## 3. Top-leverage single action

**S1, the workspace-root migration.** It is the only step that *permanently removes* load rather than managing it: it deletes the duplicate stdio MCP processes (observed live this session: `project-0-Prekzursil-playwright` + `user-playwright` mounted simultaneously), the double 358-skill enumeration, and the double `mcp.json` scope in one behavioral change — directly fixing Issue 4, shrinking the RAM amplifier behind Issues 1/2/5, narrowing Issue 3's accidental-read geometry, and giving Issue 6's drift check a clean contract. Everything else in the plan manages demand or detects failure; S1 shrinks the machine's standing burn.

(S0 still executes *first* in time because it is free and stops active bleeding — but if only one substantive change is ever made, make it S1.)

---

## 4. Standing-decision ledger

| Decision | This plan |
|---|---|
| No 2nd orchestration runtime | **Honored** — lease is a lockfile + 15-line helper; drift check is an appended read-only block; supervisor tree deferred. |
| No vector-DB / observability SaaS / trained critic / OpenRouter MCP / LiteLLM / Cursor BYOK | **Honored** — nothing here touches them. |
| Preserve semantic memory | **Honored** — semantic search stays ON by default; disable is a pre-registered fallback lever, evidence-gated. |
| No Cursor logout | **Honored** — workspace migration is a folder-open habit, not an auth change. |
| G-27 (Cloud per-job owner-invoked) | **Honored**; auto-offload explicitly rejected. |
| G-36 (one `cursor-agent`) | **Untouched**; clarified (per Cluster A) that it does not cap IDE Tasks — S0/S2 cover that axis. |
| Cluster B's earlier "disable vector sync" REC | **Superseded** by CROSSCRIT-B + evidence — not a G-lock, no flag needed. |
| **CHALLENGES STANDING DECISION flags raised: none.** WSL2 (which would have challenged the no-new-always-on posture) is rejected on the merits, not adopted. |

## 5. Unresolved tradeoffs left for the owner

1. **Which folder becomes the default open target after S1** — per-project roots under `~\source\` vs a thin `~\projects` aggregator — and whether a deliberate "home browsing" workspace exception is ever acceptable (knowing it re-triggers the double-load while open).
2. **Rules-loading strategy post-migration:** user-level always-applied rules vs ≤10-line pointer files per project root. Needs the one-project pilot's result; owner should pick the pattern he'll actually maintain.
3. **Does local fan-out ever return?** Plan says AIMD after G-4 holds; Cluster A's Skeptic dissent (permanent serial + Cloud, `cwnd=0` extra forever on this box) remains a coherent alternative the owner may simply prefer.
4. **If the 48 h A/B fails:** accept FTS-only memory, or invest in embedding scheduling/batch-size tuning as the next lever — a cost/feature call only the owner can make.
5. **Incident receipt discipline:** Cluster A's request for one full receipt on the next mass-cancel (PIDs, commit charge, `~/.cursor/subagents/` growth, abort string) is still unfunded; without it, the H2-vs-H3-vs-H4 causal story for Issue 1 stays UNVERIFIED.

## 6. Confidence

**0.75 overall.**
- **High (≥0.85):** S0 (pure policy, no mechanism to fail), S3 (both flap mechanisms disk-verified root-caused and fixed, 10-min probe passed — though 10 min ≠ 48 h), S4 design (targets a proven silent skip), the WSL2 rejection (vmmem physics is not in dispute at 1.8 GB free), the junction rejection (three independent sources converge).
- **Medium (~0.7):** S1 payoff size — the duplicate-mount RAM cost is observed but not measured in MB; the rules-loading migration risk is real and only a pilot retires it.
- **Lower (~0.6):** S2 adoption — kernel locks are only as good as the protocol compliance of agents that ignored policy before; and the causal mechanism of the original 8-cancel incident remains UNVERIFIED (H2/H3/H5), so S0/S2's sizing is defensive rather than diagnostic.
- **Known blind spot:** CROSSCRIT-A and CROSSCRIT-C were never written, so Cluster A's lease design and Cluster C's drift-check design received only my single-pass adversarial review here, not a full round-2.
