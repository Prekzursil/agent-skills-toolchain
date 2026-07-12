# The Final Agentic-Workspace Architecture (2026-06-11)

Capstone of a 15-agent research pass (`wf_cb61a221-d6a`) + adversarial review. Builds on `SELF-CALIBRATION-PLAN.md`, `WORKSPACE-CURATION.md`, `MEMORY.md`. **Verdict: GO** (critic-approved with the edits below baked in).

> **The single most important, honest finding:** this workspace is **~90–95% already built.** The remaining work is wiring-discipline + one router surface + a few unowned seams — **not new components.** Anyone selling a 12th memory store, a debate engine, a 2nd orchestration runtime, or an "agent OS" is selling the failure mode you fear. This doc is mostly a *stop-building* instruction.

## The spine (one sentence)
The native Claude Code agent loop is the **only** spine; **6 fail-open hook handlers** (one per lifecycle event) are the behavior/verification/memory wiring bus; the **filesystem** (event-ledger + basic-memory + `.beads/knowledge`) is the **only** state plane; a **single markdown routing table** lets the model pick the flow so you never do; and every "check" is a deterministic hook that **TRIGGERS an external signal** — tool result, fingerprint, fresh-context `Task()`, or a *different model* — which a **separate model call JUDGES**. Never a same-context "are you sure?" loop (T1: intrinsic self-correction degrades — Huang et al., ICLR 2024).

## The model: 5 layers · 2 buses · 6 hooks (no 3rd bus — no daemon, DB, or vector engine)
| Layer | Owns | Lives in | Status |
|---|---|---|---|
| **L1 Behavior** | clarify-at-forks, anti-tunnel, simplest-first, flag-don't-implement, anti-sycophancy | `AGENTS.md` matrix + char-preamble on `UserPromptSubmit` + goal-reinject/FALSIFY on `PreToolUse` | ~90% built |
| **L2 Router** | pick the flow + substrate so you never choose | deterministic table in `/start-task` (+ Haiku classify on abstain) | **table is the gap** |
| **L3 Verify** | catch F1 (tunnel) + F2 (spin/wrong-anchor) via escalating external signals | `simplest-probe-first` → `fingerprint.py` → `fresh-context-verify` → FALSIFY→cross-model | **DONE this session** |
| **L4 Memory** | recall prior art (F3) + survive compaction | recall-first (UserPromptSubmit) + ledger-replay + precompact snapshot | **DONE / built** |
| **L5 Capture** | write what worked (F4) without replaying wrong captures | success-gated writer on `Stop` → `.beads/knowledge/*.jsonl` + basic-memory + prune | **writer is the gap** |
| **Guarantee plane** | bound clock/spin/**hang** of autonomous loops | budget caps + fingerprint (have) + freeze-watchdog (gap) | **watchdog is the gap** |

**Bus discipline = the whole architecture.** Behavior travels ONLY through the hook lifecycle (inject/trigger/block); state travels ONLY through the filesystem. Hook ceiling: **6 functional handlers — every item below rides an existing one. Zero new hook events.** (Evidence for the ceiling: ~11 hooks → +18-21s/prompt; the "95-hook" setup is the named anti-pattern.)

## Built this session (DONE — slot in, don't rebuild)
- Anti-degen fingerprint extended to RE MCPs (`settings.json` matcher) · recall-first injection · `simplest-probe-first` skill · `fresh-context-verify` skill + FALSIFY-CHECK trigger. The de-bloat (11 plugins / 12 MCPs / 102 skills) and the curation doctrine.

---

## ⭐ IF YOU DO ONLY 3 MORE THINGS (the critic's truly-minimal subset — ~1 day, closes META + F4)
> **STATUS: all 3 BUILT + golden-tested 2026-06-11 — 5/5 acceptance pass.** Router live in `commands/start-task.md`; capture-writer live on Stop (`stop-hook.py`, E1 milestone-oracle → `.beads/knowledge/decisions.jsonl`); watchdog ported to `monitorcore.watchdog` (run alongside long loops: `python -m monitorcore.watchdog`; historical home was `D:\agent-monitor\watchdog.py`). Golden suite: `~/.claude/hooks/_golden/test_hooks.py`. **One `/reload-plugins` activates the settings.json fingerprint matcher + the earlier pending MCP/plugin curation.** Verify-first (b) confirmed: watchdog WAS net-new (built). Verify-first (d) codex/agy auth still UNCHECKED — do it before relying on any T5 cross-model gate.
1. **Apply the pending reload + write the router table in `/start-task`.** ~90% of "least manual management" in one ½-day. Highest-leverage action in the whole plan. (Table in §Router below.)
2. **Wire the freeze-watchdog** (`D:\agent-monitor\agent_monitor.py`: newest subagent-JSONL mtime stale >25 min AND child alive → alert/nudge, kill optional). The **only** real defense against the documented SSE-hang class (CC issues #33949/#25979/#54434 — upstream won't fix). A new message revives a dead stream, so the watchdog can *nudge*, not just alert.
3. **Ship the capture writer (F4) guarded by a golden acceptance test.** On `Stop`, gate on a **per-substrate success signal** and append to `.beads/knowledge/*.jsonl` with an `alternativesRejected` field.

**Everything else is deferrable.** That's the wrap line.

## Required corrections the critic forced (baked into the above)
- **E1 — capture success-signal must be per-substrate.** Your highest-value work (RE: IDA/Frida/BlueStacks; drug-discovery: schrodinger) produces **no test/build/commit exit code**. A pure exit-grep would silently capture nothing for exactly those sessions. **Fix:** the success oracle = an **event-ledger `note.py --kind milestone`** entry this session (which AGENTS.md §3 already mandates) OR an artifact write (`idb_save`), not just CI exits. Reuses existing infra; covers real work.
- **E2 — verify `STREAM_READ_TIMEOUT_MS` exists before shipping it** (the open SSE issues say there is *no* read-timeout param — it may be aspirational). If absent, the freeze-watchdog (thing #2) is the **sole** hang defense → ship it first.
- **E3 — the golden acceptance test ships BEFORE the hook edits, not after.** You're about to activate + modify hooks; "reports healthy, silently a no-op" is your exact named failure. Test-the-wiring before touching the wiring (non-symmetric fixtures — the AXIS-GOTCHA lesson).

## ⚠️ Two high-risk assumptions to verify FIRST (simplest-probe-first, before building #2/cross-model)
- **(b)** Does `D:\agent-monitor\agent_monitor.py` actually expose a `--watchdog`/kill mode, or is that net-new code? (changes #2's effort from reuse to build).
- **(d)** Is **codex/agy auth currently working?** The cross-model F2 closer (FALSIFY→cross-model) **silently fails if the 2nd CLI is unauthenticated** — and MEMORY flags that auth as flaky. Verify before relying on any cross-model gate.

---

## The Router table (`/start-task`, invoked on demand — NOT a per-prompt hook)
Deterministic table first (~75-80% of tasks route with **zero** model call), 1 Haiku classify only on abstain, ask-at-EVPI-fork-with-recommendation for tier ≥2 near-misses, `*`-prefix bypasses.
```
FLOW axis (first match wins):
  readonly OR <1 file OR <3 tool-calls         → T0  just-do-it (no gates — the F1 escape hatch)
  known recurring pipeline                      → T3  Workflow-DAG (+ per-phase checkpoint)
  RE-discovery OR novel/from-scratch design     → T4  parallel Task agents + council (cheapest-first)
  high-stakes go/no-go / ship / merge           → T5  codex-council (cross-model)
  single-file, bounded                          → T1  EnterPlanMode
  ≥3 files AND has spec/DoD                       → T2  metaswarm gates
  else                                          → ABSTAIN → 1 Haiku classify → ask-at-fork-with-recommendation

SUBSTRATE axis (orthogonal, security-relevant — the seam no dimension owned):
  RE native tool (IDA/Ghidra/Frida/BlueStacks/cheatengine)  → Windows HOST (unsandboxed; ask-list is the control)
  non-RE code / research / orchestration                    → WSL2 (native Bash sandbox = strongest isolation)
  mixed                                                     → RE leaf on host, rest in WSL2
```
Default autonomy = **fork-only** (ask only at tier ≥2 with a cheaper near-miss; recommend + flag alternatives). The 3-position dial (`ask-everything` / `fork-only` / `full-auto-summarize`) is **deferred** — a knob is still management; ship `fork-only` hardcoded, add the dial only if missed.
**Rejected router designs** (don't re-add): trained/embedding router (no corpus, needs the rejected vector backend), auto-classify-every-prompt (taxes trivial messages), multi-sample router, pure-LLM-orchestrator-as-router (that IS the tunnel reflex).

## Coverage & confidence (your "did we miss anything" ask — honest)
- **Spine: HIGH confidence** — the one T1 anchor (Huang) is rock-solid; the architecture *shape* converges across all 13 inputs.
- **Leaves: MED confidence** — mostly 2025-26 preprints, fresh/fragile, low-replication; behavior magnitudes tuned on Sonnet-4 (you run Opus 4.8 → direction transfers, magnitude may not). *Confidence in the spine ≠ confidence in every number.*
- **Genuinely THIN / UNOWNED:** (1) **cross-tool parity** (the 6-hook enforcement is Claude-Code-only; Codex/agy have separate hook lifecycles + may honor no security rules) — needs its own future pass; (2) harness acceptance testing — now closed by thing #3's golden test.

## Anti-overfit ceiling — deliberately EXCLUDED (so no later pass re-adds)
2nd orchestration runtime (LangGraph/CrewAI/AutoGen as spine) · trained/vector router · vector-DB/KG memory (Chroma/Mem0/FalkorDB/Letta) · durable-execution engine (Temporal/DBOS) · observability SaaS (Langfuse/LangSmith/ClickHouse) · guardrail frameworks (NeMo/Guardrails-AI) · default debate engine / >2-round MAD / council-as-verification-gate · per-turn sycophancy-score hook · always-on proactive engine · same-context "are you sure?" loop · re-enable `gateguard` · log-everything memory (replays wrong captures r≈1). Each is a 2nd runtime, a standing server/DB, a training pipeline, a per-turn model-call hook, or a serving-stack filter — enterprise overhead that doesn't transfer to one Windows user.

## Honest limits — what structure CANNOT do
1. **F2 residue is irreducible.** A wrong-but-self-consistent anchor that *every same-model context (incl. fresh) also believes* is undetectable by Tiers 0-2 (self-consistency is blind to convergent errors — Tan et al.). Cross-model (Tier 3) closes *most*; two models can still share a wrong prior. A thin residue needs your "reconsider." No hook judges.
2. **Indirect injection via tool output is unmitigated on native Windows** (a malicious instruction in a decompiled binary / web page / issue lands mid-task). Only the WSL2 lane's egress block limits exfil; the RE lane stays on host. Mitigation = Rule-of-Two discipline, not a filter.
3. **Cross-tool parity is unsolved** (see coverage). The Tier-3 gate is worthless if the 2nd CLI is silently unauthed.
4. **"Walk away" vs "self-correcting memory" are in tension** — a wrong capture on a topic you stop querying never gets corrected (prune is retrieval-reactive). The system you stop watching is where a stale anchor compounds unseen.
5. **Evidence is fresh/fragile** — re-validate behavior assumptions on each model upgrade; there's no automated trigger for that.

## Deferred (Phase 2/3 — build ONLY when the trigger fires; pre-build nothing)
character-preamble + anti-sycophancy rubric (cheap, do with #1-3 if time) · FALSIFY→cross-model wiring (after verifying codex auth) · `ccusage --offline` for budget visibility (drop the Prometheus exporter — OOM history) · `ask`-list for PowerShell `Remove-Item`/`Format-Volume` + `Read`-deny on `.ssh`/`.aws`/`.env`/credentials · knowledge-prune (promote at >200 entries) · OATS selection-logger (100+ events) · cross-tool-parity pass (own research).

## Sources (verified)
Huang ICLR'24 [2310.01798] · Tan self-consistent-errors (EMNLP'25) + "More Rounds, More Noise" [2603.16244] · CC SSE-hang #33949/#25979/#54434 · hook-latency Ruflo #1530 + the "95-hooks" anti-pattern.
