# Judge J2 — Workflow-tool contract: would each design's script run, resume and terminate?

- **Judge:** J2 (one of three); lens = the Workflow tool contract (`WORKFLOW_TOOL_REFERENCE.md`, research-2 §1/§3.6/§4, and the script that actually ran, `hf-space-qwen-heretic-review-wf_f47ecf9e-916.js`). I wrote none of the designs. Read order per rubric: A2 → A3 → A1. Scores are 1–5 integers; all seven criteria scored, effort weighted on criteria 2 and 3.
- **Method:** full read of all three designs (every JS skeleton and every schema), then mechanical checks on extracted scratch copies under `/tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/work/judge-J2/` (`A2.js`, `A3.js`, `A1.js`, `*.schemas.js`, `check.js`, `repro_helpers.js`): `node --check` on each assembled script (design blocks in the order each design prescribes, `export const meta` → `const meta`, body wrapped in an async function, H6 block pasted verbatim from `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` for A1); a recursive walk of every schema constant asserting `type:'object'` roots, `required ⊆ properties` and enum-typed verdict fields; greps for `Date.now|Math.random|new Date(`, `isolation`, `.filter(Boolean)`, `phase()` titles vs `meta.phases`, `effort`, `model`, `git push`; and five isolated reproductions of *pure helpers only* (no `agent()` ever called, no workflow executed). Nothing under `/workspaces/agent-skills-toolchain` was modified; no `*.hf.space` URL was touched; no token sought.
- **Reference facts I lean on (verified):** `agent()` returns bare `null` on skip/terminal death (REF §API); the H6 template's `withTimeout` returns whatever the thunk resolves to, including `null` — only `settle()` types a null (`h6-timeout-heartbeat.md` L124-153, L169-173); the harness queue is FIFO by `queuedAt` and a queued call waited up to 1,580 s at cap 2 (research-2 §1.4); only completed `result` events replay on resume (research-2 §1.1); meta phase entries need `model` when a phase uses a model override (REF §Script contract).

## 0. Mechanical results (all three)

| check | A2 | A3 | A1 |
|---|---|---|---|
| `node --check` on the assembled script | OK (768 lines) | OK (478 lines) | OK (650 lines incl. verbatim H6) |
| `Date.now / Math.random / new Date()` | none | none | none (only the H6 comment) |
| `isolation:'worktree'` | none (agents `git -C $REPO worktree add`) | none | none |
| schema walk: `required ⊆ properties`, object roots | 48 object nodes, all OK | 20 nodes, all OK | 155 nodes, all OK |
| verdict-like string fields without `enum` | none | none | none |
| `meta.phases` titles vs `phase()` calls | 9 titles; 8 called; **`Integrate` never `phase()`'d** (only via per-call `phase:` opts) | 6 titles, all called | 7 titles, all called |
| `model` declared on the meta phase that overrides it | **no** (`model:'fable'` used in Build, L1173/L1334) | n/a (no override) | **no** (`model:'fable'` in Build, L863) |
| bare `.filter(Boolean)` on a barrier | none | 2, both on pipeline results whose stage never throws (typed before) | 1, on pipeline-over-settle results (never null) |
| bare `null` from `agent()` reaches a dereference | **YES — `safeAgent` L1169→L1175 TypeError** (reproduced) | no — `run()` L1052-1057 types it (reproduced) | **YES — `safeAgent` L735-736 TypeError** (reproduced) |
| wave scheduler survives wave 2 | yes (promise DAG) | yes (`topoOrder` over the full list, `waves` filters done ids) | **NO — `topoOrder(queue)` throws `unknown dependency` on wave 2** (reproduced, L692-697 + L980/L990) |

Reproduction transcript (pure helpers copied verbatim, `repro_helpers.js`):
```
[1] A1 build(): topoOrder(queue) after a merged dep leaves the queue → THROWS on wave 2: unknown dependency c01a-hygiene
[2] withTimeout(null-thunk) → null ; h6IsDrop → false
    A2 safeAgent path: TypeError: Cannot read properties of null (reading 'status')
    A1 safeAgent path: TypeError: Cannot read properties of null (reading 'outward_actions_taken')
    A3 run() path: typed status = "null"
[3] A2 runDag(): speculative branch taken for 0 dependency edge(s) → knob is dead code (recs.has(d) is evaluated in the synchronous loop, L1425)
[4] A3 journeys: author creates tests/journeys-wplan-w1-r1a, integrator merges task/journeys-plan-w1-r1a → equal? false
[5] A2 fingerprint stable across sha/number changes: true
```

---

## 1. Contract-violation tables (one per design)

Legend: ✓ holds · ◐ partly · ✗ violated · (line refs are into the design file)

### 1a. A2 — throughput-first

| contract point | status | evidence |
|---|---|---|
| `meta` pure literal; titles match `phase()` | ◐ | L1017-1032 literal ✓; `phase('Setup'/'Plan'/'Tests'/'Build'/'Review'/'Synthesize')` + ternary `Stage`/`Promote` ✓ (L1543, 1562, 1592-1596, 1602, 1625); `Integrate` only as `phase:` opt; no `model` on the Build entry although L1173/L1334 set `model:'fable'` |
| no `Date.now`/`Math.random`/`new Date()` | ✓ | grep clean; timestamps only from agent `date -u` (COMMON `t_start/t_end`) and `args.launched_at` |
| `agent()` null → typed entry | ✗ | `withTimeout` (L1114-1122, verbatim H6 semantics) returns `null`; `safeAgent` L1169 `h6IsDrop(null)` is false → L1175 `r.status` throws. Propagation: `runTask` → `runDag.builtP` rejects → `mergedP`/`tail` reject → `await tail` (L1443) throws → top-level catch (L1620) → **whole run aborted** to synthesis. The `settle()`-wrapped calls (plan critics, reviewers, refuters, panel, ciread) are safe; every Build/Integrate/Setup/synth call is not. The design's own F-41 row (L925) claims the opposite. |
| schemas: object root, `required ⊆ properties`, enum verdicts, `sha` where code read | ✓ | `S()` L649 merges `COMMON` (`base_sha`, `head_sha`) into every schema; 48 nodes verified; enums on every verdict; only `type/enum/required/minItems` keywords (safest vs the validator) |
| pipeline vs parallel | ✓ | per-task promise chains (no barrier), `parallel` via `settle()` only at the verifier‖refuter reduce, 5-lens review, 3-refuter and 3-judge majorities, 2 plan critics (§10d L813); `pipeline(fresh, …)` for per-finding refutes L1479 |
| concurrency at cap 2 / cap 14; wave from args | ◐ | `WAVE/TA_SLOTS/FRONT_LOAD/…` from `args.knobs` or derived from `args.cap` (L1063-1075) ✓; admission semaphore L1227-1231 deadlock-free (deps awaited before `acquire`, L1425-1429) ✓. But the claim "queued agents ≤ cap → no FIFO starvation" (L195, L799) is false: at cap 2 two chains × (verifier‖refuter) + the merge-queue integrator + a clean gate = up to 6 enqueued; at cap 14 4 chains×2 + 6 test authors + integrator + 5 incremental reviewers = 20. With FIFO (research-2 §1.4) and 15-min timeouts on `judge/integrate/cleangate/refutef` (L1131-1133) a queue wait alone can fire the timer. `speculativeDeps` (the stated 1.5 h cap-14 lever) is dead code (repro [3]). |
| prompts pure in args + sorted results; SHAs pinned | ◐ | prompts built from `args` + results; arrays sorted (`known`, `found`, `rfCard`, `rows`) ✓; every code-reading prompt carries `impl.head_sha`/`prev`/`head` ✓; knobs never interpolated ✓. Impurities: synth/synthverify prompts embed `J(ledger)`/`J(dropped)` (L1636, L1639) whose push order is completion order; at cap ≥ 8 `reviewDelta` runs concurrently with the build and reads the shared `seen` set (L1411, L1470) so `KNOWN` content depends on completion timing; setup prompt embeds the session scratchpad path (`A.snapshot_src`, L1546) |
| effort / label discipline | ✓ | `label = role:item:attempt` (L1164) unique; effort per role (§3 table; xhigh only panel/resolver/plancritic); `model` inherited except hardening cards and the narrower retry of *any* authoring role (L1173 — broader than §1b C17 states) |
| `log()` on every drop / cap | ◐ | DROP/REJECT/BLOCK/deferred/budget/style-only all logged (L1170, 1179, 1328, 1144, 1139, 1478) ✓; the revert integrator's result is discarded unchecked (L1394) — a failed revert leaves `integration/<nonce>` ahead of the script's `head` silently |
| budget guard on `budget.total`; reserve; synth always | ✓ | L1136-1141; `RESERVE` 200k; synth inside the outer try/catch's fall-through (L1625-1641) |
| 1000-agent lifetime cap; ≤ 4096 items | ✓ | `agentsOk` L1142-1146 with `AGENT_CAP_SOFT` 850 and `maxAgentsThisRun` 110 slices (`nextAction:'resume'`); pipeline items are findings (tens) |
| worktree/branch lifecycle consistent, no `isolation` | ✓ | §4f L200-216 ↔ prompts L1241, 1249, 1260, 1279-1285, 1288; `git cherry` empty before worktree removal; bundles `<prev>..HEAD` per merge into the grill folder |
| no outward action inside a run | ◐ | `semantic()` aborts on `outward_actions_taken` (L1151, 1178) ✓; **but** `pIntegrate` pushes `integration/<nonce>` and `impl/*` when `args.approvals.push_remote` is set (L1284) — data-gated, not trigger-gated (T-2 says args are script input, not the user voice); `gh run download` in R2 is read-only ✓ |
| resume / replay | ◐ | `integration_sha_at_launch` recomputed per invocation and pinned in prompts (L1042, 1279); implementer `status:'reused'` on an existing GREEN branch (L1250); integrator `merge-base --is-ancestor` with rc 128 treated as unknown (L1280) ✓; smoke→full replay of the T01a chain holds positionally (I traced the call sequence: setup, testauthor:T01a, impl, verify‖refute, judge, integrate — identical prefix; divergence only at the clean gate). But every `withTimeout` retry makes control flow time-dependent: a timed-out agent still completes and journals a `result`; on resume that call returns from cache instantly, the retry branch is skipped, and the `agent()` sequence diverges from the journal from that point |
| stage ordering | ✗ | R0 (`stage:'plan'`) skips Setup (L1542) yet its symbolizer/api-ledger prompts name `REPO` and `ROOT/libsrc` (L1564-1565), which only Setup creates (L1546-1547). R0 agents are pointed at paths that do not exist. |
| R2/R3 can reach `satisfied` | ✗ | `outerLoop` precondition requires `cleanGates[last].verdict === 'GREEN'` (L1521-1523); in `stage`/`promote` no clean gate runs unless SF/RF cards were built, so a **clean** staging run ends `not-satisfied` → `nextAction` `restage` (L1629), and a clean production run ends `rollback-requested`. Also `reviewDelta(from=head, to=head)` reviews an empty delta. |

### 1b. A3 — minimal scaffold

| contract point | status | evidence |
|---|---|---|
| `meta` pure literal; titles match `phase()` | ✓ | L932-944; `phase('Setup'/'Plan'/'Build'/'Integrate'/'Review'/'Synthesize')` at L1264, 1270/1284, 1289/1184, 1168, 1209/1295, 1279/1302 — every title called, every call titled; no model override anywhere (§13 note L1316) |
| no `Date.now`/… | ✓ | grep clean; `args.launched_at` and agent `date -u` only |
| `agent()` null → typed entry | ✓ | `run()` L1046-1058: `if (r && !h6IsDrop(r)) … else ledger.push({status: r ? r.__endReason : 'null'})`, one narrower retry with `attempt: 2` suffix, then `{status:'null', reason:'agent-null'}`; `assertCommon` L1028-1034 short-circuits on drops; reproduced |
| schemas | ✓ | 20 nodes verified; `COMMON` spread into every schema; every verdict an enum (`VERDICT.verdict` 7 values, `MERGE.status` 7, `BUILD.status` 4); `sha`/`head_sha`/`tests_head` with 40-hex `pattern`. Note: `pattern/maxLength/minLength/minimum/maximum` support in the StructuredOutput validator is UNVERIFIED (the observed run used only type/enum/required) — a common gap, see §7 |
| pipeline vs parallel | ✓ | `pipeline(wave, buildTask)` L1166; `parallel(3 lenses)` L1219 (dedup needs all — justified); `pipeline(fresh, refute)` L1223; serial integration and the clean gate at the wave barrier (§10.4) |
| concurrency at cap 2 / cap 14; wave from args | ✓ | `args.wave_size` required (L950); at cap 2 a wave of 2 strictly-serial chains never enqueues more than 2 agents → **no FIFO queueing, no queue-wait-induced timeouts** (best of the three); at cap 14 width is DAG-limited (1–3), honestly stated as ~12 h critical path (§11). Barrier waves chosen explicitly for replay determinism (§10.4 L748) |
| prompts pure; SHAs pinned | ✓ | every builder prompt is `P.*(args, sorted results)`; `seenKeys` sorted (L1218), `found.sort(byId)` (L1220), status rows sorted (L1231, 1246); no ledger in any prompt; head sha in every code-reading prompt (`cardRef`, `P.verify`, `P.review`, `P.refute`, `P.veto`); `attempt: 2` suffix on retries only |
| effort / label discipline | ✓ | `role:mode:id[:retry]` (L1047, 1052); efforts per §11 table; xhigh only for `veto` and security-risk verifiers (L1120) |
| `log()` on every drop / cap | ◐ | DROP with reason and attempt (L1055); budget/agent-cap (L1041-1043); wave truncation (L1023); lens drops counted (L1222). Two silent spots: a chain that resolves `null` is recorded as `dropped_null` without a `log()` (L1167); the journeys merge failure is neither logged nor recorded (L1183, see below) |
| budget guard; reserve; synth always | ✓ | `budgetOk` L1040-1045 (`agentCount > 800` first, then `budget.total &&`); `RESERVE` 120k; synthesizer outside the main try (L1302-1307) |
| 1000-agent cap; ≤ 4096 items | ✓ | ≈240 agents (§11); soft cap 800 |
| worktree/branch lifecycle consistent, no `isolation` | ◐ | §4.4 ↔ prompts L1078-1091 consistent for author/red/builder/verifier/merge/conflict/ff/clean. **Journeys mismatch:** the author is told to create `tests/journeys-w<tag>-<nonce>` (L1092) but `integrate()` merges `task/journeys-<tag>-<nonce>` (L1087 via L1183) → `missing-ref` → `stale` → silently not merged (repro [4]); journeys therefore never reach the integration branch and the clean gate never runs them |
| no outward action inside a run | ✓ | no push anywhere; checkpoint actions computed in JS from `owner_approvals` nulls (L1245-1257) — "no agent can add or remove an action"; `assertCommon` throws on `outward_actions_taken` |
| resume / replay | ◐ | resume only when `integration_sha_at_launch` matches (§10.1); branch reuse on re-drive (§4.4); `missing-ref` → live re-drive — but L1173 re-calls `buildTask(r.card, head)` with **identical** prompts (no `attempt` suffix), contradicting §10.1 L733 "cache miss by construction"; the same timeout→replay divergence as A2 (`withTimeout` on every `run()`), though at cap 2 timeouts can only fire on genuinely slow agents because nothing queues |
| fail-closed on dropped verdict agents | ◐ | verifier null → blocked ✓ (L1124); **clean-gate null is treated as RED and reverts the last good merge** (L1177-1181: `cg.gate_exit_code === 0 && cg.head_sha === head` is false for `{status:'null'}`); **veto-judge null is fail-open** (L1232-1233: `(vj.findings || [])` → zero vetoes → `satisfied` stands); confirm-RED verifier null is misattributed to the author and re-drives it (L1109-1113) |
| R2/R3 semantics | ◐ | `satisfied()` needs `lastClean.head_sha === head` (L1198) and no clean gate runs in an evidence-only stage → a clean staging ends `dry(2)`, `checkpoint.status` = `failed`/`blocked` (L1256) while `promote-production` is still pushed unconditionally (L1255) — a contradictory checkpoint, not a crash |
| args contract | ◐ | `NEED` (L950) omits `snapshot_dir`, `wheels_dir`, `toolchain_status_sha256`, `libsrc`, `decision_queue_path`, `lens4_path`, `findings_path`, `redteam_path` that `P.setup`/`P.plan` interpolate (L1068-1076) → a missing arg yields "…snapshot undefined" prompts instead of a throw (`plan_sha` alone is checked separately at L1283) |

### 1c. A1 — reliability-first

| contract point | status | evidence |
|---|---|---|
| `meta` pure literal; titles match `phase()` | ◐ | L643-656; all seven titles called (L790, 807, 981, 946, 1004, 1049, 1059); no `model` on the Build entry although `opt()` sets `model:'fable'` for hardening cards (L863) |
| no `Date.now`/… | ✓ | grep clean |
| `agent()` null → typed entry | ✗ | `safeAgent` L733-736: `h6IsDrop(null)` false → `r.outward_actions_taken` throws (reproduced). Inside `pipeline(wave, buildCard)` the harness converts the throw to a `null` item and L982 types it `chain-threw` ✓; **outside** a pipeline (preflight, every plan agent, `integrateOne`, `inversion`, `wave-gate`, `synth`) the throw aborts the run. §10 L453 claims nulls are typed. |
| schemas | ◐ | 155 nodes verified; envelope merged (`env()` L331); enums everywhere; `ANCHOR` pattern; `sha` fields. Two consumption mismatches: `INTEGRATION.merged_sha` is optional (L415-418) yet `integrateOne` returns it as the new `head` (L970) and `build()` calls `head.slice(0,7)` (L988) → a schema-valid integrator return without `merged_sha` crashes the build; the fresh-clone **wave gate reuses `VERIFY`** (L991), forcing the integration tester to fabricate `revert_proof`, `mutants`, `negative_control`, `acceptance_reruns` (minItems 1) for a clean-clone gate — F-46 by construction |
| pipeline vs parallel | ✓ | `pipeline(wave, buildCard)`; `settle()` for the two authors, 3 refuters, 5 reviewers, 3 judges, 6 card authors (all true joins); `pipeline(unverified, pre-verify)`, `pipeline(claims, stage-claim)` |
| concurrency at cap 2 / cap 14; wave from args | ✗ | `WAVE` from `args` (L674) ✓, but every card chain fans out (2 authors, then 3 refuters) so 2 chains enqueue up to 6 agents at cap 2 and 6 chains up to 18 at cap 14 → FIFO queueing is the norm. The probes carry **300 000 ms (5 min) timeouts** (L865, 935, 936, 830) and the timer starts at enqueue: a `postcondition`/`state-probe-final` queued behind the other chain's refuters or a 45-min implementer times out, `bad(st.post)` makes `unitDone` condition 1/2 false (L768-769) and the card is **blocked `predicate`/`stale-base` spuriously**. The 41 h cap-2 plan (§11) is unsafe as written. |
| wave scheduler | ✗ | `build()` recomputes `topoOrder(queue)` on the shrinking queue (L980) after removing the merged wave (L990); `topoOrder` throws `unknown dependency` for any card whose dependency was merged (L695) → **every multi-wave R1 aborts at wave 2** (repro [1]). Removing the L990 filter would instead re-schedule merged cards forever (`waves()` L699 does not drop done ids from `rest`). The smoke run (1 card, 1 wave) cannot catch this. The `split` path appends sub-cards but never re-points dependents of the split card (L984), so `waves()` L705 throws `no ready card` once only those dependents remain. |
| prompts pure; SHAs pinned | ◐ | prompts from args + sorted results (`J(state.blocked…sort)`, `J([...seen].sort())`, `J([...probesUsed].sort())`, preverified sorted) ✓; head/base/bundle SHAs in every code-reading prompt ✓; impurity: `synth`/`synth-verify` embed `J(ledger)`/`dropped` in completion order (L1060-1062) |
| effort / label discipline | ✓ | `opt(label…)` + `:retry` (L748, 863); efforts per §11; `model:'fable'` confined to `HARDENING` cards (all stages of those cards) |
| `log()` on every drop / cap | ◐ | `safeAgent` logs every non-SUCCESS (L742); dropped card authors (L821); `chain-threw` (L985). Silent: staging fix cards are computed and **never built** (L1088 — `fix` is only logged, contradicting the log line's "their local parts are built"); inversion-scout findings are added to `seen` but never refuted or turned into fix cards (L1013-1015), so they can never be fixed and never re-appear |
| budget guard; reserve; synth always | ✓ | L718-723 (`max(RESERVE, 15 %)`, `agentCount > 800`); synthesize in the catch path (L1095) |
| 1000-agent cap; ≤ 4096 items | ◐ | ≈740 planned agents for R1 (L479) against a soft cap of 800 and a hard cap of 1000; a 10 % overrun in fix rounds trips the reserve mid-build and blocks the remaining cards `budget`; the multi-session resume plan (41 h) never says whether replayed calls count toward the per-workflow cap |
| worktree/branch lifecycle consistent, no `isolation` | ✓ | §4.4 ↔ L844-845, 852, 868-869, 949-952, 957-958; held-out branch merged at integration (L972); bundles per card and checkpoint bundles per merge; bundle size only **warned**, not `blocked:'bundle-too-large'` as §4.4 L140 states (L969) |
| no outward action inside a run | ✓ | abort on `outward_actions_taken` (L736); no push; R3 Hub check read-only |
| fail-closed on dropped verdict agents | ✓ | `satisfied` needs `votes.length === 3 && sat === 3` (L1035) — a dropped judge can never grant; refuter drops reduce survivors below 2 → predicate false (fail-closed, if over-eager) |
| termination semantics of the predicate | ◐ | the fix loop fires only on a refuter **majority** (L891-892) but `unitDone` condition 10 fails on **any** single refuter that says `refuted` with severity > low (L777) → a card with one dissenting refuter is blocked `predicate` with no fix path; `state.blocked.length === 0` is then required for `satisfied` (L1035), so the review loop runs all 4 rounds (5 reviewers + refuters + 3 judges each) with no possible success |
| smoke coverage | ◐ | smoke returns before `synthesize()` (L1071-1074): `SYNTH`/`SYNTH_VERIFY` are not exercised, contrary to "every schema exercised once" |

---

## 2. Scores with evidence (per design)

### 2a. Coverage reality (30 %) — rows traced end to end (mechanism actually present in JS/gate, not a sentence)

**A2 — 4.** Traced 15: F-1 ✓ (`PREFIX` L1087-1089 + `semantic()` repo_toplevel L1153 + toolchain hash L1640), F-5 ✓ (L1152; gate L380), F-6 ✓ (`approvals` required; L1603-1604), F-7 ✓ (gate `env -i` L364, secrets L483-489), F-12 ✓ (`reduceVerdicts` ledger-hash/collected/red/mutants/hunks L1305-1311; `semantic()` L1155), F-14 ✓ (overlap edges L1214-1219, rank order, serial queue), F-18 ◐ (counts/trailers/protected/idiom/confirm-RED/mutants L439-446, 491-523 — but no oracle lock: an implementer may edit an existing non-protected test as long as counts hold; the design leans on the verifier prompt "diff-reads every test change"), F-27 ✓ (L1338-1364), F-34 ◐ (integration fixer ≤2 then revert L1386-1396; the text's "one integration-fix round after a red clean gate, then resume admissions" is not in the code — a red clean gate just stops admissions L1410; revert result unchecked L1394), F-35 ✓ (L1151/1178; conditional push aside), F-40 ✓ (synth verifier L1639), F-41 ✗ (crash, §1a), F-43 ✓ (L1042, 1279-1280), F-45 ✓, F-46 ✓ (`semantic()` L1149-1159), F-47 ◐ (meta/phases/try-catch/smoke ✓, but the smoke is R1-only and R0's path bug and the null crash are not smoke-detectable). The gate (§7) is the most complete of the three (16 steps: self-test red-proofs, gate-integrity hash, journeys with `needs=` skips, double pytest, blob/LFS/EOL, apicheck, claim lint, idiom lint, secrets, protected trailers, mutants, confirm-RED). Anti-pattern tables (D/T/S/SD, 55 rows) each name a JS/gate mechanism with a cost class. 13 real, 2 partial, 1 false.

**A3 — 4.** Traced 15: F-1 ✓ (`PREAMBLE` + `assertCommon` L1030 + toolchain sha in setup/clean prompts), F-5 ✓ (L1032; gate L358), F-6 ✓ (JS checkpoint from `OA` nulls L1248-1255; `blocked:evidence-dir-missing` L1294), F-7 ✓ (gate `env -i` + `CANARY_SECRET` L367-369; secrets over diff **and** commit messages L563), F-12 ✓ (`okSemantics` L1121: gate exit 0, `ledger_head_sha === b.head_sha`, hunks, mutants), F-14 ✓ (`topoOrder`/`waves` with disjoint write sets L1013-1027, logged waits), F-18 ✓ (deterministic oracle lock: any modified/deleted pre-existing test outside `tests_allowed` is red, L531-532; protected; counts vs baseline; test-detection idioms; mutants — the strongest F-18 of the three), F-27 ✓ (L1106-1131), F-34 ◐ (merge-gate red → revert in the integrator prompt L1088; clean-gate red → revert last merged L1177-1181, destructive on a mere null), F-35 ✓ (throw L1031; no push), F-40 ✓ (rows compared in JS, script rows returned L1306), F-41 ✓ (reproduced), F-43 ◐ (attempt suffix on null retries; stale re-drive lacks it), F-45 ✓, F-46 ✓ (minItems/maxLength/pattern + `okSemantics`), F-47 ◐ (journeys mismatch is a script-level bug the smoke would not catch because journeys are skipped under `A.smoke`, L1183). S-AP-4 (held-out/journeys) is weakened by the journeys defect. The §1.4 cut table proves each cut by naming the surviving mechanism and its matrix rows. 12 real, 3 partial, 0 false.

**A1 — 3.** Traced 15: F-1 ✓ (L673, 738), F-5 ✓ (L737), F-6 ✓ (L1050-1051, 1079), F-7 ✓ (gate L265; PRE), F-12 ✓ (`unitDone` 4/5: digest equality across two independent gate runs + `gate_fail 0` + collected floor L771-772 — the strongest F-12 mechanism of the three), F-14 ✗ in practice (`waves()` disjointness exists L698-709 but `build()` throws on wave 2), F-18 ✓ (gate locked-oracle reset L232-234, `tamper_scan.py` contract L282, collected floor, mutants ok[8], tamper judge L883-887), F-27 ◐ (MAX_FIX/pivot/re-decompose L896-907; the arbiter/resolver only logs, its decision never changes flow L911), F-34 ✓ (L962-967), F-35 ✓, F-40 ✓ (L1062), F-41 ✗ (crash outside pipelines), F-43 ✓ (state probe L865; but its 5-min timeout makes it a liability at cap 2), F-45 ✓, F-46 ◐ (envelope + JS checks L739; VERIFY misused for the wave gate), F-47 ✗ (the wave-2 throw is exactly the class of bug F-47 promises to catch and the smoke cannot). Several gate tools (`tamper_scan.py`, `no_lost_hunks.sh`, `gate_redproof.sh`, `apicheck.py`) exist only as contracts (L282) delivered by card `c01c`; the gate as written in §7 calls them on every run, so a pre-`c01c` tree fails closed on "file not found" (acceptable) — but it also means the pre-flight red-proof (§7 table "P0 setup --mode clean") cannot run before `c01c` lands. 10 real, 3 partial, 2 not real.

### 2b. Workflow-tool contract (20 %)

- **A2 — 3.** Strong: literal `meta`, clean greps, 48 schema nodes correct, per-task pipeline with justified barriers, wave/knob sizing from args, unique labels, effort tiers, drops logged, `budget.total` guard, 850/110 agent caps, worktree lifecycle consistent, no `isolation`. Broken: bare-null crash aborts the run (repro [2]); R0 points agents at paths Setup has not created; R2/R3 can never reach `satisfied`; `speculativeDeps` dead; judge fail-open on drop (L1355); `Integrate` never `phase()`'d and no `model` on the Build phase entry; completion-order content in the synth prompt; data-gated push. Each is a small fix, but three of them make a run fail or lie as written.
- **A3 — 4.** Every mechanical check passes; null contract implemented and reproduced; barrier waves never exceed the cap at cap 2 (the only design with no queue-wait timeout exposure); prompts pure with no ledger leakage; labels/effort/model clean; JS-computed checkpoint. Deductions: journeys branch mismatch (silent), clean-gate null → destructive revert, veto-judge null fail-open, stale re-drive without the promised suffix, R2/R3 contradictory checkpoint, `NEED` incomplete.
- **A1 — 2.** Literal `meta`, clean greps, 155 schema nodes correct, justified barriers, effort/labels clean, fail-closed judges. But: `build()` throws at wave 2 in every multi-wave run (repro [1]); bare-null crash outside pipelines (repro [2]); 5-min probe timeouts plus per-chain fan-out guarantee spurious `predicate`/`stale-base` blocks under FIFO at cap 2; `merged_sha` optional yet consumed as `head`; VERIFY misused for the wave gate; split path deadlocks `waves()`; ≈740 agents against an 800 reserve; no `model` on the Build phase entry.

### 2c. Termination and replay guarantees (15 %)

- **A2 — 3.** Bounded: `MAX_FIX` 3 (verify+veto combined), two-strikes pivot with `alternatives ≥ 2`, oscillation A→B→A, `MAX_VETO` 1, `MAX_ROUNDS` 3, `DRY_ROUNDS` 2 gated by the inversion pass, `budgetOk`, `agentsOk`, `maxAgentsThisRun`; every exit typed (§5c enum) and logged. Resume: git-state idempotency (`reused`), ancestor check, `integration_sha_at_launch`, smoke→full prefix verified by me. Defects: a null kills the run (typed abort, work in flight lost; resume recovers because the null'd call has no `result`); R2/R3 loop to `max-rounds` then emit `restage`/`rollback-requested` forever on a clean staging (a program-level non-termination); judge fail-open; timeout→replay divergence; incremental-review `seen` timing.
- **A3 — 4.** Bounded: `MAX_AUTHOR` 2, `MAX_BUILD` 3, two-strikes, oscillation, `MAX_ROUNDS` 3, `dry` 2, `budgetOk`, 800; typed exits everywhere (`buildTask` never throws, L1136); `satisfied()` is a JS predicate whose `parkedCritical` rule lets parked leaves terminate the loop (better semantics than A1/A2's "zero blocked"); barrier waves chosen so control flow never branches on completion order; `attempt` suffix on retries; `missing-ref` → live re-drive. Defects: veto-null fail-open, clean-gate-null revert, journeys never merged, R2/R3 `dry` instead of `satisfied`, stale re-drive without suffix.
- **A1 — 2.** Counters and five stop conditions are all present and typed, but the run cannot get past wave 1 (`build()` throw → `FAILED:build …` via the catch — typed, yet no useful termination), the split path can throw, condition 10 blocks cards with no remediation path and then forces four review rounds that cannot succeed, inversion findings are silently dropped, probe timeouts spuriously block cards at cap 2, and ≈740 agents sit 60 below the reserve with replay accounting unaddressed.

### 2d. Owner checkpoints and secret hygiene (10 %)

- **A2 — 4.** `SYNTH.checkpoint` enum with `approvals_needed`/`evidence_paths`, verified by a second agent; approvals as data; `env -i` gate + secrets scan over ranges and gate logs; durable `/workspaces/qwen38-space-build` with a `/tmp` refusal (L1062); grill-folder bundles (synced); toolchain status hash asserted by the synth verifier. Deduction: in-run `git push` when `approvals.push_remote` is set (L1284) — the brief's list does not name pushes to an owner-named existing repo, but T-2 makes args script input, not authority.
- **A3 — 5.** Checkpoint object computed in JS from typed states (no agent can add/remove an action, L1245-1257); nothing pushes; `env -i` + fixed `CANARY_SECRET`; secrets regex over diff **and** commit messages; durable `/workspaces/space-build{,-wt,-tools,-libsrc}` outside the rsync and the cwd repo; toolchain status sha asserted in setup and every clean gate; P0 pre-scan and journal-export scan in the checklist.
- **A1 — 4.** Checkpoint via `SYNTH.checkpoint` + synthesis verifier; nothing pushes; `gitleaks` if present else regex; durable `/home/codespace/build`; bundle-size guard only warns (L969 vs §4.4 L140).

### 2e. Program fit (15 %)

- **A2 — 3.** Decision sheet §4a maps every against-recommendation decision to a build consequence; cards T01a…T16 follow lens-4's 14 steps with CORRECTED ids inlined; pins (T02) before lift (T03) ✓; ship-but-flag §4e ✓; CI does staging+canary+promotion (C15, T16 with a decision rule and last-known-good control) ✓; persona boundary T15/T01c ✓; catalog gate T13/T14 ✓; 3.12 refusal and LF renormalisation ✓. Deduction: the staging/promotion representation is broken in the script — a clean R2 can never reach `promote-production` (§1a), so the promotion path exists only on paper.
- **A3 — 4.** Decisions sheet is agent-written (planner) then owner-approved at C0 with `plan_sha`; cards §4.2 follow the 14 steps; CORRECTED-only rule enforced by `verifier mode:'plan'`; pins and lift share one card but the author writes pins before the builder moves code (characterisation-first holds by role order); ship-but-flag in every card's `out_of_scope`; CI staging/canary/promotion with `EXPECTED.json` asserted in R2; persona boundary card 13b; catalog card 13a + harness 12; 3.12 (honest about 3.12.3 vs 3.12.12); LF. Deduction: R2/R3 status mislabels a clean staging as `failed`/`blocked` while still emitting `promote-production`.
- **A1 — 4.** Decision sheet agent-authored, approved via `plan_hash` (`OA.plan_hash === A.plan_hash`); c01a…c14 with CORRECTED text; pins c02a before lift c02b; video OFF; CI/promotion c14 + R2 evidence reader; held-out seams H1–H7 add composition fit; persona c13b; catalog c13a; 3.12; LF. Deduction: staging fix cards are never built (L1088) — the "fix staging-only failures through the same inner loop" promise is not implemented.

### 2f. Simplicity and anti-overfit (5 %)

- **A2 — 3.** Twelve knobs, an admission semaphore, front-loaded test authors, incremental reviews, speculative deps (dead), a timing/waste ledger, a synth verifier — each justified by a failure mode, but the throughput machinery is where the contract bugs live, and one lever does nothing. Cost stated honestly.
- **A3 — 5.** Six roles, one gate, one script; every cut in §1.4 names the surviving mechanism and matrix rows; nothing without a failure mode; cost stated.
- **A1 — 2.** ~30 roles, 36 schemas, a 12-condition predicate, held-out authors, tamper judge, arbiter, re-decomposer, two probes per card; DS/AP-12 is acknowledged and accepted; the extra surface is exactly where the wave-2 throw, the probe timeouts and the predicate/no-fix-path inconsistency live.

### 2g. Cost realism (5 %)

- **A2 — 4.** Derived from research-2 §1.4 with `[E]` tags, per-role table, waste ratio, 110-agent slices that fit the 1000 cap and a resumable plan. The cap-14 6.5 h figure leans on `speculativeDeps` (dead) and on front-loading not being queue-starved; the cap-2 17 h figure assumes no spurious timeouts.
- **A3 — 4.** 240 agents, 18–20 h / 14–16 h, honest that the cap buys width not depth; resumable invocations; comfortably inside the cap.
- **A1 — 2.** Honest about 41 h / 22 h and ≈740 agents, but 740 vs an 800 reserve leaves no room for the stated 1.2 fix rounds/card variance; the multi-session resume plan ignores replay accounting; spurious probe timeouts would inflate blocked cards and re-runs.

### 2h. Score table and weighted totals

| criterion (weight) | A2 | A3 | A1 |
|---|---|---|---|
| 1 Coverage reality (30 %) | 4 | 4 | 3 |
| 2 Workflow-tool contract (20 %) | 3 | 4 | 2 |
| 3 Termination & replay (15 %) | 3 | 4 | 2 |
| 4 Owner checkpoints & secrets (10 %) | 4 | 5 | 4 |
| 5 Program fit (15 %) | 3 | 4 | 4 |
| 6 Simplicity (5 %) | 3 | 5 | 2 |
| 7 Cost realism (5 %) | 4 | 4 | 2 |
| **weighted** | **3.45** | **4.15** | **2.80** |

---

## 3. Blocking defects per design (would make the run fail or lie)

**A2**
1. **Bare `null` from `agent()` crashes `safeAgent`** (L1169→L1175) and, because `runDag` chains `builtP → mergedP → tail`, aborts the entire run (L1443 → L1620). The F-41 row (L925) and §10b claim the opposite. One-line fix: map `null` to `h6Receipt('null', …)` before `h6IsDrop`.
2. **R0 runs against paths that do not exist:** Setup is skipped for `stage:'plan'` (L1542) while the symbolizer/api-ledger prompts name `REPO` and `ROOT/libsrc` (L1564-1565) that only Setup creates.
3. **R2/R3 cannot reach `satisfied`:** the panel precondition needs a clean gate in `cleanGates` (L1521-1523); none runs in an evidence-only stage, so a clean staging ends `restage` and a clean production ends `rollback-requested` (L1627-1629); the reviewers are given an empty delta `head..head` (L1503).
4. `speculativeDeps` is dead code (L1425, repro [3]) — the advertised cap-14 lever does nothing.
5. Judge drop is fail-open (L1355); revert result unchecked (L1394); no `model` on the Build phase entry despite overrides; `Integrate` never `phase()`'d.

**A3**
1. **Journeys never integrate:** author branch `tests/journeys-…` (L1092) vs merged branch `task/journeys-…` (L1087/L1183) → `missing-ref` → silently skipped; the clean gate's journeys step never sees them (S-AP-4/F-34 weakened).
2. **Clean-gate null/timeout reverts a good merge** (L1177-1181) — a dropped agent is read as RED.
3. **Veto-judge null is fail-open** (L1232-1233 → `satisfied`).
4. R2/R3: `satisfied()` unreachable without an in-run clean gate → `status:'failed'` with `promote-production` still emitted (L1198, L1255-1256).
5. Stale re-drive reuses identical prompts (L1173) despite §10.1; `NEED` omits args that `P.setup`/`P.plan` interpolate (L950 vs L1068-1076).

**A1**
1. **`build()` throws on wave 2 of every multi-wave run:** `topoOrder(queue)` over the shrunken queue hits `unknown dependency` (L692-697, L980, L990; repro [1]). The single-wave smoke cannot detect it.
2. **Bare `null` crashes `safeAgent`** (L735-736) — typed only when inside `pipeline(wave, buildCard)`; in preflight/plan/integration/inversion/wave-gate/synth it aborts the run.
3. **Spurious blocks at cap 2:** 5-minute probe timeouts (L865, 935, 936) with per-chain fan-out under FIFO queueing → `unitDone` conditions 1/2 false → cards blocked `predicate`/`stale-base` without any defect.
4. `INTEGRATION.merged_sha` optional but consumed as `head` (L415-418, L970, L988) → TypeError on a schema-valid return.
5. Condition 10 blocks on a single dissenting refuter while the fix loop needs a majority (L777 vs L891-892) → blocked with no fix path, then four unwinnable review rounds (L1035 requires zero blocked). Inversion findings silently dropped (L1013-1015); staging fix cards never built (L1088); split path can throw `no ready card` (L984, L705); ≈740 agents vs an 800 reserve; VERIFY misused for the wave gate (L991).

---

## 4. Pairwise comparisons

**A1 vs A2.** Both crash on a bare `null` from `agent()` and both leave `model` off the phase entry that overrides it, so those do not separate them. The decisive difference is the scheduler: A2's promise DAG (`runDag` L1418-1449) is deadlock-free, dependency-correct and FIFO-aware, whereas A1's `build()` recomputes `topoOrder` over a queue from which merged cards have been removed and therefore throws on wave 2 of every real run — the one bug the mandatory smoke run is structurally unable to catch. A1 also chooses 5-minute probe timeouts and per-chain fan-out that cannot coexist with the harness's FIFO queue at cap 2, so even a fixed `build()` would spuriously block cards. A2's remaining blockers (R0 path ordering, R2 precondition, null typing) are each a few lines; A1's are structural. **A2 wins.**

**A2 vs A3.** A2 has the richer gate (self-test red-proofs, gate-integrity hash, journeys with `needs=` skips), better R0 grounding (symbolizer, api ledger, catalog provenance) and a deterministic timing/waste ledger; A3 has the stronger oracle lock and the only JS-computed checkpoint. The decisive difference on this lens is that A3 *implements* the tool contract it cites: `run()` types nulls (reproduced), its barrier waves never enqueue more than the cap at cap 2 (no queue-wait timeouts, no completion-order branching), its prompts carry no completion-order content, and its R0 runs after Setup. A2 buys throughput with an admission semaphore plus H6 timeouts and pays with a null crash that aborts the run, a dead speculative knob, an R0 that names non-existent paths and an R2 that can never promote. A3's own defects (journeys branch name, clean-gate/veto null handling, R2 status) are real but non-fatal and local. **A3 wins; A2 is the main graft source.**

**A1 vs A3.** A1's verification depth is the best on paper — digest equality across two independent gate executions, locked-oracle reset, tamper scan, revert-proof and negative control, held-out seams, unanimous fail-closed judges. A3 deliberately cut most of that and proved each cut against the matrix. The decisive difference is that A3's script would run through all waves, resume deterministically and terminate with a typed checkpoint, while A1's cannot complete wave 2, crashes on a null outside pipelines, blocks cards spuriously at cap 2 and sits within 60 agents of its own reserve. Depth that never executes protects nothing. **A3 wins decisively; A1's gate/predicate mechanisms are graft material.**

---

## 5. Final ranking

1. **A3 — 4.15** (minimal scaffold)
2. **A2 — 3.45** (throughput-first)
3. **A1 — 2.80** (reliability-first)

**Position-bias control.** After ranking I re-read A1's strongest sections: §7 (`gate.sh` with locked-oracle reset, digest over the timestamp-free canonical ledger, tamper scan contract) and §13.3 (`unitDone`, twelve booleans printed per card). They are the strongest verification mechanisms in the panel and I have moved them to the top of the graft list. They do not change the ranking: the predicate is evaluated only after a chain that the wave-2 throw prevents from running for 23 of 24 cards, and condition 10 as written blocks cards with no remediation path. The ordering A3 > A2 > A1 stands.

---

## 6. Graft list for the synthesizer

**Take into A3 from A2 (section refs into design-A2):**
1. §7 gate steps 13–15: `--journeys` with `needs=<card>` skip markers counted in the ledger, `gate-integrity` (repo copy hash == root copy), and `--self-test` red-proofs on every clean gate (RED on `f88b120`, RED on the false-claim fixture) — A3 runs red-proof only in setup and card 01.
2. §13 `semantic()` (L1149-1159) and `STAGING_RE` level-forcing in JS (L1108, L1183): raise `verification_level` mechanically, reject a `verify:pass` whose `checks[]` never ran `gate.sh`, reject `veto` without `reproduced`. A3 forces levels only in the planner prompt.
3. §4d/§13 `rankCards` (L1202-1208): order each wave's ready set by longest-path rank instead of by id so the spine is enqueued first (T-8) — a drop-in for A3's `waves()` that keeps barrier waves and replay determinism.
4. §13 R0 grounding trio (L1563-1567): findings symbolizer with executed reproduction of the five UNVERIFIED critic findings, api-ledger from `libsrc` with `known_bad[]`, catalog provenance saved raw with `unresolved` on fetch failure — A3 folds all three into one planner prompt and never pre-verifies critic-1..5 in R0 (its `mode:'evidence'` routing is stated in §12.1 F-11 but not coded).
5. §10a/§14 the cache-key settling experiment on the smoke run (resume once unchanged, count `key` matches; change a non-prompt knob, resume again) and `knobs.maxAgentsThisRun` slicing with `nextAction:'resume'`.
6. §11e/§9 `t_start`/`t_end` on every return → `timing-<nonce>.json` and `waste_ratio` from the synth verifier, so the next run's plan critic reads measured p50s.
7. §13 `pIntegrate` incremental bundles `<prev>..HEAD` numbered per merge (L1283) instead of A3's `git bundle … --all` per merge (grows with the repo; A1 §4.4 L140's 20 MB assertion belongs here too).
8. §13 `fingerprint()` (L1106): hex-sha and digit normalisation before FNV — A3's fingerprint normalises digits and paths but not shas.

**Take into A3 from A1 (section refs into design-A1):**
9. §7 ledger digest over the timestamp-free canonical part (L272-277) plus `unitDone` condition 4 (implementer digest === verifier digest, L771): two independent gate executions must agree — A3 compares only `ledger_head_sha`.
10. §7 gate step 3 locked-oracle reset (`git checkout <oracle> -- tests/acceptance`, L232-234) and the `tamper_scan.py` idioms (Δ assert count, loosened matchers, `-k/--deselect` in recorded commands, L282) folded into A3's scope/idiom steps.
11. §9 `VERIFY.revert_proof` and `negative_control` (L385, 390) + `unitDone` 7/8: revert the implementation hunks, tests must fail — a cheap sufficiency proof A3's verifier lacks.
12. §13.7 the `probesUsed` set handed to the inversion mandate (L1012, 1019) — A3's last-round veto mandate says "do not reuse the lenses' probes" but never passes them.
13. §13.7 fail-closed judging: a dropped judge/veto agent can never leave `satisfied` standing (L1035) — fixes A3's veto-null fail-open.
14. §4.6 held-out seams H1–H7 as the journeys spec list for A3's `author mode:'journeys'` (A3 has J1–J6; H2 identity, H5 catalog admission and H7 error taxonomy are missing).
15. §13.1 `validateCards` throwing at script start on a card without a runnable check and on protected paths outside the gate card (L710-716) — A3 only logs `PLAN DEFECT` (L1274).

**Drop or fix in the winner (A3):**
- Fix the journeys branch name (one `P.mergeBranch(branch, head)` builder; or have the journeys author use `task/…`).
- Clean-gate `null`/timeout: re-run once, then record `clean-gate-unavailable` — never revert on a drop.
- Veto `null`: `stop='veto-unavailable'`, not satisfied.
- R2/R3: define `satisfied()` for evidence stages (evidence verdict + last clean gate sha from `args`) and never emit `promote-production` with `status:'failed'`.
- Add the `attempt` suffix to the stale re-drive; `log()` `dropped_null` chains; extend `NEED` to every interpolated arg.
- Replace the `P.merge(...).replace(...)` revert hack with a `P.revert(id, head)` builder (the design's own note L1314 concedes this).
- Keep `withTimeout`, but size every timeout from observed `queuedAt→startedAt` waits (research-2 §1.4) and log when a receipt fires on a call that later journals a `result` (replay divergence marker).

---

## 7. What none of them handles (common gaps)

1. **Timeout ↔ replay interaction.** All three wrap every `agent()` in H6 `withTimeout`. A timed-out agent keeps running and journals a `result`; on resume that call returns from cache instantly, the retry branch is skipped, and the `agent()` sequence diverges from the journaled one from that point — the prefix cache is then blind for the rest of the run. None states this, logs it, or bounds it (A2 and A1 also change the retry *prompt*, guaranteeing the divergence).
2. **Queue wait counts against the timer.** The timer starts at enqueue and the harness queue is FIFO with observed waits of 1,580 s at cap 2. None subtracts queue time or derives timeouts from measured waits; A1's 5-minute probes are the extreme case, A2's 15-minute judges/integrators the moderate one, A3 is safe only because its waves never exceed the cap.
3. **Lifetime-cap accounting across resumes.** None says whether replayed (cached) `agent()` calls count toward the 1000-per-workflow cap; A1 (≈740) is exposed, A2's slicing assumes they do not, A3 never asks.
4. **Permission prompts mid-wave.** All rely on the smoke run; none distinguishes "blocked on a permission dialog" from "hung" — the H6 receipt would mark the card failed while the dialog is still pending.
5. **Schema keyword support is UNVERIFIED.** A3 and A1 use `pattern`, `maxLength`, `minLength`, `minimum`, `maximum`; the observed run used only `type/enum/required`. If the StructuredOutput validator ignores them the `minItems`-style guards silently weaken; if it rejects them the agent loops on validation errors. Only A2 stays inside the observed keyword set.
6. **`v2:` cache-key composition.** Every design's smoke→full replay claim rests on the documented prefix rule; only A2 proposes to measure it (§10a). None has a fallback if the cache is purely positional and the smoke/full sequences differ before the card chain (A1's first wave reorders calls relative to its smoke).
7. **`seen` does not persist across runs.** R2/R3 reviewers restart with an empty `KNOWN` set, so R1's refuted findings re-enter (A2 writes `refuted.json` to disk but never reloads it into `seen`; A3/A1 never write it).
8. **Budget-throw fan-out.** Once `budget.spent() ≥ total`, every remaining `agent()` throws; all three retry once per call (A2 twice with a narrower prompt) and then walk every remaining loop iteration to a typed block. Bounded, but hundreds of instant `threw` ledger rows and no early exit on the budget error message.
9. **Cap arg vs actual cap.** `cap/fleet/wave_size` come from args; no design has the setup agent assert `nproc` against the arg, so a stale arg after a resize silently mis-sizes waves (correctness-neutral, cost-relevant).
10. **Phase-entry `model` field.** A1 and A2 override `model` inside Build without declaring it on the meta phase entry; none of the three documents whether a meta phase that is only ever referenced via per-call `phase:` opts (A2's `Integrate`) satisfies "titles must match `phase()` calls".
11. **Completion-order content in the synthesizer prompt.** A2 and A1 embed the ledger in push order; A3 avoids it but none sorts the ledger by `(role, id, attempt)` before any prompt use.
12. **Unchecked revert results.** All three discard or barely check the revert integrator's return (A2 L1394, A3 L1181 checks only `status`, A1 L966), so a failed revert leaves the integration branch ahead of the script's `head` with no typed state.
