# COUNCIL — Next Build Wave (six voices) — 27.08.2026

> Six-voice council (extends the 4-voice `council` skill: Architect, Skeptic, Pragmatist, Critic,
> + Security, + Chief of Staff) on: **what is the next build wave for the shared agent harness,
> in what order, and what stays queued?** Each voice ran as an independent subagent with only the
> question + compact context + the local evidence docs (anti-anchoring; no conversation history).
> The synthesizer formed its own Architect position BEFORE reading any voice (recorded below).
> Discovery/decision only — nothing was implemented. No secrets. Basic-memory note skipped:
> `BASIC-MEMORY-RELIABILITY_2026-08-27.md` contains no "Post-fix MCP-surface probe" section.

## Evidence base (read by voices)

`CONSOLIDATED-GEM-DECISIONS_2026-08-27.md` (incl. VERIFY-2), `HARNESS-AUDIT_2026-08-27.md`,
`CURSOR-CUSTOMIZE-AUDIT_2026-08-27.md`, `CURSOR-MARKETPLACE-VISITED_2026-08-27.md`,
`BASIC-MEMORY-RELIABILITY_2026-08-27.md`, `local-models-audit_2026-08-27.md`,
`RECOVERED-THREADS_2026-08-27.md`, `skills\openrouter-routing\openrouter-complete-surface_2026-08-27.md`,
`openrouter-free-models_2026-08-27.md` — all under `C:\Users\Prekzursil\.agents\`.

---

## Raw positions (compact, unedited in substance)

### Synthesizer's pre-council position (formed first, before reading any voice)
A → B → C; D + prune-and-merge + deep-research fix queued; deep-research *instrumentation* rides
on B (subagentStart/Stop is the instrument the 42%-success mystery needs). Reasons: (1) A deletes
false claims from the always-injected rules — correctness there compounds every turn at trivially
reversible cost; (2) B closes the 40-vs-0 hook asymmetry in the editor where work actually happens
and is the only veto surface; (3) C is worth more after B's lifecycle evidence exists, and D
explicitly needs C + ISR telemetry. Risk: C deferred while subagents still die under RAM pressure.

### Architect (independent subagent)
**Position:** A then B immediately, then C; D and the family merges stay queued behind C's
provenance substrate. **Reasoning:** A fixes false self-description in the always-injected rules;
B closes the zero-hooks Cursor asymmetry. **Risk:** `failClosed` hooks blocking shells on the
RAM-starved box. **Surprise:** self-description drift — not missing guards — is the root defect;
audits must verify claims against disk, on a monthly change-budgeted cadence with rev-pinned
visited-sets.

### Skeptic
**Position:** the framing is half wrong — A isn't a "wave," it's twenty minutes of deleting false
claims; do it immediately, unsequenced. Then B **narrowed** to the only parts with teeth: the two
veto-capable hooks (beforeShellExecution/beforeMCPExecution, failClosed) + subagentStart/Stop
logging. Before C or D, build the measurement they presuppose (deep-research instrumentation +
the absent harness scorer). C ships now only as a one-paragraph doctrine line; its enforcement
and all of D stay queued. **Reasoning:** VERIFY-2 caught the real disease — two TIER-0 "gaps"
were already built; the failure mode is not missing capability but not knowing what exists.
D depends on ISR telemetry that is item 4 of PLANNED-UNBUILT, i.e. doesn't exist — building MEL
registries now is ceremony no process measures. On Cursor everything except two hooks is
observe-only; "parity" with ~40 Claude hook families is a mirage. **Risk:** narrowing C to a doc
line means the stalled-subagent failure keeps biting until enforcement lands — mitigated only if
B's subagentStop logging actually gets read. **Surprise:** reject the monthly hunt — this hunt
itself died three times mid-write; re-hunt on **trigger** (measured regression or upstream
rev-hash change against the visited ledger, e.g. 25 Bolt @ edb0999), quarterly ceiling.
Visited-set: append-only, keyed by revision, invalidated only by upstream change — never by
calendar.

### Pragmatist
**Position:** A this sitting, B next sitting, C the sitting after; D + merges queued (merges
belong inside the lifecycle wave). Piggyback deep-research instrumentation onto B's
afterFileEdit/subagentStop logging — passive data collection costs nothing while C waits.
**Reasoning:** A is partly *negative work* (VERIFY-2: budget pacing already wired, execpolicy
half-built) — highest return-per-minute, zero new processes; B is where the work actually is,
and subagentStart/Stop is the first real instrument for the documented stalled-subagent failure;
C before D because D is ceremony without C's measurement — this hunt is the proof case (three
passes died; disk artifacts saved it). **Risk:** a failClosed beforeShellExecution guard on a box
where spawning Python can take minutes — the safety feature becomes the stall; ship the shell
guard observe-only for one week, measure hook latency, then flip failClosed on. **Surprise:**
the fastest wins here are *un-building* — A deletes work already done wrong on paper. Cadence:
monthly hunt on fixed change budget (≤K adoptions, one-in-one-out, trend-gated); visited-set =
append-only VISITED files pinned to revision hashes; every hunt starts with a GROUND dedup pass,
never a fresh crawl.

### Critic
**Position:** A → B → C with backup-first, one-edit-per-commit discipline; D queued.
**Reasoning/Risk:** two concrete failure modes — (1) C's fail-closed presumption ("completion
claim false when artifact absent") will **misfire on this box** because artifact writes lag under
RAM pressure (transcript-flush lag): honest completions get marked false; needs a grace window
before adverse inference. (2) B's failClosed guard risks blocking all shell commands — ship it
fail-open/observe-first. A's edits touch the two always-injected rules files and the Stop
manifest: a bad edit degrades every future session of every agent simultaneously — backup first,
verify in a fresh session.

### Security
**Position:** A first, then B — **gated on verified Ollama loopback bind** (it was LAN-open on
0.0.0.0:11434) — then C; D and both options queued, **except** pull one minimal tracer-round
(tamper detection) forward from D. **Reasoning:** the real enforcement wins are the execpolicy
git-write delta (prose ban → enforced policy) and the false-claim deletions; Cursor currently has
zero veto surface in the editor where work happens. **Risk:** failClosed hooks self-DoS under RAM
pressure. **Surprise:** the guard files themselves (`hooks.json`, `default.rules`, `agents.json`)
are the unwatched attack surface — nothing detects tampering with the guards; a minimal scheduled
dry-run tracer (no daemon) is worth early adoption.

### Chief of Staff
**Position:** ship A today in one sitting (it shrank — VERIFY-2 shows budget-pacing already wired,
execpolicy half-built, so A is mostly deletions + a small delta), B next sitting with the
deep-research instrumentation logger attached (passive), C after B; D + prune-and-merge queued.
Nothing touches PR #292's ~70 dirty paths, MIRCEA/BPMD, or P2 verification — those wait on the
owner. **Reasoning:** A is a permanent quota rebate — stale tombstones and false NOT-CHECKED
paragraphs are paid in tokens every turn on two metered subscriptions; B must precede C or
fail-closed doctrine converts the RAM-kill symptom into chronic false-red gates; each wave is
sitting-sized and independently landable — critical when sessions themselves die mid-pass.
**Risk:** A edits the always-injected rules + Stop manifest — a bad edit degrades every future
session; mitigate with backup-first, one file per edit, fresh-session verification. **Surprise:**
A is not housekeeping — it is the only item that *compounds*, and fixing the false pacing claims
restores the ability to measure quota, which every later sequencing decision depends on.
**Cadence:** monthly hunt on change budget; re-run audits only after a wave lands, not on a timer;
visited-set = append-only, rev-pinned, reopen only when the pinned rev changes.

---

## Verdict

- **Consensus:** All six voices, and the synthesizer's pre-council position, converge on the same
  spine: **Wave A first (one sitting, mostly deletions), Wave B second (Cursor hooks — narrow),
  Wave C third, Wave D + prune-and-merge queued.** Unanimous secondary points: deep-research gets
  *instrumentation only* (riding on B's lifecycle logging) before anyone touches its logic; the
  user-gated items (PR #292 ~70 dirty paths, MIRCEA ECC/BPMD, P2 2007/2007) are sequenced around
  and never self-green-lit; no new always-on processes anywhere; visited-sets are append-only and
  rev-pinned, and every hunt starts from a GROUND dedup pass.
- **Strongest dissent:** the **Skeptic** rejects the wave framing itself: A is not a wave but an
  immediate 20-minute correction; B should be cut to the two veto hooks + subagent lifecycle
  logging (everything else on Cursor is observe-only "parity theater"); C should ship now only as
  a doctrine paragraph with enforcement queued behind measurement (harness scorer + instrumentation),
  because VERIFY-2 proved the harness's real disease is *not knowing what it already has*; and the
  monthly hunt cadence should be replaced by trigger-based re-hunts with a quarterly ceiling —
  hunts are expensive and die on this box.
- **Premise check:** the Skeptic challenged the question — "pick the next build wave" presumes
  building is the bottleneck, but two TIER-0 items were already built and nobody knew. Partial
  acceptance: the recommendation below promotes the measurement track (scorer + instrumentation)
  and shrinks C's first landing to doctrine + observe-mode. **Bias flag honored:** Skeptic + Critic
  independently aligned against the synthesizer's initial "C as a full enforcement wave 3"
  (Skeptic: doctrine-only first; Critic: adverse inference misfires under transcript-flush lag).
  Two voices against the initial position = real signal — the synthesizer changed C's shape
  accordingly. A third alignment (Pragmatist + Critic + Security) forced observe-first on B's
  failClosed guard, also adopted.
- **Recommendation:** **A (today) → B-narrow (next sitting, observe-first) → C (doctrine now,
  enforcement after B's evidence) → D queued**, with a measurement track threaded through:
  1. **Wave A — today, one sitting, backup-first, one file per edit, fresh-session verification
     after the rules edits.** Order: (a) delete the false budget-pacing "NOT-CHECKED/not computable"
     prose from CLAUDE.md + AGENTS.md and point at the already-wired statusline fields + compress
     the AgentBridge tombstone to one full copy + pointer; (b) registry/deny fix for markitdown +
     meta-tool in `agents.json` + re-run sync; (c) Stop-event rebalance (backup manifest first);
     (d) Codex execpolicy git-write **delta only** (+ allow read-only git); (e) tbcml → Codeberg
     pointer fix + ADMET v1-vs-v2 caveat lines. All reversible, zero new processes.
  2. **Wave B — next sitting, narrow scope.** Create `~\.cursor\hooks.json` with exactly:
     beforeShellExecution + beforeMCPExecution guards **in observe/allow mode first** (mirror the
     destructive-command set from `default.rules`), subagentStart/subagentStop lifecycle logging
     (the stalled-subagent instrument), afterFileEdit logger. Flip `failClosed`/deny only after
     ~1 week of latency evidence shows the guard itself won't stall the box. **Gate:** verify
     Ollama is loopback-bound before this sitting (Security). **Passenger:** deep-research
     instrumentation reads the same lifecycle logs — no skill-logic changes.
  3. **Wave C — doctrine text lands with Wave A/B (one paragraph: a budget-aborted gate is never
     green; completion claims require disk artifacts); enforcement lands only after B's evidence,
     and with a grace window for transcript-flush lag before any adverse inference (Critic).**
     Checkpoints gain `disk-verified` vs `agent-claimed` provenance.
  4. **Measurement track (threaded, not a wave):** port/author the deterministic harness scorer
     into `.agents\scripts\` as a Wave B/C passenger so the next audit emits numbers instead of
     NOT-CHECKED; per-hook ISR telemetry stays queued until the scorer + lifecycle logs exist.
  5. **Queued (in order):** Wave D airworthiness trio + skill lifecycle system (needs C's substrate
     + ISR telemetry) — **except** one minimal scheduled dry-run tracer-round on the guard files
     themselves (hooks.json / default.rules / agents.json tamper check, no daemon), pulled forward
     per Security; prune-and-merge of skill families (folds into the lifecycle wave, not before);
     eviction landmarks; deep-research *fix* (only after instrumentation data); paid OpenRouter
     bake-off (blocked on user top-up + per-key limit click, not on a decision); Codex `elevated`
     sandbox stays TRIAL-with-scripted-revert.
  6. **User-gated, never self-started — sequence around only:** commit decision on ~70 dirty paths
     in `agent-skills-toolchain` / reconcile with PR #292; MIRCEA ECC protocol + BPMD spawn (waits
     on explicit "go"); P2 2007/2007 twice-verified fail-closed check (never green on a
     budget-aborted gate).
  7. **Revisit cadence (synthesis of Skeptic vs Pragmatist/CoS):** event-driven with a ceiling —
     re-run the relevant *audit* after each wave lands (not on a timer); run a *gem-hunt* at most
     monthly and only on a fixed change budget (≤K adoptions, one-in-one-out, trend-gated), and
     skip the month if no wave landed; allow trigger-based re-hunts any time a visited-set's
     pinned upstream rev changes or a measured regression appears; hard quarterly ceiling on
     full re-audits. Once the harness scorer exists, its post-sync numbers become the trigger
     signal, replacing calendar guesswork.
  8. **Visited-set discipline:** append-only `*-VISITED_*.md` files pinned to revision hashes
     (the marketplace file @ `edb0999…` is the template); an entry reopens only when its pinned
     rev changes upstream — never by calendar; every hunt starts with the GROUND dedup pass
     against the visited ledger + done-waves list; hunt outputs are written incrementally to disk
     (idempotent addendum pattern) so a killed pass resumes instead of circling.

---

*Council run 27.08.2026, six independent subagent voices + in-context synthesizer. Nothing
implemented; this file is the decision record.*
