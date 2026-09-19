# Design v2 — the implementation workflow for the Space rebuild (design-v1 revised: the critic's 38 gaps closed, every mechanism now exercised by an adversarial fake-harness drive)

- **Synthesizer:** design-v2-final (reviser pass over design-v1), Claude Fable 5.1, 2026-09-19. Read-only research; nothing under `/workspaces/agent-skills-toolchain` was modified; no `*.hf.space` URL was called; no token was sought; no MCP connector that writes, launches or bills was used. Scratch work (the §7.2/§9/§13 artefacts and their checks) lives under `scratch/revise-v2/`.
- **Inputs read in full:** everything v1 read (see its header: `DESIGN_BRIEF.md`, `JUDGE_RUBRIC.md`, J1/J2/J3, A3 base, the A1/A2 grafts, `WORKFLOW_TOOL_REFERENCE.md`, `DECISION-QUEUE.md` resolved decisions, the CORRECTED lines, lens-4 §C-§F) **plus `design-v1-critique.md` in full** — 38 gaps (C-1..C-38: 6 blocking, 16 major, 16 minor) and the critic's own adversarial drive (21 scenarios, 61 assertions, 19 real failures). The judges' reports remain the standard for anything the critic did not mention. Decisions are law: every DQ resolved decision is carried in §4.0 exactly as v1 carried it.
- **What changed:** all 38 gaps are resolved in the body with mechanisms — in `gate.sh`, in `script.js`, or in the prompt contract — never as sentences. **Appendix B maps every C-id to its resolving section.** The three v1 blocking defects that were design-level (import-app RED by construction, fix cards nobody wrote, journeys collected by the wrong suite) now have mechanisms that the drive exercises end to end.
- **Mechanical results (scratch dir `revise-v2/`):** `bash -n gate.sh` OK; all embedded Python compiles (13 heredocs + 3 one-liners, checked mechanically); the schema walk over §9 passes clean (34 object nodes, 7 roots, `required ⊆ properties`, no empty enums, no cross-namespace collisions); `node --check` passes on the assembled §13 (checked in its ESM-factory form and as an async-IIFE wrap, since the plain body contains top-level await by design); the gate's control path dry-runs green 22/22 in a throwaway repo (self-pin exit 66, typed RED ledger, identical `LEDGER_DIGEST` across two executions while `LEDGER_SHA256` differs, tampered baseline RED, conditional `import-app`, journeys `needs=` counting, claim-lint, per-`Card:` waiver counting); **the adversarial fake-harness drive (`drive.mjs`: the critic's 21 scenarios adapted + 16 new ones + the 4 v2.1 scenarios S38-S41 = 41 scenarios, 107 assertions) passes 107/107** (98/98 over the original 37 at v2).
- **What the v2 drive caught in my own drafts (fixed in the script, never in the assertions):** (1) a protected-ownership contradiction — the gate's ownership rule and the script's `validateCards` disagreed on who may write a protected path; resolved coherently: ownership = `MANIFEST_MIN` of the card ∪ `protected_touch` (C-21); (2) the synthesizer was blocked by the budget guard after a HALT, violating C-7/F-45 — `budgetOk(label, exemptFromHalt)` now exempts it (that reserve is what it is FOR); (3) a not-ready promote run advanced `next_args.stage` to `done` — now `(ready ? 'done' : 'promote')` (C-9). Assertions that the critic itself marked as encoding a v1 defect are flipped to the intended behaviour and marked `[flipped: …]` in Appendix C; two of my own draft assertions were wrong and are marked `[corrected, not a flip: …]`.
- **v2.1 (in place, after critic-v2's audit — verdict `revise`, 0 blocking):** critic-v2 found 3 majors + minors V-4..V-11 (its §0 header says "9 minor"; its own table lists 8 — see Appendix D) and confirmed all 38 C-closures. Applied here: **V-1** `assertCommon`'s receipt handling is now genuinely log-only — the card is never nulled (drive S38 tests a REMAINING phrase, not the removed one); **V-2** card 01's journeys conftest is pinned byte-for-byte to the self-contained path-scoped `pytest_collection_modifyitems(config, items)` hook (`import pytest` included — the dry run proved a conftest naming `pytest` without importing it is ruff F821 and dies at collection), `journey` is registered in `pytest.ini` `markers`, and a both-collections DoD line catches an inert or over-scoped marker at card 01 (drive S39; the dry run implements exactly the pinned bytes); **V-3** an R1 `plan-needs-repair` now relaunches `stage=plan` with `plan_defects` populated in every stage (drive S40); **V-11** a journeys author reporting SUCCESS over a red `journeys-only-tests` gate is refused before the merge (drive S41). The drive grew to 41 scenarios / 107 assertions; all checks re-run green.
- **UNVERIFIED (designed around, marked inline):** everything v1 listed (setTimeout in the sandbox; the cache-key composition; StructuredOutput `pattern/maxLength/minimum` support — still removed from the schemas and enforced in JS; replayed calls counting toward the 1000-agent cap — still assumed yes; every wall-clock number — **the v2 drive runs a fake harness and yields no timing evidence**; Codespaces idle timeouts; how permission prompts surface for concurrent subagents) plus the v2-new open items: whether the optional torch wheel is in the P0 venv (Q2, decides card 08a's manifest via `args.torch_in_venv`), whether `gradio[mcp]` installs (Q3), the `libsrc` wheel-source layout for apicheck (C-16), and the budget-throw-message regex: `run()` HALTs with no retry fan-out when a thrown call's text matches `/budget|ceiling|spend/i` — the real harness throw text is UNVERIFIED (v2.1 V-9 re-lists it; if the message differs the HALT never fires and the miss degrades to typed, retryable `not_attempted` starvation, bounded by the per-call `budget.remaining()` guard).

## Thesis in one paragraph

V1's skeleton stands after the critic's review — one deterministic gate, one script with four `args.stage` runs, six roles, plain-JS control flow, owner checkpoints as data — but the review proved that five of its mechanisms were still sentences (RED-by-construction `import-app`, fix cards in memory, journeys inside the default suite, a DAG asserted only at plan time, R2/R3 allowed to say `ready` over a confirmed staging finding) and that its failure rows starved silently. V2 closes all 38 gaps with mechanisms: every conditional step degrades to a recorded non-blocking state instead of RED-by-construction; review fix cards are first-class cards committed on a mutable `plan/fixes/` by the single writer; journeys are a separate pytest collection run only by `--journeys` with `needs=` counted; the DAG is recomputed per wave from the live status map and a parked root blocks its dependents before a single lens is spent; no R2/R3 path can emit `promote-production` over a confirmed critical/high staging finding; every checkpoint row and parked entry carries a reason and a suggested next action. The whole §13 script is then driven against a fake harness — the critic's scenarios plus sixteen new ones aimed at exactly these gaps — 107 assertions across 41 scenarios after the v2.1 extension, all passing, with the three real defects the v2 drive caught fixed in the script and the four v2.1 scenarios aimed at critic-v2's majors. Cost: ≈ 335-350 agents across all runs (≤ 110 per invocation at cap 2), ≈ 28-29 h wall-clock at cap 2 (5-7 invocations), ≈ 20-22 h at cap 14; the coverage matrix keeps all 136 v1 rows and adds §12.7 for the v2 mechanisms.

---

## 1. Adopted principles (ids) and how conflicts between lenses were resolved

### 1.1 Principles adopted (unchanged from A3 except where marked ★)

| Lens | Adopted | Adopted with a narrower mechanism | Cut (see §1.4) |
|---|---|---|---|
| Doctrine D-n | D-2 freeze+hash contract · D-3 ground first (base sha via `args`) · D-5 file-disjoint units, real DAG · D-6 TDD red-proof (confirm-RED by a fresh agent) · D-7 smallest check ladder, empty check set = fail · D-8 two strikes then park (fingerprint in JS) · D-12 one shared `taskDone()` reducer (★ twelve conditions, §5) · D-13 two mechanically independent signals (★ builder digest === verifier digest) · D-14 both-states proof of every gate (★ `--self-test` on every clean gate) · D-15 verifier never authored · D-16 refute-first, enumerated verdicts · D-17 overclaim = rewrite the sentence · D-19 write the algorithm · D-20 typed terminal state per agent · D-21 null-tolerant, typed drop receipts · D-22 resume-safe by construction (★ git-state idempotency is the resume; the cache is a speed-up) · D-24 gates decide, judge vetoes (★ a dropped judge is "unavailable", never "satisfied") · D-25 journeys against the packaged deliverable (★ H1-H7) · D-27 structured handoffs · D-28 owner-only actions · D-30(b,c,d) | D-1 (card on disk at a sha; prompt carries path + DoD lines) · D-11 (artifact = branch + `.gate/last_run.digest` + `plan/status/<id>.json`) · D-23 (dry counter kept; DoD inversion is the veto judge's last-round mandate, ★ fed with `probesUsed`) · D-26 (one verifier with an ordered rubric) | D-4 · D-10 · D-18 · D-29 |
| Tool-native T-n | T-1 · T-2 · T-4 · T-5 · T-6 · T-7 · T-8 (★ rank order inside barrier waves) · T-10 · T-11 · T-12 · T-13 · T-14/T-15 · T-16 (★ `status:'reused'` on an existing green branch) · T-17 · T-18 · T-19 · T-20 · T-21 · T-22 (★ smoke run + cache settling experiment) · T-23 · T-24 · T-25 | T-3 (only the JS predicate says `satisfied`) · T-9 (agent-created worktrees; ★ persona card uses a history-free clone) | — |
| External S-n (research-3) | S-1 · S-2 · S-3 · S-5 (★ oracle reset before pytest) · S-6 (★ tamper idioms) · S-7 · S-11 · S-12 · S-14 · S-15 · S-16 · S-17 · S-18 · S-19 · S-20 · S-21 · S-22 · S-23 · S-24 | S-4 (★ H1-H7 seams written after the wave, hidden by time) · S-8 (three scripted mutants, ★ mandatory and all killed) · S-9 · S-10 · S-13 | S-25 |
| External DEEP | S-1..S-9, S-12, S-14..S-22; S-11 (no swaps) | S-10 · S-13 | — |

### 1.2 Where the two external runs disagree, and which is followed

Unchanged from A3 (pairwise judging → DEEP; held-out tests → DEEP adapted as post-wave journeys; mutation testing → DEEP with scripted mutants; process monitor → neither; cross-family critic → degraded to fresh Claude at `xhigh`). One addition: on state probes vs cache, A1 (probe before every cached sha) vs A2 (git-state idempotency), this design follows A2's mechanism and A1's intent: one live setup probe per invocation (its prompt carries `launched_at` in `git` resume mode) returns the live heads and merged ids, and the merged set is read from git, never from memory (§10.1).

### 1.3 Conflicts between lenses and decisions, and the resolution

C-A … C-L unchanged from A3 (files+git over prompt embedding; never `isolation`; author ≠ builder with an oracle lock; JS `satisfied()` with a veto-only judge; dry counter + inversion mandate; no agent pushes; local integration branch + bundles until the owner creates the remote; M-5 one release integrated incrementally; D-10 cut at the root; no cross-vendor judge available; G-15/G-19 decisions win; six verbs = one verifier role in modes). Added in v1 (all still standing):

| # | Conflict | Resolution |
|---|---|---|
| C-M | lens-4 "fixture #1 must precede step 4's merge" vs wall-clock (all three designs made it optional) | **lens-4 wins.** Card `platform-04-streamparser` carries `owner_precondition: fixture1_path` and is `blocked_on_owner` until the owner records the metered call; everything downstream waits (typed `not_attempted: dependency-blocked`). R1 therefore has an owner stop after cards 01-03b; the C0/C1 checkpoints say so (§2.1). |
| C-N | A3's Q4 (defer gateway hardening, harness, catalog, CI to a second build run) vs decision **G-3 "Both, equally"** (API items first-class) and M-3 | **The decision wins.** Q4 is deleted; cards 07, 11, 12, 13a, 14 stay in R1's DAG; G-3 is named in the decision sheet (§4.0) with `against_recommendation: true`. |
| C-O | G-15/G-24 "the only credential in the container is one narrowly scoped inference token" vs M-2 (the CPU Space must reach both the HF router and the private worker Space) | **The decision stands; the count needs an owner clarification.** §4.0 row `G-24-clar`: one fine-grained token scoped to inference-provider calls + read access to the worker Space; only if HF cannot combine those scopes does a second read-only worker token exist. Card 08b reads `HF_TOKEN` for both unless `WORKER_TOKEN` is set. The C1 `set-staging-secrets` action asks the owner to record `owner_approvals.token_topology`. |
| C-P | M-3 "promotion only after the 12-prompt harness passes" vs M-5 "everything in one release" (the release will contain entries the paid harness has not measured) | **Both decisions stand; a policy clarification is recorded for approval** (§4.0 `M-3-clar`): `core/catalog.py` exposes only entries with `admission: passed`; pending entries are hidden from the selector and `/v1/models`; at least one entry must be `passed` (owner runs the harness on staging, C2 `run-harness`) before promotion. |
| C-Q | G-19 boundary ("nothing in the workflow authors or restores the clause") vs the absence test that must recognise the clause | **The boundary wins.** The owner generates `tests/fixtures/persona_boundary.json` (sha256 of every 6-word shingle of the normalised clause) off-workflow with `tools/make_boundary_fixture.py`; the test compares shingle hashes; no agent ever holds the clause or its fragments; card 13b is `blocked_on_owner` until the fixture exists. **V2 strengthens the mechanism (C-21):** card 01 delivers the generator, the author prompt carries an explicit FIXTURE COPY STEP, the gate pins `--boundary-sha256` (a new owner field, `persona_boundary_fixture_sha256`), and the protected-path rule is an ownership rule (a card may write a protected path its own manifest declares), not a 01-only ban. |
| C-R | T-14/T-15 replay purity vs correctness under an UNVERIFIED cache key | **Correctness never depends on the cache.** `args.resume_mode='git'` (default): every invocation is fresh; git state (existing green branches → `reused`, `plan/status/*.json` on the integration branch → merged set) is the checkpoint. `'cache'` is allowed only after the smoke run's settling experiment (§10.1). |
| C-S | inference-perf-3 CORRECTED ("LogitsProcessor with a CPU unit test, or remove the placebo") vs a gate venv without torch | **Decided as a card with an owner question (§15 Q2).** Default if unanswered: remove the placebo (slider, preset key, README sentence; the API accepts `presence_penalty` only when 0 and returns 400 otherwise). If the owner adds the CPU torch wheel to the venv at P0, card 08a implements `worker/penalty.py` with the test. **V2 wires this into the manifests (C-14):** `args.torch_in_venv` decides `worker/penalty.py` inside `MANIFEST_MIN` and inside the planner's prompt — the required-files check and the plan can no longer contradict each other. |

### 1.4 What was cut, what the judges made me re-add, and why each cut is still covered

| Item | Status in v1 | Still covered by / why re-added | Matrix rows |
|---|---|---|---|
| Separate **refuter** agents (3 per finding, majority) | cut (kept) | one `verifier mode:'refute'` per fresh finding; `holds` needs an executed reproduction | F-12, F-30, S-AP-1, S-AP-14 |
| Separate **auditor** / **critic** per task | cut (kept) | decision sheet + cards quoting only CORRECTED text (JS asserts `corrected_text` per cited id); `verifier mode:'plan'`; review lens `decision-fidelity`; DoD lines are commands with exit codes on both sides | F-9, F-10, F-16, F-19 |
| **Judge panel** (3 votes → `satisfied`) | cut (kept) | `satisfied()` in JS + one veto-only judge; **a dropped judge is `veto-unavailable`, never satisfied** (J2 A3-3) | AP-6, S-AP-11 |
| **Synthesizer-verifier** agent | ★ re-added conditionally | rows are compared in JS; **only when they differ** a `synthesizer mode:'fix'` bash call rewrites the on-disk rows from the script's table (J1 G13: the file and the checkpoint object could disagree before) | F-40 |
| Per-**wave LLM review** | cut (kept) | gate after every merge; `--clean --self-test --journeys` per wave; one whole-tree LLM review loop | F-34, F-32 |
| Dedicated **conflict-resolver role** | cut (kept) | `integrator mode:'conflict'`, fresh call, re-gated | F-32 |
| **Transcript monitor** | cut (kept) | tamper/idiom/claim lints in the gate; commit-per-step | S-AP-3, SD-AP-2 |
| **`mutmut`** | cut (kept) | `gate.sh --mutants`: ★ written ≥ 1, ALL killed, tree unchanged after the round-trip — mandatory in `taskDone()` (J1 A3-3, G4) | F-20, SD-AP-3 |
| **Hidden held-out branch** (ACL) | cut (kept); ★ content re-added | A1's seams H1-H7 are the journeys spec, written after the wave whose card merged, skipped-with-reason `needs=<card>` until then, counted by the gate; a seam still skipped after its card merged is a synthetic blocking finding (J1 G7, J3 graft 8, A2 gate step 13) — **v2: a separate pytest collection, default-deselected, `--journeys` selects it (C-4)** | S-AP-4 |
| `isolation:'worktree'` | cut (kept) | agent-created worktrees; ★ `repo_toplevel` prefix test + `git_common_dir === <repo>/.git` (J1 D1) | F-1, F-33 |
| **Plan-critic** role | cut (kept) | `verifier mode:'plan'` + `validateCards()` throws at script start + owner C0 — **v2: `checkPlan()` runs in every stage, so R1 never approves or builds a defective plan (C-19)** | F-13, F-14, F-46 |
| **DoD-inversion scout** | cut (kept) | the veto judge's last-round mandate ★ receives `probesUsed` (A1 §13.7) | AP-11 |
| **Pre-verifier** for UNVERIFIED findings | ★ re-added | J1/J3 reproduced that A3's F-11 row was prose: the plan stage now runs `pipeline(unverified_finding_ids, verifier mode:'preverify')` before the planner; a REFUTED id cannot become a card (JS) | F-11 |
| **Decision-sheet table** in the design | ★ re-added | J3: A3 delegated the sheet to the planner and never named G-3/G-2. §4.0 carries the table with `against_recommendation`/`dq_line`; the planner's `decisions[]` must mark the five ids (JS) | F-9 |
| **Revert-proof / negative control** | ★ re-added | J1 G4/J2 graft 11: `gate.sh --revert-proof <oracle>` re-runs the final DoD tests on the pre-implementation tree (must be red) and every mutant is a negative control — **v2: the test set also includes builder-added `tests/unit/*` (C-28)** | F-19, F-20 |
| **State-probe agent per card** | declined as an agent; ★ folded | a per-card probe call replays from the cache it should check; instead: one live setup probe per invocation (`launched_at` in its prompt under `git` mode) returns live heads, merged ids, remotes; JS refuses a stale `integration_sha_at_launch` (J1 G2, J2 CG7 — see Appendix A) | F-43 |
| **R0 grounding trio** | ★ re-added | A2 §13: api-ledger (planner mode) ‖ catalog provenance (verifier mode, raw Hub reads saved) ‖ pre-verifiers, all before the planner | F-8, F-11, F-25, F-39 |
| **Scout:reuse / de-sloppify / minority report** | cut (kept) | not failure modes in the matrix | — |
| **Cross-vendor judge** | unavailable (verified by A3) | fresh Claude at `xhigh`; logged `judge_rail` | AP-6 |

---

## 2. Run structure

One script, four runs selected by `args.stage`; a run never pauses for a human; every outward-facing action is a checkpoint object computed in JS and executed or approved by the owner in their own message. R1 has owner stops inside it (fixture #1 before card 04, the persona-boundary fixture before card 13b, the worker-checkpoint decision before card 08c — each a typed `blocked_on_owner` row, never a guess), every invocation is sliced (`args.max_agents_this_run`, default 110 at cap 2 ≈ 5.5 h) so a run ends inside the Codespace's attention span, and **every checkpoint row and every parked entry carries a machine-readable `reason` and a suggested `next` action** (C-22) — the owner never has to reverse-engineer a state from a row label.

### 2.0 P0 — orchestrator pre-flight (outside the script, before R0)

1. `mkdir -p /workspaces/space-build /workspaces/space-build-tools /workspaces/space-build-bundles`; copy `libsrc/` to `/workspaces/space-build-libsrc`; `chmod -R a-w` both snapshots and libsrc. Nothing under `/tmp`, the grill folder or the toolchain repo (JS refuses). **Bundles accumulate under `/workspaces/space-build-bundles/<nonce>/` and only their manifest is written into the grill tree (C-17: the grill folder is rsynced by the owner's sync loop every five minutes and must not be the bundles' live directory).**
2. **Create the 3.12 venv** at `/workspaces/space-build-venv` offline from the pinned wheels (`--no-index --find-links /workspaces/space-build-libsrc`): ruff, pytest, fastapi, gradio, gradio_client, transformers, huggingface_hub — and, only if the owner answers §15 Q2 with "add it", the CPU torch wheel (recorded as `args.torch_in_venv`; it decides `worker/penalty.py` inside `MANIFEST_MIN`, C-14). **This is the only place in the whole workflow where anything is ever installed (C-31):** every later stage — the setup probe included — asserts the venv EXISTS, runs `python -V`, and reports `FAILED` if it is absent; no prompt ever says "create if missing".
3. Write `gate.sh` (§7.2, byte-for-byte) to `/workspaces/space-build-tools/gate.sh`; write `baseline.json` (`{base_sha, baseline_collected, skipped_ids[]}` from `pytest --collect-only -q` at `base_sha` under the venv, expected 73); compute `args.gate_sha256`, `args.baseline_sha256` with `sha256sum`. The gate verifies its own bytes against `--gate-sha256` on every run and refuses otherwise (exit 66); the baseline file is verified the same way (J1 CG1). **The self-test's false-claim fixture pair is delivered by card 01** (`tests/fixtures/gate/false-claim.patch` + `false-claim-target.txt`, C-2; v2.1 V-4 correction) — only the temp worktree and the crafted, lint-matching commit message are gate-created. P0 therefore runs `BROKEN_SHA=<base> gate.sh --self-test --profile bootstrap --base <base>` once: the bootstrap profile proves `broken_red=true` live and tolerates `fixture-not-yet-delivered` (a full-profile `--self-test` before card 01 would report `fixture-missing` and go RED by design); the setup agent re-proves it live at every invocation.
4. Snapshot the toolchain repo status **excluding `docs/grills`** → `args.toolchain_status_sha256` (C-17: the owner's grill sync loop legitimately writes `docs/grills` every five minutes; that is not a mutation of the executed fleet); `nproc` → `args.cap = min(16, nproc − 2)` (the setup agent re-reports `nproc`; a mismatch throws `cap-mismatch`); `args.wave_size ≤ cap`.
5. Regex-scan every input file the agents will read for secret shapes; redact before launch. The trigger message states the `AUTHORITY` rules and carries no secret.
6. Compute `args.unverified_finding_ids` (every `verdict: **UNVERIFIED**` id in `workflow-findings.md`: critic-1..5 today), `args.against_recommendation_ids = ['G-1','G-3','G-2','M-5','G-15+G-24']` (the five decisions taken against the recommendation, DQ lines 85-123), `args.catalog_candidates` (the three named repos + the two quantised candidates).
7. Owner checklist (recorded in the run report as owner actions, never done by agents): send the other agent's stop notice; disable both Windows scheduled tasks; rotate its token; revoke the pasted token; delete `NF4_EXPORT`/`NF4_UPLOAD_TOKEN`; set the Codespace idle timeout to the maximum and keep a client attached; disable the HF connector's write tools for the build session; `gh repo list --json name` and the Hub namespace listing saved as the launch snapshot for the post-run comparison (§2.4). **Off-workflow, before card 13b can build: run `tools/make_boundary_fixture.py` (delivered by card 01) over the clause file at a path only the owner holds, and record `owner_approvals.persona_boundary_fixture_path` AND `owner_approvals.persona_boundary_fixture_sha256` (C-21 — the sha is what the gate pins).**
8. **Smoke run** (`args.smoke=true`, R1 with one S card, owner attending): surfaces permission prompts, worktree mechanics and every schema; **the review loop is skipped in smoke mode (C-33)** so the smoke stays one card wide. **Settling experiment** (A2 §10a): resume the smoke run once unchanged and count `key` matches in `journal.jsonl`; change `args.max_rounds` and resume again. Only if both replays hit may the orchestrator set `args.resume_mode='cache'`; otherwise `'git'` stays (§10.1).

### 2.1 The four runs

| Run | `args.stage` | Preconditions (asserted by the script from `args` + the setup probe) | Produces (durable) | Checkpoint object emitted |
|---|---|---|---|---|
| **R0 plan** | `plan` | `build_repo` at `base_sha`; venv EXISTS; pinned gate + baseline; snapshots read-only; `unverified_finding_ids`, `against_recommendation_ids`, `catalog_candidates` in args | branch `plan/<nonce>`: `plan/decisions.json` (rows with `against_recommendation`, `dq_line`; incl. the clarifications of §4.0), `plan/preverified.json` (executed verdict per UNVERIFIED id), `plan/api-ledger.json` (symbols + `known_bad[]` regexes), `plan/cards/*.json` (22 cards), `plan/index.json`, `AGENTS.md`; `<grill>/evidence/catalog/*.json` (raw Hub reads incl. `has_visual_tensors`) | **C0** `approve-plan` (→ `args.plan_sha`) **or `repair-plan` (C-19: any script or plan-verifier defect yields repair-plan, never approve-plan; `next_args.plan_defects` carries the defects and the relaunch runs the planner in REPAIR MODE)**, `record-fixture-1` (REQUIRED before card 04 can build; the recording tool arrives with card 01, so the stop happens after R1's first invocation), `record-boundary-fixture` (before 13b), `decide-worker-checkpoint` (before 08c) |
| **R1 build** | `build` | `plan_sha` approved; setup probe: `plan/<nonce>@plan_sha` merged into `integration/<nonce>` (first commit), live head == `integration_sha_at_launch` (throws `stale-launch-args` if not), `remotes == []` unless approved, `nproc` matches `cap`; `owner_approvals` present (fields may be null); **`checkPlan(idx)` re-run here (C-19): a defective plan throws `plan-needs-repair` before any author or builder is launched** | `integration/<nonce>` with `plan/status/<id>.json` per merged card; per-task branches `tests/<id>-<nonce>`, `task/<id>-<nonce>`, `task/journeys-<tag>-<nonce>`; review fix cards committed on `plan/fixes/` (C-3); `.gate/last_run.{json,digest}` per checkout; incremental bundles under `/workspaces/space-build-bundles/<nonce>/` + manifest in the grill tree; `RUN-REPORT-<nonce>.md`; `build-bundles/<nonce>/status.json` (rows with reason+next, `seen_keys`, last clean gate — the input of the next invocation); CI files written and unit-tested, never executed | **C1** `create-github-repo`, `create-staging-spaces`, `set-staging-secrets` (with the token-topology clarification), plus whichever of `record-fixture-1` / `record-boundary-fixture` / `decide-worker-checkpoint` is still missing; `blocked_on_owner[]` (owner-precondition cards + deferred DoD lines, each with `field`/`why`/`next`/`severity`, C-22), `parked[]` (each with `reason` + `next`), `api_unresolvable[]` (C-16), `retry_parked_suggested[]` (C-8), `next_args` (`stage: 'build'` again while any card is `blocked_on_owner`/`not_attempted`/parked, else `'stage'` — it never advances on a halt, dry stop or budget stop, C-9) |
| **R2 stage** | `stage` | `github_repo_url`, `staging_evidence_dir`, `integration_sha_at_launch` == live head == `last_clean_gate.head_sha`, `fixture1_path` | evidence findings → refuted → fix cards through the same inner loop (local-level only; staging/owner-level findings become `blocked_on_owner` rows — **a confirmed critical/high one stops the run before any promotion action can be computed, C-6**); `evidence/staging/<sha>/` in the repo; updated bundles; report | **C2** `run-hf-job-quantize` (only if `worker_checkpoint_decision.needs_export`), `run-harness` (M-3-clar: ≥ 1 `passed` entry), `promote-production` **only when `status === 'ready'` AND `owner_approvals.production_space_head === base_sha` (or `adopted_delta_sha`) AND `blocked_on_owner` is empty — `ready` is false while any owner-critical finding stands (C-6), so the action is unreachable in that state** |
| **R3 promote** | `promote` | `production_evidence_dir` (running sha, canary ×3, rollback-drill record) | final report; `owner_actions[]`; **`rollback` only on confirmed critical/high evidence (C-6) — an unavailable or malformed evidence read never triggers a rollback, it blocks** | **C3** `none` or `rollback` with the exact `promote.py --to <last_good_sha>`; `next_args.stage` stays `promote` until the evidence is clean (C-9) |

The R2/R3 verifiers read files; they never call a Space. The canary and the rollback drill are executed by the CI workflow card 14 wrote (Trusted Publisher OIDC; `hf spaces wait --timeout`; `fetch_space_logs(build=True)` on failure; 16-token generation ×3 = pass^3; `/healthz.git_sha` == pushed sha and never `unknown`; visibility assertion `private`, not `protected`; last-known-good comparison; log tail on failure — A1 §12 S/AP-12) and the owner triggers that CI run. **`EXPECTED.json` is written by CI at deploy time from the contract in `tools/expected.py` (card 14 ships the tool, C-35) — agents never write evidence files.**

### 2.2 The checkpoint object (computed by the script; the synthesizer only renders it)

```json
{
  "stage": "build", "nonce": "r1a", "status": "ready|blocked|failed", "halt": null,
  "head_sha": "…", "integration_branch": "integration/r1a",
  "actions": [ { "id": "C1-1", "kind": "create-github-repo", "why": "G-1a …", "exact_steps": ["gh repo create …", "git -C /workspaces/space-build remote add origin <url>", "git -C /workspaces/space-build push -u origin integration/r1a plan/r1a", "post-check: gh repo list --json name shows exactly one new repo"], "blast_radius": "new private repo", "rollback": "…", "cost_estimate": "0", "evidence_paths": ["…/.gate/last_run.json", "…/status.json"] } ],
  "blocked_on_owner": [ { "task_id": "platform-04-streamparser", "field": "fixture1_path", "why": "owner-precondition:fixture1_path", "next": "owner records owner_approvals.fixture1_path; relaunch stage=build", "severity": null } ],
  "parked": [ { "task_id": "…", "state": "parked", "reason": "fix-exhausted|agent-null:…|no-progress|oscillation|secret-shaped-output|integration:…", "next": "retry_parked|inspect the trail|review fix card" } ],
  "rows": [ { "task_id": "…", "state": "merged+gate-green|parked|reverted|blocked_on_owner|not_attempted|dropped_null", "reason": "…", "next": "…", "head_sha": "…", "dod_done": 3, "dod_total": 4, "dod_deferred": 1 } ],
  "api_unresolvable": [ { "task_id": "platform-08b-worker-backend", "symbols": ["transformers.AutoModelForImageTextToText"] } ],
  "stop_reason": "satisfied", "agents": 97, "replay_risk": false,
  "last_clean_gate": { "verdict": "pass|fail|gate-unavailable", "head_sha": "…", "digest": "…", "why": null },
  "next_args": { "stage": "build", "plan_sha": "…", "integration_sha_at_launch": "…", "resume_mode": "git", "prior_status_path": "…/status.json", "last_clean_gate": { "head_sha": "…|null", "digest": "…|null" }, "retry_parked_suggested": ["…"], "plan_defects": [] }
}
```

`kind` is an enum: `approve-plan · repair-plan · record-fixture-1 · record-boundary-fixture · decide-worker-checkpoint · create-github-repo · create-staging-spaces · set-staging-secrets · run-hf-job-quantize · run-harness · promote-production · rollback · none`. Every entry is computed in JS from typed ledger states; no agent can add or remove an action. `status` is `ready` only when the stop reason is `satisfied`, no `HALT`, the integration branch is not dirty, every card row is merged or a reported parked leaf, **`blocked_on_owner` is empty and no confirmed critical/high owner finding stands (C-6)**; `promote-production` is emitted only from a `ready` R2 with the F-38 head recorded. `rows[].reason` and `rows[].next` are mandatory on every row (C-22); `not_attempted` rows are retryable by definition (§10.1) and the parked ones whose reason matches `RETRYABLE_RE` are exactly what `retry_parked_suggested` lists (C-8). `next_args.stage` never advances past a stage that did not finish (C-9): the table is `plan → build|plan`, `build → stage|build`, `stage → promote|stage`, `promote → done|promote`.

### 2.3 Invocations, slicing and resume (F-43, F-44, F-45; C-8)

- Every invocation runs the setup probe first; in `resume_mode='git'` its prompt carries `launched_at`, so it is always live and reports: `integration_head_live`, `branch_heads[]`, `merged_on_integration[]` (from `git ls-tree integration/<nonce> plan/status/`), `remotes[]`, `nproc`, the gate/baseline sha256s, `prior_rows` + `seen_keys` from `args.prior_status_path`. **JS seeds the row table from git — merged is what git says — and treats prior rows as detail, never truth (C-8):** a prior parked row whose reason matches `RETRYABLE_RE` (`not_attempted:…`, `starved:…`, `agent-null`, `threw`, `timeout-or-dialog`, `integration:not-merged:null`, `fixcards-unavailable`) is re-driven automatically, because nobody ever judged that work; other parks persist unless `args.retry_parked[]` names them (the checkpoint's `retry_parked_suggested` computes exactly that list); `not_attempted`, `blocked_on_owner`, `dropped_null` and `reverted` prior rows are never adopted — they are re-evaluated live. The review `seen` set seeds from `seen_keys` (J2 gap 7).
- `args.max_agents_this_run` (110 at cap 2) with a **per-chain reservation of 7 agents** (`agentsOk`): a wave is admitted only when 7 agents per chain remain in the slice; a worst-case chain (≈ 20 `agent()` calls: 2 authors + 2 reds + 3 builds + 3 verifies, each retryable once) can outrun that reservation mid-chain and then degrades to typed, retryable starvation (C-8) — nothing is lost but the promise (v2.1 V-7); otherwise the remaining cards are `not_attempted: agent-slice-or-budget` (retryable — never parked, C-8) and `next_args.stage` repeats the stage (A2 §13; C-9). Replayed calls are assumed to count toward the lifetime cap (J2 gap 3); in `git` mode there are none.
- **Starvation is a state, not a park (C-8):** any chain cut short by the budget guard, the agent slice or a HALT returns typed `starved` and lands as `not_attempted` with the reason and `next: relaunch stage=<stage> with next_args` — on resume those cards are simply built (their author/builder branches survive and return `reused`).
- Owner stops inside R1 (fixture #1, boundary fixture, worker decision) end an invocation with `status: 'blocked'`; the owner records the field and relaunches with `next_args`.

### 2.4 Outward-action post-checks (F-35, J1 CG5; C-17)

Self-report (`outward_actions_taken`) stays required on every schema, but it is no longer the only signal: the setup probe and every clean gate return `git remote -v` lines (JS: non-empty without `github_repo_url` → `HALT`), the clean gate returns the branch count, and both return the toolchain status hash — computed as `git status --porcelain -- . ':!docs/grills'` on the toolchain repo, because the owner's grill sync loop writes `docs/grills` every five minutes and that is not a mutation of the executed fleet (C-17); a mismatch → `HALT`. The synthesizer report lists the owner's Hub post-checks (`gh repo list --json name` unchanged vs the P0 snapshot; namespace listing unchanged) as owner runbook steps — those two remain **O** because the script must not hold a Hub token.


## 3. Agent roles and the separation table

Six roles; a `mode` narrows the task without changing rights; every call is a fresh `agent()`.

| Role | Modes | May write | May never | Votes on | Effort | Reading-list cap |
|---|---|---|---|---|---|---|
| **planner** (R0) | `plan` (incl. REPAIR MODE re-runs, C-19), `api-ledger` | `plan/**`, `AGENTS.md` on `plan/<nonce>` | code, tests, gate files | nothing | high (`api-ledger` medium) | resolved decisions + lens-4 §B-§F + CORRECTED lines + red-team §1-§3 + `plan/preverified.json` (+ its own prior plan and the defect list in REPAIR MODE) |
| **author** | `tests`, `journeys` | new test files under `tests/` on `tests/<id>-<nonce>` (journeys on `task/journeys-<tag>-<nonce>`); existing test files only when listed in `tests_allowed`; xfail/skip only for `xfail_allowed` ids; **persona cards copy the owner fixture verbatim (C-21)** | any non-test file; `system_prompt.py` history (persona card: history-free clone) | nothing | medium | card (verbatim, incl. the finding for fix cards, C-3) + `core` interfaces named in the card + api ledger |
| **builder** | `implement`, `fix` | `files_allowed` + `new_modules` + `required_files` + NEW files under `tests/unit/` on `task/<id>-<nonce>` | any existing test; protected paths outside the card's own manifest (C-21); `plan/**` (except `plan/status/` for the integrator); requirements outside `deps_allowed`; installs; outward actions | nothing (returns evidence) | high | card + decisions + api ledger + files in `files_allowed` |
| **verifier** | `plan`, `preverify`, `catalog`, `index`, `red`, `verify`, `refute`, `review`, `veto`, `evidence` | `.gate/mutants/<id>.json`, `.gate/*-<id>.json` (mode `verify`); `<grill>/evidence/catalog/*.json` (mode `catalog`) | any source/test file; any branch; approving | the ONLY role with a verdict; a `verify:pass` is admissible only when its `gate_digest` equals the builder's | medium; **xhigh** for `veto` and `risk:'security'` | mode-specific (§13 prompts) |
| **integrator** | `setup`, `merge`, `conflict`, `ff`, `revert`, `clean-gate`, **`fixcards` (C-3)** | `integration/<nonce>` (serial, single writer) incl. `plan/status/<id>.json` and **`plan/fixes/*.json` (mode `fixcards` only — the one mutable area of `plan/`)**; venv/tools under `/workspaces/space-build*` (mode `setup` only); bundles | task branches; source edits except conflict hunks | nothing | medium (`conflict` high; `merge`/`ff`/`revert`/`clean-gate`/`fixcards` low) | two cards + hunks (`conflict`); the fix cards verbatim (`fixcards`); nothing else |
| **synthesizer** | `report`, `fix` | `RUN-REPORT-<nonce>.md`, `build-bundles/<nonce>/status.json` | any branch, any code | nothing; its rows are overwritten by the script's table (mode `fix` rewrites the file when they differ) | low | the script-computed table + ledger summary (sorted) |

Separation (who authored what → who may judge it):

| Artifact | Authored by | Judged by | Never judged by |
|---|---|---|---|
| Pre-verification of an UNVERIFIED finding | `verifier mode:'preverify'` (executed probe, mechanically different from the finder's) | planner may only cite the recorded verdict; JS refuses a card citing a REFUTED id | the finder |
| Decision sheet, cards, DAG | planner | `verifier mode:'plan'` (refute-first) + `validateCards()` (throws) + JS (`against_recommendation` marks, REFUTED ids, manifest cards) + owner (C0) — **re-checked in every stage (C-19)** | planner |
| DoD tests | author | `verifier mode:'red'` (`gate.sh --only-tests` at `tests_head`: author-range tamper rules + RED for the expected reason + **digest equality with the author's own run, C-29**) | author, builder |
| Implementation diff | builder | `verifier mode:'verify'`: its own gate run must reproduce the builder's `LEDGER_DIGEST`; mutants; revert-proof (incl. builder-added `tests/unit/*`, C-28); DoD re-runs; `apicheck-extended` (C-18); `diff_stats` required (C-25) | builder (its digest is one half of the equality, never a verdict) |
| Merged tree | integrator | gate on the merged tree (digest returned) + `gate.sh --clean --self-test --journeys` per wave — **skipped only when nothing merged and the last clean gate passed at this head (C-38)** | the builder whose task was merged |
| Review fix cards | `verifier mode:'review'` + `mode:'refute'` (content) → **committed to `plan/fixes/` by the integrator `mode:'fixcards'` (C-3)** | the same inner loop (author → confirm-RED → builder → verifier) on the fix card | the reviewer (never its own fix) |
| Review findings | `verifier mode:'review'` (3 lenses) | `verifier mode:'refute'` (fresh, reproduction mandatory and **non-zero-exit on the defect, C-27**) | the reviewer |
| `satisfied` | JS predicate | `verifier mode:'veto'` (veto with reproduction only; a drop = `veto-unavailable`) | any agent |
| Run report rows | script | JS comparison; `synthesizer mode:'fix'` rewrites the file on mismatch | synthesizer |

Two preamble constants precede every prompt (§13): `PREAMBLE` (F-4; also demands `repo_toplevel` + `git_common_dir` and fixes the dummy-credential convention so fixtures cannot match the secret regex, C-32) and `AUTHORITY` (T-2: no push, no remotes, no repo/Space creation, no secrets, no `*.hf.space`, no HF Jobs, no token lookup, no installs, no foreground servers, no `git log/show` of `system_prompt.py`, no edits under `plan/` — except `plan/status/` for the integrator and `plan/fixes/` for the `fixcards` mode).

---
## 4. Task model

### 4.0 The decision sheet (`plan/decisions.json`) — law; carried here so the owner reads it in the design, written by the planner, refuted by `verifier mode:'plan'`, marks asserted in JS (F-9)

| id | decided (DQ line) | against rec. | build consequence |
|---|---|---|---|
| G-1 (original) | both write, split lanes (85) | **yes** | superseded by the revision below; kept as a row so the sheet is complete |
| G-1 REVISED / work split REVISED | Claude is the single writer, platform AND product (150-153) | — | no hand-off brief; product cards are ordinary cards in the DAG; the other agent's scheduled tasks are still guarded (F-38: `production_space_head` precondition) |
| M-1 | hybrid, hosted first (90) | — | `backends/hosted.py` first (card 03b); worker second; automatic fallback ships OFF (flag) |
| G-3 | **Both, equally** (96) | **yes** | core/UI/API split (cards 02-08); API items first-class (07, 11, 12 stay in R1; Q4 deleted) |
| G-1a / G-26-29 | GitHub SSOT, CI-only production writer, staging + 16-token canary, gate = F821 + tests + import smoke + claim-vs-diff, rollback (100) | — | card 01 gate; card 14 CI/promotion-as-code written + unit-tested, never executed in R1; `build_info.json` written by CI at deploy (the `/healthz` sha source); **a placeholder `build_info.json` with `git_sha: "unknown"` ships in card 03b so `/healthz` is testable and the canary rejects `unknown` (C-34)** |
| G-2 | leave it down until the pipeline (106) | **yes** | no rollback commit; nothing in any run touches production; the first production deploy is R2's promotion |
| M-5 | everything in one release (109) | **yes** | one production promotion; many staging promotions; every card PR-sized and staging-promotable |
| G-15 + G-24 | keep it in-container, hardened, six points (115) | **yes** | cards 09a/09b: (1) env allowlist (2) `prctl(PR_SET_DUMPABLE,0)` (3) rlimits inside a runner + `start_new_session` + `killpg` — **no `preexec_fn`** (4) fresh cwd + output cap (5) **enabled only by an operator secret flag; the UI checkbox and any API/MCP argument cannot enable it; never reachable over MCP or `/v1`** — card 05a DoD line + `tests/test_python_eval_surfaces.py` (protected) + seam H4 (6) no token files; exports off-Space (HF Job); one narrow inference token |
| G-24-clar (needs owner approval) | one fine-grained token = inference-provider scope + read on the private worker Space; two tokens only if HF cannot combine | — | card 08b reads `HF_TOKEN` for both unless `WORKER_TOKEN` is set; C1 `set-staging-secrets` records `token_topology` |
| G-19 | neutral set, cleaned, extended by Claude; no filter-evasion clause; README + tests consistent; no off-repo archive (124) | — | card 13b (history-free clone; owner-generated shingle-hash fixture; absence test protected); card 01 makes the persona-archive test repo-local **and delivers `tools/make_boundary_fixture.py` (C-21)** |
| M-3 / M-4 | curated evidence-gated `models.yaml`; harness admission; no free-text ids (132) | — | card 12 harness; card 13a catalog with provenance + `admission`; gate catalog step |
| M-3-clar (needs owner approval) | pending entries hidden from the selector and `/v1/models`; ≥ 1 `passed` entry before promotion | — | `core/catalog.py.visible()`; `tests/test_catalog_policy.py` (protected); C2 `run-harness` |
| M-2 | one worker Space, one resident model; draft deleted; lease work only in the worker; no automatic `xlarge` (137) | — | cards 08a/08b; `gpu_size` is catalog config; `assistant_model=` is a known-bad idiom |
| G-16-clar (from inference-perf-2/-5/-7 CORRECTED) | vision kept ⇒ **the worker keeps the VLM class (`AutoModelForImageTextToText`)**; `prefill_chunk_size` forbidden while that class is loaded (blocking idiom); `trust_remote_code=True` dropped; **the resident checkpoint must carry `model.visual.*`** | — | R0 catalog agent records `has_visual_tensors`; card 08c (owner decision; export HF Job if neither candidate has them); gate catalog step requires `has_visual_tensors` on local entries |
| Continue-clar (gpu-lease-3 CORRECTED + critic-4) | continuation at **token level**: worker yields a control record `{"__ctl__": {"new_ids", "finish", "prompt_len"}}`; next lease gets `prefix_ids`; `continue_final_message` only for a user Continue on a finished non-thinking turn | — | card 08a (CPU test with a fake generate: seam integrity; greedy equality) + seam H1; `continue_final_message=…reasoning…` is a blocking idiom |
| Kernels-clar (inference-perf-4 CORRECTED) | positive boot probe `importlib.util.find_spec('fla')`/`('causal_conv1d')` printed at boot; `flash-linear-attention` tested on the STAGING worker only; Triton JIT budgeted in the first lease; no `kernels`/`use_kernels` without a build check | — | card 08a (probe line, CPU-testable) + card 08d (staging-required DoD lines → runbook rows) |
| presence-penalty (inference-perf-3 CORRECTED) | LogitsProcessor + CPU test **or** remove the placebo (§15 Q2; default remove) | — | card 08a (`worker/penalty.py` **only when `args.torch_in_venv` — the manifest is derived from the decision, C-14**) or cards 06/07 (remove slider/preset/README sentence; API 400 unless 0) |
| G-13/G-6/G-14/G-16 | maximal, multi-model, expand tools, keep vision/video (164) | — | ship-but-flag decides sequencing (§4.6); video OFF at launch, images ON |
| Owner process | max concurrency; resize before the implementation workflow; keep full reports (158) | — | `args.cap`/`wave_size`; the setup probe asserts `nproc`; full reports under `evidence/`. **V2 adds two owner fields:** `owner_approvals.persona_boundary_fixture_sha256` (the sha the gate pins with `--boundary-sha256`, C-21) and `owner_approvals.accepted_findings` (the ids of confirmed medium/low staging-evidence findings the owner explicitly accepts — recorded data, never inferred, never usable for critical/high; the acceptance policy itself is §15 Q10) |

### 4.1 The card (one PR-sized task) — `plan/cards/<id>.json` on `plan/<nonce>`, merged into `integration/<nonce>` by the setup stage so every worktree can read it; review fix cards live on the mutable `plan/fixes/` and are committed there by the integrator (C-3) (schema §9.1)

| Field | Rule |
|---|---|
| `id` | `<lane>-<nn>[a-d]-<slug>`; sorted order = default priority; review fix cards are `platform-00-rf<round>-<nn>-<slug>` |
| `path` | `plan/cards/<id>.json` for plan cards, `plan/fixes/<id>.json` for review fix cards; every prompt names the path AND carries the card content verbatim (C-3), so a gate never reads a file an agent did not write |
| `step` | 1-14 (lens-4 §D) |
| `decision_ids[]` / `finding_ids[{id, corrected_text}]` | the card quotes ONLY the decided value / the CORRECTED line; **JS throws if a cited finding has no `corrected_text`**; a REFUTED id (from `plan/preverified.json`) may not be cited |
| `files_allowed[]` / `new_modules[]` / `required_files[]` / `deps_allowed[]` | the builder's write set; any hunk outside it, any hunk under `plan/`, any requirement outside `deps_allowed` fails gate step 8. `required_files[]` names files the card must have delivered (its manifest); **`new_modules ∪ required_files` is what `--require` passes to the gate — validated at plan time against the design's `MANIFEST_MIN` (C-14)** |
| `tests_allowed[]` | test files the AUTHOR may create or modify; the builder may only ADD under `tests/unit/` |
| `xfail_allowed[]` | test ids (`file::name`) that may carry xfail/skip — the lens-4 §F known-bads only (`verifier mode:'plan'` refutes anything else); replaces every `Skip-Added:`/`Tests-Removed:` trailer (J1 CG9) |
| `expected_green_tests[]` | test ids that are green on the base tree BY DESIGN — characterisation pins and contract tests (C-13). Confirm-RED requires RED for everything else and GREEN for exactly these, on both the author's and the verifier's execution; the plan verifier refutes any id that is not a lens-4 §F pin or an old-tree contract test |
| `tests_removed_expected` | integer, default 0; the collected floor is `baseline − Σ tests_removed_expected` |
| `est_lines` / `est_minutes` | sizing for the rank order and the scope-expansion check (`changed ≤ 2 × est_lines`); **`est_lines` must fit the size class (S ≤ 120, M ≤ 300) or validation throws (C-13: card 01 is size M because the gate copy + fixtures + skeleton are ≈ 300 lines)** |
| `dod[]` | ≤ 8 lines `{id, command, expect, verification_level}`; every command runnable on CPU under `$VENV`; **no `-k/-x/--deselect/--ignore/--lf` or `|| true`** (JS + gate); `staging-required`/`owner-required` lines are `deferred`, never `pass` (F-37); JS raises the level when the text matches `STAGING_RE` |
| `depends_on[]` | acyclic (JS) |
| `size` | `S` (≤ 120 lines) or `M` (≤ 300); `L` throws at validation |
| `protected_touch` / `bootstrap` | `bootstrap` is false on every card (the profile exists only for the setup red-proof at `base_sha`; JS throws otherwise). **Protected paths are owned, not banned (C-21):** a write-set hit on a protected path is accepted only when the card's own manifest declares it (`MANIFEST_MIN[id]`) or the card carries `protected_touch` (platform-01-gate); anything else fails validation and the gate's scope step |
| `risk` | `none | security | persona | catalog`; `security` → reading list ≤ 6 files, verifier `xhigh`, and a DoD line about surfaces/operator flag (JS); `persona` → history-free clone, G-19 role names only, the FIXTURE COPY STEP; `catalog` → provenance fields mandatory |
| `apis_expected[]` | symbols the gate's apicheck imports from the pinned wheels; unresolved-without-torch symbols are recorded `unresolvable-needs-torch`, never RED (C-16) |
| `owner_precondition` | an `owner_approvals` field that must be non-null before the card may build (`fixture1_path` on 04, `persona_boundary_fixture_path` on 13b, `worker_checkpoint_decision` on 08c) — typed `blocked_on_owner` with the field, the why and the next action (C-22) |

### 4.2 How the 14 steps become 22 cards (the planner's default split; C0 approves) — CORRECTED finding ids inlined; v2 changes marked

| Card | Step | What it builds | deps | risk | Findings carried (CORRECTED text inlined in the card) | Owner precondition |
|---|---|---|---|---|---|---|
| `platform-01-gate` (**M in v2**, bootstrap red-proof at P0 only, protected) | 1 | import at `f88b120`, junk deletion, `.gitattributes`+`.editorconfig` then a `Renormalize-Only: yes` commit, `tests/protected.txt`, `ruff.toml`, `pytest.ini` (excludes `tests/live/`, defines `staging_required`, **deselects the `journey` marker from every default run, C-4**), `tools/gate.sh` (repo copy == pinned bytes), `tests/test_constants_pin.py` **+ the `config.py` skeleton with every §4.6 flag so the pins are green within this card's own gate run (C-13)**, `tests/test_import_contract.py`, `tools/stubs/{torch,transformers,spaces}` (import-only stubs for the worker import smoke), `tests/fixtures/gate/false-claim.patch` + `false-claim-target.txt` (the gate self-test's fixture targets, C-2), `tests/journeys/conftest.py` (the PATH-SCOPED `journey`-marker hook pinned byte-for-byte in §4.8, C-4/v2.1 V-2) **plus a DoD line that runs BOTH collections — `--journeys` over a one-file smoke journey under `tests/journeys/` AND the default suite, both green**, `tools/make_boundary_fixture.py` (C-21), persona-archive test made repo-local | — | — | security-tools-6 (`apply_patch` EOL/newline — tracked here, fixed in 09c) | — |
| `platform-02-pins` (M) | 2 | author writes the 10 pins of lens-4 §F (RED via `new_modules` ImportError); builder moves pure functions verbatim into `core/` (`--color-moved` shows moves only, `moves_only` in `diff_stats`) | 01 | — | tool_parse known-bads as `xfail_allowed`; §C items 2, 8 (DoD lines, §4.7) | — |
| `platform-03a-types-fake` (M) | 3 | `core/types` (GenerationRequest, SamplingParams, Message, Event), **`core/engine.py` (C-36: previously delivered by no card)**, `backends/base`, `backends/fake`, FakeEngine, conformance suite skeleton (rows `fake` / `recorded-hosted` skipped-needs-owner, `provenance`), `tools/record_fixture.py --i-accept-cost` | 02 | — | §C items 1, 3, 6, 7, 9 | — |
| `platform-03b-thin-slice` (M) | 3 | `api/app` with `/healthz` reading `build_info.json` (`git_sha`, fallback `git rev-parse`, else `unknown` which the canary rejects), `/v1/chat/completions` relay, `backends/hosted`, one `models.yaml` entry with provenance, placeholder chat via `gr.mount_gradio_app`, **placeholder `build_info.json` (`git_sha: "unknown"`, C-34)**; **its own gate command runs BOTH collections — the default suite and `--journeys` — so card 03b can be green before any journey exists (C-1/C-4)** | 03a | — | openai-api-1/2 (disconnect stops the generator; SSE framing) | — |
| `platform-04-streamparser` (M) | 4 | `core/parsing.StreamParser`, `core/events`, error taxonomy, `reasoning_content` in/out; pins flip; the recorded fixture becomes conformance case #1 | 03b | — | openai-api-3/5/9, chat-loop-ui-4; §C items 4, 5 | **`fixture1_path`** (C-M) |
| `platform-05a-registry` (S) | 5 | tool registry = THE `python_eval` gate; **G-15 (5) verbatim**: operator secret flag only, checkbox/API/MCP cannot enable, absent from `/v1` and MCP toolsets; `tests/test_python_eval_surfaces.py` (protected) | 04 | security | security-tools-8, chat-loop-ui-2; §C item 10 | — |
| `platform-05b-agent-session` (M) | 5 | `core/agent.run_turn` (rounds cap, one rejection round, pairing, prompt-token budget before any backend call, titled notices), `SessionStore` (TTL sweep, explicit keys, per-call bench for API/MCP, never `rmtree` in unload) | 05a | — | chat-loop-ui-1/3/6, gpu-lease-4, security-tools-8 | — |
| `product-06-ui` (M) | 6 | `build_ui(FakeEngine)`: selector (visible catalog entries only), presets, personas dropdown, render, history replay as JSON in the FINAL yield, explicit Continue, grouped settings; `presence_penalty` control per the Q2 decision | 05b | — | chat-loop-ui-1/8/9, critic-2 (`_user_text` both shapes) | — |
| `platform-07-gateway` (M) | 7 | API key opt-in, size/role/range validation before any backend call, threadpool + disconnect watcher, non-blocking semaphore → 429, ledger, `/v1/preflight`, `/status`; `x-ip-token` bound inside the generator body | 03b | — | openai-api-1/2/7/8, gpu-lease-6 | — |
| `platform-08a-worker-pure` (M) | 8 | `worker/encode.py` (encode ladder catching ValueError; `continue_final_message` only for a finished non-thinking user Continue), `worker/lease.py` (estimator rows at measured-or-UNVERIFIED rate, `max_time` = worker entry − measured cold-start margin, **token-level continuation**: control record + `prefix_ids`, stop event → StoppingCriteria, heartbeat, stats record), boot probe line printing `find_spec('fla')`/`('causal_conv1d')`, **`worker/penalty.py` ONLY when `args.torch_in_venv` (C-14)** | 03a | — | gpu-lease-1/3/5/7/8, inference-perf-4/-6, critic-1, critic-4 | — |
| `platform-08b-worker-backend` (M) | 8 | `worker/app.py` (import-time load with **`AutoModelForImageTextToText`**, no `trust_remote_code`, no `prefill_chunk_size`, `@spaces.GPU(size=…)` from the catalog), `backends/worker` (`gradio_client` with the token from env: `WORKER_TOKEN` or `HF_TOKEN`), fallback order OFF, cancel plumbing | 08a, 04 | — | inference-perf-2/-5/-7, gpu-lease-3 (control dict intercepted for BOTH consumers) | — |
| `platform-08c-worker-checkpoint` (S) | 8 | `models.yaml` local entry for the decided candidate (`has_visual_tensors: true` required by the gate), `tools/export_checkpoint.py` (VLM class; runs off-Space as an HF Job; unit-tested against a fake), runbook rows for the bf16-mount fallback until one boot is observed; DoD `staging-required` | 08b, 13a | catalog | inference-perf-2 CORRECTED | **`worker_checkpoint_decision`** |
| `platform-08d-kernels` (S) | 8 | `flash-linear-attention` in the worker requirements behind a flag; Triton JIT budgeted as `overhead` in the estimator's first lease; DoD lines `staging-required` (measured on the staging worker only; never on production) | 08b | — | inference-perf-4 CORRECTED | — |
| `platform-09a-pyeval-env` (S) | 9 | env allowlist, `prctl(PR_SET_DUMPABLE,0)` at startup, canary-secret red-proofs (never prints an environment) | 05a | security | security-tools-1 | — |
| `platform-09b-pyeval-runner` (S) | 9 | `-I runner.py` with `setrlimit` inside the child, `start_new_session`, `killpg`, fresh cwd, output cap; **no `preexec_fn`** (blocking idiom) | 09a | security | security-tools-1 CORRECTED | — |
| `platform-09c-net-guards` (M) | 9 | SSRF opener (resolve once, dial the literal IP, redirect validated before the hop, ports), `regex` timeout, calculator allowlist, archive caps, `apply_patch` ambiguity/offset/EOL/newline, network-origin neutraliser + narrow taint rule | 05a | security | security-tools-3/4/5/6/7/9 | — |
| `product-10-vision` (M) | 10 | OpenAI content parts end-to-end on the fake backend; caps; `vision:false → 400` with zero backend calls; video OFF (flag), images ON | 04, 06 | — | critic-2, chat-loop-ui-9 | — |
| `platform-11-mcp` (S) | 11 | `ask/poll/status/preflight` via `gr.api`; `chat` hidden; listing snapshot = 4 typed tools; exists only if G-18 keeps MCP (§15 Q3) | 05b, 07 | — | chat-loop-ui-7, security-tools-2 | — |
| `platform-12-harness` (M) | 12 | 12-prompt harness, `--backend fake --dry-run` default, zero-call test, `--i-accept-cost` + owner env var, `max_retries=0`, cost ledger, admission schema, evidence JSON per entry | 03b | — | gpu-lease-4 (cost) | — |
| `product-13a-catalog` (S) | 13 | `models.yaml` fill from `evidence/catalog/*.json` (`revision` 40-hex, `provenance{source_url, fetched_at, saved_path}`, `admission: pending|passed|failed`, `has_visual_tensors` on local entries), `core/catalog.py` (`visible()` hides pending — M-3-clar), `tests/test_catalog_policy.py` (protected), `tools/render_readme.py --check`, **`evidence/catalog/README.md` — the R0 catalog raw reads copied into the repo so the gate and CI can read them (C-34)** | 12, 03b | catalog | — | — |
| `product-13b-personas-readme` (M) | 13 | G-19 set (8 roles, role/output contract/tool guidance/quota-aware behaviour), wiring, absence test against the shingle-hash fixture (protected), README rendered from catalog + registry + collected count; **the FIXTURE COPY STEP copies `owner_approvals.persona_boundary_fixture_path` to `tests/fixtures/persona_boundary.json` and its sha256 must equal `persona_boundary_fixture_sha256` (C-21)** | 06, 13a | persona | — | **`persona_boundary_fixture_path`** (C-Q) |
| `platform-14-promotion-ci` (M) | 14 | **`.github/workflows/{gate,deploy-staging,promote,health}.yml`** (OIDC, `permissions:` blocks, SHA-pinned actions, `production` environment; the four filenames the required-files check asserts, C-14/C-34), **CI writes `build_info.json` at deploy**, **`tools/expected.py` — the `EXPECTED.json` contract CI writes from (C-35)**, `tools/promote.py` (sha check incl. `unknown` → fail, `hf spaces wait`, canary pass^3 with last-known-good control, visibility tripwire `private`, log tail on failure, rollback = redeploy known-good), scheduled health job; unit-tested against fakes; never executed | 07, 08b, 12 | — | S/AP-12 canary contract (A1) | — |

22 cards. Critical path: 01 → 02 → 03a → 03b → 04 → 05a → 05b → 06 → 10 (9 deep) with 13b after 06 and 08c after 08b/13a; the owner stop at 04 splits R1 into at least two invocations by design (C-M).

### 4.3 DAG, waves, sizing — all plain JS (§13); recomputed at runtime (C-5)

- `topoOrder(cards)` — dependencies first, ties by id; throws on a cycle or an unknown dependency (F-14, F-47).
- `rankCards(cards)` — A2's longest-path rank in estimated minutes (`est_minutes` or S=20/M=35, +14 per node); `waves()` orders each ready set by `(−rank, id)` (T-8) **and the same key orders integration, C-24** inside **barrier waves** (replay-safe control flow); a wave holds up to `args.wave_size ≤ args.cap` ready cards with pairwise-disjoint write sets; a clash waits (logged); **`readyWave()` is recomputed from the LIVE status map before every wave (C-5): a card whose dependency is parked, blocked on the owner or not yet merged is never scheduled — its dependents can never be built ahead of a failed root.** After the loop, `markDependencyBlocked()` types every still-unstatused card `not_attempted: dependency-blocked:<dep>(<state>)` with the next action (C-22). `waves()` never throws.
- Sizing: `S ≤ 120`, `M ≤ 300` lines, **validated against `est_lines` at plan time (C-13)**; `changed_lines ≤ 2 × est_lines` is a `taskDone()` condition (A2 G8) computed from the gate's `LEDGER_DIFF_STATS` and **fail-closed when the stats are missing (C-25)**; a builder `partial` is not `built` (condition 12) and is re-driven as a fix round.

### 4.4 Worktree → branch → bundle lifecycle (every path absolute; every git command `git -C`)

```
setup     : git -C $R merge --no-ff <plan_sha> into integration/<n> (first commit; plan/** only; once)
author    : git -C $R worktree add $WT/tests-<id>-<n> -b tests/<id>-<n> <integration_head>
            write tests; commit "tests(<id>): …" (trailer Card: <id>); gate.sh --only-tests <paths> --card … --base <head> → expect RED
            git -C $R worktree remove $WT/tests-<id>-<n>            (branch survives in the store)
  persona : git clone --depth 1 --single-branch --branch integration/<n> file://$R $WT/tests-<id>-<n>   (history-free)
            FIXTURE COPY STEP: cp $OA.persona_boundary_fixture_path tests/fixtures/persona_boundary.json (sha256 must equal the pinned value, C-21)
            … commit …; git -C $R fetch $WT/tests-<id>-<n> HEAD:refs/heads/tests/<id>-<n>              (local fetch, never a push)
verifier  : git -C $R worktree add --detach $WT/red-<id>-<n> <tests_head> ; gate.sh --only-tests … ; remove
builder   : git -C $R worktree add $WT/task-<id>-<n> -b task/<id>-<n> tests/<id>-<n>
            implement in commits (Claims: block + Card: trailer); gate.sh --card … --oracle <tests_head> LAST, on the committed clean tree (advisory; returns its LEDGER_DIGEST + steps, C-18); remove
verifier  : git -C $R worktree add --detach $WT/verify-<id>-<n>-<k> <task_head>
            gate.sh --card … --oracle <tests_head> (must reproduce the builder's LEDGER_DIGEST) ; --mutants … --tests … ; --revert-proof <tests_head> --tests <author's + builder-added tests/unit> ; remove
fixer     : git -C $R worktree add $WT/task-<id>-<n>-fix<k> task/<id>-<n>
integrator: in $R on integration/<n>: git merge --no-ff task/<id>-<n>   (record merge_sha for every merge, C-12)
            conflict → git merge --abort → return hunks → integrator mode:'conflict' in $WT/conflict-<id>-<n>
              (created DETACHED — `git worktree add --detach … <head>` — because integration/<n> is checked out in $R, C-30)
            clean  → gate.sh --base <prev_head> --journeys --require … --xfail-allow … ; git cherry == "" ; patch-ids present ;
                     write plan/status/<id>.json {merged, head_sha, merge_sha, gate_digest} + commit ; git bundle create <bundles>/<id>.bundle <prev>..integration/<n> (incremental)
journeys  : author on task/journeys-<tag>-<n> (same helper as every merged branch) → integrator mode:'merge' (gate carries --journeys, C-4)
fixcards  : integrator mode:'fixcards' writes plan/fixes/<fixid>.json verbatim + one commit "plan(fixes): review round <r>" (C-3)
clean-gate: git -C $R worktree add --detach $WT/clean-w<k>-<n> <head> ; BROKEN_SHA=<base> gate.sh --clean --self-test --journeys --lint-base <last clean pass> --require … ; remove
revert    : integrator mode:'revert' on integration/<n>: git revert -m 1 <merge_sha> (+ remove plan/status/<id>.json) ; gate ; return head + digest (checked in JS, C-12)
```

- Branch names carry the run nonce (F-33); a re-drive of the same card in the same run reuses the branch (`status:'reused'` when already green — T-16); every re-drive carries `redrive: <k>` in its prompts (cache miss by construction, J1 D4).
- A worktree is removed by the agent that created it, and only after `git rev-parse <branch>` equals the head it reports; the gate pre-step prunes `index.lock` older than 10 min and kills only listeners whose cwd is the current tree (J1 CG2).
- Bundles are incremental (`<prev>..integration/<n>`, A2 §13) under `/workspaces/space-build-bundles/<nonce>/` (C-17); `bundle_bytes` is reported; > 20 MB is logged with the runbook advice "push from the checkout"; the manifest lands in the grill tree.

### 4.5 Integration order, conflict resolution, integration test

- **Order:** strictly serial, `(−rank, id)` order inside the wave (C-24), one `integrator` call per merge (single writer). A card whose head is already an ancestor returns `already-merged` **with evidence (C-20): the integration head is unchanged, a gate run at that head exited 0 with its digest and the pinned gate sha, and the cherry/patch-id assertions came back empty — anything less is typed `already-merged-unproven` and blocks the card; the head never moves on an `already-merged`.**
- **Conflict:** the integrator never resolves; a fresh `mode:'conflict'` call gets ONLY the hunks and both cards, resolves in its own **detached** worktree (C-30), runs the gate, returns the merge sha; `mode:'ff'` fast-forwards and re-gates. A second conflict → `blocked:integration:conflict`.
- **Lost-hunk check:** `git cherry` empty AND every patch-id present — asserted in JS (`mergeOk`), together with `gate_exit_code === 0`, a 64-hex `gate_digest`, `gate_sha256_observed === args.gate_sha256` and a real `merge_sha` (C-12/C-20).
- **Red after merge (F-34):** the integrator reverts **the recorded `merge_sha`** immediately (`status: reverted`, JS-verified result) → `parked: integration:gate-red-after-merge(reverted)`; a fix card for it comes from the review loop. **"merged + red" is a revert-now case checked against the same merge sha — the target is never "HEAD", which after a journeys merge is the wrong commit (C-12).** A revert that fails for any reason marks the integration branch dirty: no further merges, checkpoint `failed`.
- **Integration test:** `integrator mode:'clean-gate'` after every wave **that merged or merged journeys (C-38: a wave with nothing merged and a last clean gate passing at this exact head is skipped, logged)**: detached pristine checkout of the wave head, `gate.sh --clean --self-test --journeys --lint-base <last clean pass> --require <manifest> --xfail-allow <union>`; **the idiom lint inside it only sees `--lint-base..HEAD` (C-15), so earlier waves' idioms are not re-counted and waiver counts stay per-card.** The clean gate is typed in JS three ways: **`pass`** (exit 0, head matches, digest 64-hex, pinned gate, `self_test.broken_red === true`, `self_test.false_claim_red === 'true'`), **`fail`** (a real RED → `mode:'revert'` of the last merged card **by its merge sha**, whose result is checked: on anything but `merged + exit 0 + digest`, the integration branch is marked dirty, no further merges happen and the checkpoint is `failed` — J2 gap 12), or **`gate-unavailable`** (a dropped agent, a malformed shape, a wrong head, or **exit 0 contradicted by a non-red self-test — any of these is `unavailable`, never a revert, C-11**; `satisfied()` stays false). A journey still `skipped` although its `needs=` card is merged becomes a synthetic blocking finding for the review loop. The clean gate also returns `remotes[]`, the branch count and the toolchain status hash (a mismatch → `HALT`, docs/grills excluded, C-17).

### 4.6 Ship-but-flag (lens-4 §E; A2 §4e) — every flag is a `config.py` constant with a row in `tests/test_constants_pin.py`

| Flag | Default at launch | Pin row (protected test) | Card that owns the constant |
|---|---|---|---|
| automatic hosted→worker fallback | OFF | `FALLBACK_TO_WORKER is False` | 08b |
| server-side tools for `/v1`/MCP | OFF | `SERVER_TOOLS_API is False` | 07 |
| `http_request` POST + third-party reader | OFF | `HTTP_POST_ENABLED is False`, `READER_MODE is False` | 09c |
| video (images ON) | OFF | `VIDEO_ENABLED is False`, `IMAGES_ENABLED is True` | 10 |
| automatic lease chaining (explicit Continue ON) | OFF | `AUTO_CHAIN is False`, `EXPLICIT_CONTINUE is True` | 08a |
| cross-turn `preserve_thinking` | OFF | `PRESERVE_THINKING is False` | 05b |
| `python_eval` | operator secret flag only | `PYTHON_EVAL_ENV_FLAG == 'QWEN_PYEVAL_OPERATOR'` and the surfaces test | 05a |
| `xlarge` | operator config only, never a request field | `GPU_SIZE_FROM_REQUEST is False` | 08b |

Every card's `out_of_scope[]` lists these defaults unless it is the card that owns the constant (A3's enforcement, kept). **Card 01 ships the `config.py` skeleton containing all eight constants (C-13):** the pins test is green inside card 01's own gate run via `expected_green_tests`, and every later card edits its own flag with the pin already in place.

### 4.7 lens-4 §C duplication items → DoD lines (J3 gap 4)

| §C item | Collapses into | Card | DoD line (mechanical) |
|---|---|---|---|
| 1 message assembly ×2, persona keys ×2, `red_team` fallback ×3 | `core/prompting.build_messages` | 03a | `test -z "$(git grep -ln 'def build_messages\|def _as_messages\|def normalize_messages' -- '*.py' \| grep -v core/prompting.py)"` |
| 2 content flattening ×3 | `core/prompting.text_of` | 02 | `test "$(git grep -c 'def _flatten_content\|def _user_text\|def text_of' -- '*.py' \| awk -F: '{s+=$2} END {print s}')" = 1` |
| 3 image placeholders ×2 | worker encoder | 03a | `git grep -n '_content_for_template' -- '*.py' \| grep -v worker/encode.py \| wc -l` = 0 |
| 4 parse/validate policy ×3 (is chat-loop-ui-4) | one `StreamParser` | 04 | `git grep -ln '<tool_call>' -- '*.py' \| grep -v core/parsing.py \| grep -v tests/` = empty |
| 5 thinking split ×4 | same parser; `/v1` gains `reasoning_content` | 04 | `git grep -c '</think>' -- '*.py' \| grep -v core/parsing.py` = empty (tests excluded) |
| 6 usage block ×2 | `Finish.usage` | 03a | `git grep -n 'prompt_tokens' -- '*.py' \| grep -v core/types.py \| grep -v api/protocol.py \| grep -v tests/` = empty |
| 7 error-to-content ×3 | `BackendError → Finish(reason)`; UI titled notice; API status | 03a | `git grep -n 'GPU lease ended' -- '*.py'` = empty |
| 8 sampling kwargs in 5 places | `SamplingParams` | 02 | `git grep -n 'repetition_penalty' -- '*.py' \| grep -v core/types.py \| grep -v tests/ \| grep -v worker/` = empty |
| 9 stop normalisation ×3 | one validator | 03a | `git grep -c 'def _normalize_stop\|def normalize_stop' -- '*.py'` sums to 1 |
| 10 tool dispatch ×4, `python_eval` gate ×2 | registry (the single choke point for G-15 (5)) | 05a | `git grep -n 'python_eval' -- '*.py' \| grep -v core/tools/registry.py \| grep -v tests/` = empty |

`verifier mode:'plan'` refutes a plan in which any §C item lacks a DoD line (prompt rule (g)).

### 4.8 Journeys = held-out seams H1-H7 + J1 (A1 §4.6; A2 gate step 13) — a separate collection (C-4)

| Seam | What the journey exercises | `needs=` card |
|---|---|---|
| J1 | `QWEN_STUB=1` boot serves UI + `/healthz{git_sha}` (from `build_info.json`) in < 10 s on a free port | 03b |
| H7 | error taxonomy: quota / illegal-duration / abort → titled notice in the UI, `{"error":…}` event on `/v1`, partial text kept | 04 |
| H4 | `python_eval` × operator flag × every surface: the UI checkbox alone cannot enable it; unreachable over `/v1` and MCP | 05a |
| H6 | session isolation × TTL sweep × no `rmtree` on unload; two sessions → two benches | 05b |
| H2 | `/v1` × identity: `x-ip-token` bound inside the generator body; 429 on the non-blocking semaphore; stream stops on disconnect | 07 |
| H1 | tool loop × streaming × Continue at **token level**: turn 2 contains turn 1's tool results; `finish_reason: length` → Continue resumes from `prefix_ids` (fake worker) | 08a |
| H3 | MCP `ask → poll → status → preflight` with `chat` hidden; listing = 4 typed tools | 11 |
| H5 | catalog admission × `models.yaml` schema × harness zero-call × pending entries hidden | 13a |

**The mechanics changed in v2 (C-4); v2.1 pins the bytes (V-2).** Card 01 delivers `tests/journeys/conftest.py` EXACTLY as follows — self-contained (it imports its own `pytest`: a conftest naming `pytest` without importing it is ruff F821 and NameErrors at collection, which the dry run proved on pytest 9.1.1) and path-scoped, because a bare `pytestmark = pytest.mark.journey` in a conftest is inert (pytest reads `pytestmark` only from test modules, so `--journeys` collects 0) and an unscoped hook marks every item in the session (so `-m "not journey"` deselects the whole default suite); both naive implementations are RED, and card 01's both-collections DoD catches them at card 01, never at the first seam wave:

```python
import pathlib
import pytest

def pytest_collection_modifyitems(config, items):
    for it in items:
        if it.path.is_relative_to(pathlib.Path(__file__).parent):
            it.add_marker(pytest.mark.journey)
```

`pytest.ini` (also card 01) registers the marker (`journey: held-out seam journey (selected only by gate.sh --journeys)` under `markers`) and deselects it from every default run. The default suite therefore NEVER collects a journey: a missing journey cannot be a RED baseline skip, and `needs=` is the only legal skip reason (`pytest.mark.skip(reason="needs=<card-id>")`). `--journeys` runs the collection at **every merge gate and every clean gate** (not only post-wave); the gate counts `skipped_needs[]` by parsing the reasons and reports `skipped_other = max(0, skipped − needs-matches)` — any skip without a `needs=` reason is RED. JS turns a journey whose card IS merged but still skipped into a synthetic blocking finding (§6). The journeys author runs only for a wave in which one of these cards merged (≈ 6-8 times per R1, not per wave). Card 03b's own gate command runs both collections so the thin slice is provably green in both before any journey exists (C-1).

---

## 5. Inner loop per task (exact counters and exit conditions)

```
author → confirm-RED (two-execution digest equality; expected_green_tests exempt both ways, C-13/C-29)
       → builder (gate LAST on the committed clean tree, C-18) → fresh verifier (gate digest must match; DoD re-runs;
       mutants; revert-proof incl. builder-added tests/unit, C-28; apicheck-extended, C-18; diff_stats required, C-25)
       → [fixer ← typed failures (digest-mismatch carries both ledgers' steps, C-18) → verifier]≤2 → taskDone() (JS)
```

| Counter | Value | Exhaustion → typed result |
|---|---|---|
| `MAX_AUTHOR` | 2 author calls (second re-driven WITH the red verdict, C-26) | `blocked:'tests-not-red'` |
| `MAX_BUILD` | 3 builder calls = 1 `implement` + ≤ 2 `fix` | `blocked:'fix-exhausted'` |
| two-strikes | failure fingerprint after a fix equals the previous one — **the fingerprint is never empty (C-18), so a vacuous verifier cannot disable two-strikes** | `blocked:'no-progress'` |
| oscillation | fingerprint sequence A→B→A | `blocked:'oscillation'` |
| `MAX_NULL_RETRY` | 1 per call slot (`attempt: 2` + `NARROW`) | `blocked:'agent-null:<role>'` |
| starvation | budget guard, agent slice or HALT cut the chain short — **typed `starved` → `not_attempted` (retryable on resume, C-8), never parked** | `not_attempted:'starved:<why>'` |
| secret in a return | any secret-shaped string in `failures[]`, `output_tail`, `notes`, `red_excerpt`, excerpts (redacted in JS before anything reads it) | `blocked:'secret-shaped-output'` (never fixer-fed) |
| budget / halt | `budget.remaining() ≤ RESERVE`, agent slice, `HALT` (outward action, toolchain mutated, remote added, budget throw) — **the synthesizer is exempt (C-7)** | `{status:'null', reason:'budget'|'halt'}` → `not_attempted` |

1. **author** (`mode:'tests'`) → `{tests_head, test_paths[], red_excerpt, gate_digest, mutants_suggested[]}`; exit: `commits_made ≥ 1` (or `reused`) and a 40-hex `tests_head`. Persona cards run the FIXTURE COPY STEP (C-21) and commit the fixture with the tests.
2. **confirm-RED** (`verifier mode:'red'`): `gate.sh --only-tests <paths> --card … --base <head>` at `tests_head`: the **author-range tamper rules** (no pre-existing test M/D outside `tests_allowed`; no assertion-count drop in a modified pre-existing test; no skip/xfail marker outside `xfail_allowed`) and RED for the expected reason (rc 1 or 2, collected > 0, passed == 0 **except exactly the card's `expected_green_tests`, which must be green — an extra green new test is RED and a listed-but-not-green one is RED, on BOTH executions (C-13)**; rc 5 and rc 0 are not red). `pass` requires `red.sha === tests_head` **and `red.gate_digest === author.gate_digest` — confirm-RED is a two-execution equality too (C-29)**.
3. **builder** (`mode:'implement'`): implements, commits per step with a `Claims:` block, runs every DoD command, **then runs the gate LAST, at the final commit, on a clean tree (C-18)** and returns `gate_digest` + `gate_profile` + `gate_steps[]` (the mismatch diagnosis) + `dod[]` (one row per card DoD id) + `apis_used[]` (each with a `ledger_ref`).
4. **verifier** (`mode:'verify'`): runs the same gate command itself in a detached worktree (`gate_digest`, `gate_sha256_observed`, `idiom_hits`, **`diff_stats` — required, its absence fails the card (C-25)**, `apicheck_unresolvable[]`), re-runs every DoD command (`dod_reruns[]`), reads the diff (`hunks_cited`), writes and runs 3 mutants (`--mutants … --tests …`), runs `--revert-proof <tests_head> --tests <author's tests + builder-added tests/unit/*>` (C-28), **and separately runs the apicheck with the builder's `apis_used[]` appended, recorded as `checks[]: apicheck-extended` — a run with its own ledger that never perturbs the digest equality (C-18)** — clearing idiom warnings by idiom.
5. **`taskDone()`** = `okSemantics(c, t, b, v)` — twelve booleans, logged per card, all required:
   1. `v.verdict === 'pass' ∧ v.gate_exit_code === 0`
   2. `v.ledger_head_sha === b.head_sha ∧ v.sha === b.head_sha` (40-hex)
   3. **`v.gate_digest === b.gate_digest`** (64-hex) — two independent executions agree (A1 G1; F-12)
   4. `v.gate_sha256_observed === args.gate_sha256` and profile `full` on both sides — the bootstrap profile is never a card profile (CG1; A2 G9)
   5. `hunks_cited ≥ 1 ∧ checks[] contains a gate.sh run` (A2 `semantic()`)
   6. `mutants.written ≥ 1 ∧ killed === written` (F-20)
   7. `revert_proof.observed === 'red'` (negative control)
   8. `b.dod.length === c.dod.length` and every local-level DoD id exits 0 in **both** `b.dod` and `v.dod_reruns` (A1 ok[6]; `expected_green_tests` are covered by condition 1's rule set, not by a per-id exemption here)
   9. `warnings_cleared.length ≥ idiom_hits` (F-10 in code)
   10. `diff_stats` present **(fail-closed without it, C-25)** `∧ insertions + deletions ≤ 2 × est_lines` (scope expansion)
   11. neither return had a secret-shaped string redacted (CG3)
   12. `commits_made ≥ 1 ∧ status ≠ 'partial'` ∧ every `apis_used[]` carries a `ledger_ref` (F-8)
   DoD lines at `staging-required`/`owner-required` are `deferred`, never done (F-37).
6. **fixer** (`builder mode:'fix'`) receives ONLY typed failures (`failures[]`, failed checks, failed DoD re-runs, mutants, revert-proof, the verifier's strongest disagreement, all capped and redacted) and the card. **A digest mismatch (condition 3) additionally carries `digest_mismatch`: both ledgers' step lists, the steps only in the builder's, the steps only in the verifier's, and the hint "re-run the gate LAST on the committed tree" (C-18).**

Fingerprint = sorted failing test ids + first error lines with shas, digits and paths normalised **+ the failed condition ids + the digest-mismatch step diff (C-18)**, computed in JS; it can never be the empty string, so two-strikes always has teeth.

---

## 6. Outer loop per wave and for the whole tree

### 6.1 Per wave (mechanical; no LLM review per wave)

```
readyWave() recomputed from the live status map (C-5) →  pipeline(wave, buildTask)
  →  serial integrate in (−rank, id) order (merge → gate on the merged tree with --journeys (C-4) → cherry/patch-id
     → status commit (with merge_sha, C-12) → incremental bundle)
  →  [journeys author when a seam card merged → integrate]
  →  integrator mode:'clean-gate' (--clean --self-test --journeys) typed pass|fail|gate-unavailable (C-11)
     — skipped when nothing merged and the last clean gate passed at this head (C-38)
fail → checked revert of the last merged card BY ITS MERGE SHA (revert failure ⇒ integration dirty ⇒ no further merges);
gate-unavailable → no revert, not satisfied
```

### 6.2 Whole tree (after the last wave; also the body of R2/R3 on their evidence)

```
round = 0; dry = 0; seen = Set(prior seen_keys); probesUsed = Set()
gate the loop itself before spending a lens (C-5, C-10, C-33):
  smoke mode                        → skip the review loop entirely ('smoke-skip-review')
  tree incomplete (C-5)             → stop 'tree-incomplete' — any card not merged and not a parked LEAF,
                                      incl. every dependent of a parked card; no lens is ever spent on such a tree
  last clean gate ≠ pass at head    → run ONE clean gate first; fail/unavailable → stop, no lenses (C-10)
while (true):
  stop if satisfied() ∧ vetoes==0 ∧ round>0        → 'satisfied'
  stop if HALT                                      → 'halt:<why>'
  stop if round ≥ MAX_ROUNDS (3)                    → 'max-rounds'
  stop if dry ≥ 2                                   → 'dry'
  stop if budget/agent slice cannot fund the round  → 'budget-or-agent-cap'
  round++
  findings  = parallel(3 lenses) + synthetic findings (journeys skipped after merge; staging evidence)   // barrier: dedup needs all
  levels raised in JS (STAGING_RE); fresh = dedup(findings, seen); probesUsed ∪= lenses' probes_used
  confirmed = pipeline(fresh, verifier mode:'refute') → holds ONLY with a reproduction that exits non-zero on the
              defect (a "holds" without one is ignored and logged, C-27)
  staging/owner-level confirmed findings → blocked_on_owner rows (never a fix card) — EXCEPT ids the owner listed in
              owner_approvals.accepted_findings at medium/low severity, which are recorded deferred (C-6 policy, §15 Q10);
              a confirmed critical/high one at stage/promote → stop 'blocked-on-owner:staging-evidence' (C-6)
  local confirmed findings + vetoes → fix cards → integrator mode:'fixcards' commits plan/fixes/ (C-3)
              → buildAndIntegrate (waves, clean gates); fixcards unavailable → not_attempted, never silent
  vetoes    = satisfied() ? verifier mode:'veto' (xhigh; last-round mandate = DoD inversion with probesUsed) : []
              a dropped veto judge → stop 'veto-unavailable' (fail closed)
  dry = (fresh.length==0 ∧ vetoes.length==0) ? dry+1 : 0
```

`satisfied()` (JS): `¬HALT ∧ ¬INTEG_DIRTY ∧ lastClean.verdict==='pass' ∧ lastClean.head_sha===head ∧ openBlocking===0 ∧ unreviewed===0 ∧ tree-complete ∧ ownerCritical===0` (C-5/C-6). **R2/R3 (J2 A3-4):** `lastClean` is seeded from `args.last_clean_gate` **only when its `head_sha` equals the live integration head AND its digest is 64-hex — otherwise it is `gate-unavailable: no prior pass at this head` and the pre-check re-runs one clean gate (C-10)**; findings that need a code fix run through the same loop and refresh `lastClean` via the fix wave's clean gate; `promote-production` is emitted only from `status:'ready'`, and `ready` is false while any row is `blocked_on_owner`, `not_attempted`, or a confirmed critical/high owner finding stands (C-6).

Budget reserve: `RESERVE = args.reserve_tokens ?? 120000`; a budget-ceiling throw from `agent()` sets `HALT='budget-exhausted'` and every later `budgetOk()` is false without further calls (J2 gap 8); **the synthesizer is exempt from the HALT branch and from the reserve guard — the reserve is what pays for it, so it always runs (C-7/F-45).**

---

## 7. Deterministic gates

One script, `gate.sh`, written at P0 to `/workspaces/space-build-tools/gate.sh` and **pinned by `args.gate_sha256`**: the script verifies its own bytes on every run and exits 66 otherwise, so neither the external copy nor the in-repo copy (`tools/gate.sh`, also pinned by `tools/gate.pin` and compared byte-for-byte in the integrity step) can be edited by an agent without every subsequent run going RED (J1 CG1). It is the ONLY admissible evidence of verification: it writes `.gate/last_run.json` and `.gate/last_run.digest` (sha256 over the timestamp-free canonical part: shas, mode, profile, python, step names + exit codes, pytest counts + a hash of the sorted outcomes, idiom hits, mutants, revert-proof, journeys, self-test), prints `LEDGER_SHA256` and `LEDGER_DIGEST`; **two independent executions at the same sha with the same arguments produce the same `LEDGER_DIGEST`** (verified in the dry run; `LEDGER_SHA256` still differs because it covers the timestamps) and the script accepts a card only when the builder's and the verifier's digests are equal (C-29: also required for confirm-RED). Only exit 0 is green; pytest exit 5 is red; a missing tool, a missing required file, a missing/tampered baseline are red (fail closed), never "skipped". V2 additions to the same script: `--lint-base` scopes the idiom lint to `--lint-base..HEAD` (C-15); `--boundary-sha256` pins the persona fixture (C-21); `--journeys` is the only selector of the journeys collection and counts `needs=` skips (C-4); apicheck resolves a symbol it cannot import by ast-parsing the pinned wheel SOURCE under `--libsrc`, recording `unresolvable` when even that fails — never RED (C-16); `--card` mode prints `LEDGER_DIFF_STATS` for the scope check (C-25), excluding `tools/gate.sh` and `tests/fixtures/` (C-13); and the self-test's false-claim fixture is generated by the gate itself, so the red-proof exists before card 01 delivers anything (C-2).

### 7.1 Where it runs

| Invocation | By whom | On what | Purpose |
|---|---|---|---|
| `gate.sh --only-tests <paths> --card <card> --base <head>` | author (its own RED proof), then verifier `mode:'red'` | detached checkout of `tests_head` | author-range tamper rules + confirm-RED (rc 1/2, collected > 0, passed == 0 **except exactly the card's `expected_green_tests`, both executions, C-13**; failure classes recorded); **pass additionally requires the verifier's `gate_digest` to equal the author's (two executions, C-29)** |
| `gate.sh --card <card> --base <tests_head> --oracle <tests_head> [--libsrc <dir>] --require … --xfail-allow …` | builder (advisory; run LAST on the committed clean tree, C-18), then verifier `mode:'verify'` (authoritative; digest must match) | task worktree / detached checkout of the task head | full gate on the branch: oracle lock + reset, scope/protected (ownership rule, C-21)/plan/tamper/deps, claims + per-`Card:` waivers, apicheck (import-first, else wheel SOURCE; `unresolvable` recorded, C-16) + known-bad, two-tier idioms scoped `--lint-base..HEAD` (C-15), suite ×2 vs the pinned baseline, `LEDGER_DIFF_STATS` (C-25) |
| `gate.sh --card <card> … --oracle <tests_head>` **with the builder's `apis_used[]` appended** | verifier `mode:'verify'` (separate run) | the verify checkout | **`apicheck-extended`: its own `checks[]` entry with its own ledger — it never perturbs the digest equality (C-18)**; unresolved symbols are recorded `unresolvable-needs-torch` (C-16) |
| `gate.sh --mutants <file> --tests <p1,p2> --out .gate/mutants-<id>.json` | verifier `mode:'verify'` | the verify checkout | sufficiency: ≥ 1 written, all applied, all killed, tree unchanged |
| `gate.sh --revert-proof <tests_head> --tests <p1,p2 …>` | verifier `mode:'verify'` | temp worktree at the oracle | negative control: the final DoD tests are RED without this card's implementation — **the test set includes the builder-added `tests/unit/*` (C-28)** |
| `gate.sh --base <prev_head> --require … --xfail-allow … --journeys --tests-removed N` | integrator `mode:'merge'`/`'ff'`/`'revert'` | main checkout on `integration/<n>` | green on the merged tree, else revert (F-34) — **`--journeys` at every merge gate so a `needs=` skip is always counted where its card just merged (C-4)** |
| `BROKEN_SHA=<base> gate.sh --clean --self-test --journeys --lint-base <last clean pass> --boundary-sha256 <hex> --base <base> --require … --xfail-allow …` | integrator `mode:'clean-gate'` per wave (skipped per C-38); setup (`--self-test --profile bootstrap`) | detached pristine checkout | full suite ×2, conformance, journeys with `needs=` skips counted, README check, gate integrity, boundary sha (non-blocking until card 13b is in the tree, C-21), idioms only over `--lint-base..HEAD` (C-15), **red-proofs on every clean gate** (RED on `f88b120`; RED on the false-claim fixture *from the claim-lint step itself*, verified from the inner ledger — C-2); JS types the result `pass | fail | gate-unavailable` (C-11) |
| `tools/gate.sh` in CI (card 14) | CI on every PR, fresh clone, 3.12 | runner | the same pinned bytes |

### 7.2 `gate.sh` (exact contents — `bash -n` clean; all embedded Python compiles: 13 heredocs + 3 one-liners, checked mechanically; control path dry-run in a throwaway repo, 22/22 checks green)

```bash
#!/usr/bin/env bash
# gate.sh — the only admissible evidence of verification for the Space rebuild (design-v2 §7).
# Runs ONLY under the pinned 3.12 venv. Fails closed: a missing tool, a wrong interpreter, a missing
# required file, an unpinned or tampered copy of this script, a missing/tampered baseline, a dirty tree
# in --card mode, pytest exit 5, or any blocking step != 0 makes the gate RED. Writes .gate/last_run.json
# (+ started_at) and .gate/last_run.digest (sha256 over the timestamp-free canonical part; two
# independent runs at the same sha with the same arguments on a clean tree MUST produce the same
# digest — that equality is what the script accepts as evidence, never a single agent's word). Prints
# "LEDGER_DIFF_STATS <json>" (in --card mode), "LEDGER_SHA256 <hex>" and "LEDGER_DIGEST <hex>" as its
# last lines. Exit 0 == green, nothing else is.
set -u
: "${VENV:?VENV (path of the 3.12 venv) is required}"
PY="$VENV/bin/python"
MODE=full; BASE=""; CARD=""; ORACLE=""; ONLY_TESTS=(); MUTANTS=""; OUT=""; CLEAN=0; SELFTEST=0; JOURNEYS=0
PROFILE=full; REQUIRE=""; XFAIL_ALLOW=""; TESTS_REMOVED=0; BASELINE=""; BASELINE_SHA=""; GATE_SHA=""; REVERT_ORACLE=""; TESTS_CSV=""
LIBSRC=""; LINT_BASE=""; BOUNDARY_SHA=""; APICARD=""
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;            --card) CARD="$2"; shift 2;;
    --oracle) ORACLE="$2"; shift 2;;        --out) OUT="$2"; shift 2;;
    --baseline) BASELINE="$2"; shift 2;;    --baseline-sha256) BASELINE_SHA="$2"; shift 2;;
    --gate-sha256) GATE_SHA="$2"; shift 2;; --profile) PROFILE="$2"; shift 2;;
    --require) REQUIRE="$2"; shift 2;;      --xfail-allow) XFAIL_ALLOW="$2"; shift 2;;
    --tests-removed) TESTS_REMOVED="$2"; shift 2;;  --tests) TESTS_CSV="$2"; shift 2;;
    --libsrc) LIBSRC="$2"; shift 2;;        --lint-base) LINT_BASE="$2"; shift 2;;
    --boundary-sha256) BOUNDARY_SHA="$2"; shift 2;;
    --apicheck) APICARD="$2"; MODE=apicheck; shift 2;;
    --only-tests) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do ONLY_TESTS+=("$1"); shift; done; MODE=only-tests;;
    --mutants) MUTANTS="$2"; MODE=mutants; shift 2;;
    --revert-proof) REVERT_ORACLE="$2"; MODE=revert-proof; shift 2;;
    --clean) CLEAN=1; shift;;               --self-test) SELFTEST=1; shift;;
    --journeys) JOURNEYS=1; shift;;
    *) echo "gate.sh: unknown arg $1" >&2; exit 64;;
  esac
done
# ---- 0a. self integrity: this very file must be the bytes the orchestrator pinned in args (CG1) ----
[ -n "$GATE_SHA" ] || { echo "gate.sh: --gate-sha256 is required (fail closed)" >&2; exit 66; }
[ "$(sha256sum < "$0" | cut -d' ' -f1)" = "$GATE_SHA" ] || { echo "gate.sh: this copy does not match the pinned sha256 (fail closed)" >&2; exit 66; }
case "$PROFILE" in full|bootstrap) ;; *) echo "gate.sh: --profile must be full|bootstrap" >&2; exit 64;; esac
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gate.sh: not inside a git checkout" >&2; exit 65; }
cd "$REPO" || exit 65
GITDIR="$(git rev-parse --git-dir)"; HEAD_SHA="$(git rev-parse HEAD)"
[ -n "$BASE" ] || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo "$HEAD_SHA")"
[ -n "$LINT_BASE" ] || LINT_BASE="$BASE"        # C-15: lint/claim range; the clean gate passes the previous clean head
[ -n "$OUT" ] || OUT="$REPO/.gate/last_run.json"; mkdir -p "$(dirname "$OUT")" "$REPO/.gate"
DIGEST_OUT="${OUT%.json}.digest"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; STEPS=(); RED=0; IDIOM_HITS=0; REQUIRED_MISSING=""; DIFFSTATS="null"; APIUNRES="[]"
step() { # name exit_code summary blocking(1|0)
  local n="$1" c="$2" s="$3" b="${4:-1}"
  STEPS+=("$("$PY" -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"exit_code":int(sys.argv[2]),"summary":sys.argv[3][:400],"blocking":sys.argv[4]=="1"}))' "$n" "$c" "$s" "$b")")
  if [ "$b" = "1" ] && [ "$c" != "0" ]; then RED=1; fi
}
finish() { # write the ledger + the timestamp-free digest, print both hashes, exit
  local counts="${PYCOUNTS:-null}" rp="${REDPROOF:-null}" mu="${MUTRES:-null}" rv="${REVERTRES:-null}" jo="${JOURNEYRES:-null}"
  "$PY" - "$OUT" "$DIGEST_OUT" "$HEAD_SHA" "$BASE" "$ORACLE" "$STARTED" "$MODE" "$PROFILE" "$CLEAN" "$IDIOM_HITS" "$REQUIRED_MISSING" "$counts" "$rp" "$mu" "$rv" "$jo" "$DIFFSTATS" "$APIUNRES" "$LINT_BASE" "${STEPS[@]}" <<'PYEOF'
import json, sys, hashlib, platform
(out, dout, head, base, oracle, started, mode, profile, clean, idiom_hits, req_missing, counts, rp, mu, rv, jo, ds, apiu, lint_base, *steps) = sys.argv[1:]
led = {"head_sha": head, "base_sha": base, "oracle": oracle, "lint_base": lint_base, "python": platform.python_version(), "started_at": started,
       "mode": mode, "profile": profile, "clean": clean == "1", "idiom_hits": int(idiom_hits),
       "required_missing": [p for p in req_missing.split(",") if p],
       "steps": [json.loads(s) for s in steps], "pytest": json.loads(counts), "red_proof": json.loads(rp),
       "mutants": json.loads(mu), "revert_proof": json.loads(rv), "journeys": json.loads(jo),
       "diff_stats": json.loads(ds), "apicheck_unresolvable": json.loads(apiu)}
led["green"] = all(s["exit_code"] == 0 for s in led["steps"] if s["blocking"])
pt = led["pytest"] or {}
canon = {k: led[k] for k in ("head_sha", "base_sha", "oracle", "lint_base", "mode", "profile", "clean", "python", "green", "idiom_hits", "required_missing", "red_proof", "mutants", "revert_proof", "journeys", "diff_stats", "apicheck_unresolvable")}
canon["steps"] = [{"name": s["name"], "exit_code": s["exit_code"]} for s in led["steps"]]
canon["pytest"] = {k: pt.get(k) for k in ("collected", "passed", "failed", "errors", "skipped", "xfailed")}
canon["outcomes_sha256"] = hashlib.sha256(json.dumps(pt.get("outcomes", []), sort_keys=True).encode()).hexdigest()
digest = hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
led["digest"] = digest
data = json.dumps(led, indent=1, sort_keys=True).encode()
open(out, "wb").write(data); open(dout, "w").write(digest + "\n")
if led["diff_stats"] is not None: print("LEDGER_DIFF_STATS", json.dumps(led["diff_stats"], sort_keys=True, separators=(",", ":")))
print("LEDGER_SHA256", hashlib.sha256(data).hexdigest())
print("LEDGER_DIGEST", digest)
PYEOF
  exit "$RED"
}
# ---- 0b. pre-step: interpreter, tools, listeners leaked from THIS tree only, stale lock, clean, dirty, required files ----
PYV="$("$PY" -V 2>&1)"; case "$PYV" in "Python 3.12."*) step interpreter 0 "$PYV";; *) step interpreter 1 "refusing: $PYV is not 3.12.x"; finish;; esac
for t in ruff pytest; do [ -x "$VENV/bin/$t" ] || step "tool:$t" 1 "missing in venv (fail closed)"; done
leaked=""
for pid in $(ss -ltnp 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
  [ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" = "$REPO" ] && [ "$pid" != "$$" ] && { kill "$pid" 2>/dev/null; leaked="$leaked $pid"; }
done   # CG2: the kill is scoped to listeners whose cwd is THIS worktree; sibling chains' servers are never touched
step stray-servers 0 "killed listeners with cwd == this tree:${leaked:- none}" 0
find "$GITDIR" -maxdepth 1 -name index.lock -mmin +10 -delete 2>/dev/null; step index-lock 0 "stale index.lock older than 10 min removed" 0
if [ "$CLEAN" = "1" ]; then
  if [ -n "$(git status --porcelain -uall)" ] || git symbolic-ref -q HEAD >/dev/null; then step clean-checkout 1 "--clean requires a detached, pristine checkout"; else step clean-checkout 0 "detached at $HEAD_SHA, tree clean"; fi
fi
if [ "$MODE" = "full" ] || [ "$MODE" = "only-tests" ]; then   # C-18: a digest is only comparable from a committed, clean tree
  dirty="$(git status --porcelain -uall -- . ':!.gate' ':!*__pycache__*' | head -5)"
  step tree-dirty "$([ -z "$dirty" ] && echo 0 || echo 1)" "${dirty:-tree clean (ignoring .gate/ and __pycache__)}"
fi
if [ -n "$REQUIRE" ]; then   # CG10: required-files manifest (JS passes the union for every merged card); absence is RED, never skipped
  for p in ${REQUIRE//,/ }; do [ -e "$p" ] || REQUIRED_MISSING="$REQUIRED_MISSING,$p"; done
  REQUIRED_MISSING="${REQUIRED_MISSING#,}"; step required-files "$([ -z "$REQUIRED_MISSING" ] && echo 0 || echo 1)" "${REQUIRED_MISSING:-all required files present}"
fi
if [ "$MODE" = "full" ]; then   # the baseline comes from args, pinned; never from a file inside a checkout (D2)
  if [ -z "$BASELINE" ] || [ -z "$BASELINE_SHA" ] || [ ! -f "$BASELINE" ]; then step baseline 1 "--baseline <path> --baseline-sha256 <hex> required in full mode (fail closed)";
  elif [ "$(sha256sum < "$BASELINE" | cut -d' ' -f1)" != "$BASELINE_SHA" ]; then step baseline 1 "baseline file does not match the pinned sha256 (fail closed)";
  else step baseline 0 "baseline pinned"; fi
fi
[ "$RED" = "1" ] && finish
# ---- helper: run pytest under a scrubbed env (no inherited secrets; network blackholed; fixed canary) -----
PYTEST_ENV=(env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$TMP" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONNOUSERSITE=1
            HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 TRANSFORMERS_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False
            HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
            CANARY_SECRET=canary-9f3e-not-a-secret QWEN_STUB=1)
run_pytest() { # tag paths...   (journeys carry the `journey` marker — card 01's tests/journeys/conftest.py adds it — and are deselected from every default run; C-4)
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider -p no:randomly --disable-socket --allow-hosts=127.0.0.1 -rs -m "not journey" --continue-on-collection-errors \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
run_pytest_journeys() { # tag paths...   (the ONLY runner that selects the journey marker; step 11 and the journeys author's --only-tests)
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider -p no:randomly --disable-socket --allow-hosts=127.0.0.1 -rs -m "journey" \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
counts() { "$PY" - "$1" <<'PYEOF'
import sys, json, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot(); s = r if r.tag == "testsuite" else r.find("testsuite")
    def tid(tc): return f'{tc.get("classname")}::{tc.get("name")}'
    def sk(tc):
        k = tc.find("skipped")
        return None if k is None else ("X" if "xfail" in ((k.get("type") or "") + (k.get("message") or "")).lower() else "S")
    def outcome(tc): return "F" if tc.find("failure") is not None else "E" if tc.find("error") is not None else sk(tc) or "P"
    c = {"collected": int(s.get("tests", 0)), "failed": int(s.get("failures", 0)) + int(s.get("errors", 0)),
         "errors": int(s.get("errors", 0)), "skipped": int(s.get("skipped", 0))}
    c["xfailed"] = sum(1 for tc in s.iter("testcase") if sk(tc) == "X")
    c["passed"] = c["collected"] - c["failed"] - c["skipped"]
    c["skip_ids"] = sorted(tid(tc) for tc in s.iter("testcase") if sk(tc) is not None)
    c["passed_ids"] = sorted(tid(tc) for tc in s.iter("testcase") if outcome(tc) == "P")
    c["outcomes"] = sorted(f'{tid(tc)}:{outcome(tc)}' for tc in s.iter("testcase"))
    print(json.dumps(c))
except Exception as e:
    print(json.dumps({"collected": 0, "error": str(e)}))
PYEOF
}
# ---- MODE only-tests: author-range tamper rules + confirm-RED (expected_green_tests are the characterisation exception, C-13) ----
if [ "$MODE" = "only-tests" ]; then
  "$PY" - "$BASE" "$CARD" "$XFAIL_ALLOW" <<'PYEOF' >"$TMP/atamper.log" 2>&1; step author-tamper $? "$(tail -c 300 "$TMP/atamper.log")"
import json, subprocess, sys, re, pathlib
base, card_path, xallow = sys.argv[1], sys.argv[2], sys.argv[3]
card = json.load(open(card_path)) if card_path else {}
allowed_mod = set(card.get("tests_allowed", [])); xfail_ok = set(card.get("xfail_allowed", [])) | set(x for x in xallow.split(",") if x)
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
bad = []
for line in git("diff", "--name-status", f"{base}..HEAD", "--", "tests/").splitlines():
    st, path = line.split("\t", 1)[0][:1], line.split("\t")[-1]
    if st in "MD" and path not in allowed_mod: bad.append(f"pre-existing test {st} outside tests_allowed: {path}")
    if st == "M" and path.endswith(".py"):
        before = git("show", f"{base}:{path}"); after = pathlib.Path(path).read_text(errors="ignore")
        if len(re.findall(r"^\s*assert\b", after, re.M)) < len(re.findall(r"^\s*assert\b", before, re.M)): bad.append(f"assertion count dropped in {path}")
for path in git("diff", "--name-only", "--diff-filter=AM", f"{base}..HEAD", "--", "tests/").split():
    if not path.endswith(".py") or not pathlib.Path(path).exists(): continue
    for m in re.finditer(r"pytest\.mark\.(xfail|skip|skipif)|pytest\.(skip|xfail)\(", pathlib.Path(path).read_text(errors="ignore")):
        if path.startswith("tests/journeys/") and "needs=" in pathlib.Path(path).read_text(errors="ignore"): break   # journeys: needs=<card> skips are the seam protocol (C-4)
        if not any(x.startswith(path) for x in xfail_ok): bad.append(f"skip/xfail marker in {path} with no xfail_allowed entry for that file"); break
print("\n".join(bad) or "author-range tamper rules ok"); sys.exit(1 if bad else 0)
PYEOF
  jo=1; for p in "${ONLY_TESTS[@]}"; do case "$p" in tests/journeys*) ;; *) jo=0;; esac; done
  if [ "$jo" = "1" ]; then   # journeys are composition tests: they may be green; the step reports, it does not judge
    rc="$(run_pytest_journeys red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
    step journeys-only-tests "$([ "$rc" = "0" ] || [ "$rc" = "1" ] && echo 0 || echo 1)" "rc=$rc $(printf '%s' "$PYCOUNTS" | head -c 200)"
    finish
  fi
  rc="$(run_pytest red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
  verdict="$("$PY" - "$PYCOUNTS" "$rc" "$TMP/pytest-red.log" "$CARD" <<'PYEOF'
import json, sys, re; c = json.loads(sys.argv[1]); rc = int(sys.argv[2]); log = open(sys.argv[3], errors="ignore").read()
card = json.load(open(sys.argv[4])) if sys.argv[4] else {}
eg = set(card.get("expected_green_tests", []))                       # C-13: characterisation pins / contract tests that are green-on-old BY DESIGN
passed = set(c.get("passed_ids", []))
classes = sorted(set(re.findall(r"\b(AssertionError|NotImplementedError|ImportError|ModuleNotFoundError|AttributeError|TypeError|ValueError|SyntaxError)\b", log)))
probs = []
if rc not in (1, 2): probs.append(f"rc={rc} (only 1/2 are red; 5 = nothing collected, 0 = nothing failed)")
if c.get("collected", 0) <= 0: probs.append("collected 0")
if c.get("failed", 0) <= 0: probs.append("no failing test (at least one new test must be RED)")
extra = sorted(passed - eg)
if extra: probs.append("green new tests outside expected_green_tests: " + ",".join(extra[:5]))
notgreen = sorted(eg - passed)
if notgreen: probs.append("expected_green_tests not green (the pin does not characterise the old tree): " + ",".join(notgreen[:5]))
print("0" if not probs else "1", "; ".join(probs) or f'collected={c.get("collected")} passed={c.get("passed")} failed={c.get("failed")} errors={c.get("errors")} rc={rc} expected_green={len(eg)} classes={",".join(classes)}')
PYEOF
)"; step confirm-red "${verdict%% *}" "${verdict#* }"
  finish
fi
# ---- MODE mutants: every scripted break must turn the card's tests red; ≥1 written, all killed, tree unchanged ----
if [ "$MODE" = "mutants" ]; then
  BEFORE="$(git status --porcelain | sha256sum)"
  MUTRES="$("$PY" - "$MUTANTS" "$TESTS_CSV" "$VENV" "$TMP" <<'PYEOF'
import json, sys, subprocess, pathlib
mut, tests_csv, venv, tmp = sys.argv[1:]; doc = json.load(open(mut))
ms = doc["mutants"] if isinstance(doc, dict) else doc; tests = [t for t in tests_csv.split(",") if t] or (doc.get("tests", []) if isinstance(doc, dict) else [])
res = {"written": len(ms), "killed": 0, "applied": 0, "detail": []}
if not tests: print(json.dumps({"written": 0, "killed": 0, "applied": 0, "detail": [{"error": "no test paths given (--tests)"}]})); sys.exit(0)
for m in ms[:3]:
    p = pathlib.Path(m["file"]); src = p.read_text(encoding="utf-8")
    if src.count(m["find"]) != 1: res["detail"].append({"file": m["file"], "applied": False}); continue
    p.write_text(src.replace(m["find"], m["replace"]), encoding="utf-8"); res["applied"] += 1
    rc = subprocess.run([f"{venv}/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--disable-socket", "--allow-hosts=127.0.0.1", *tests],
                        env={"PATH": f"{venv}/bin:/usr/bin:/bin", "HOME": tmp, "HF_HUB_OFFLINE": "1", "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "QWEN_STUB": "1", "CANARY_SECRET": "canary-9f3e-not-a-secret", "PYTHONDONTWRITEBYTECODE": "1"},
                        capture_output=True, text=True).returncode
    subprocess.run(["git", "checkout", "--", m["file"]], check=False)
    killed = rc in (1, 2); res["killed"] += killed; res["detail"].append({"file": m["file"], "applied": True, "killed": killed})
print(json.dumps(res))
PYEOF
)"; k="$("$PY" -c 'import json,sys; r=json.loads(sys.argv[1]); print(0 if (r["written"]>=1 and r["applied"]==r["written"] and r["killed"]==r["written"]) else 1)' "$MUTRES")"
  step mutants "$k" "$MUTRES"
  [ "$(git status --porcelain | sha256sum)" = "$BEFORE" ] || step mutants-roundtrip 1 "tree changed by the mutant round-trip"
  finish
fi
# ---- MODE revert-proof: the FINAL test set (author's + builder-added, C-28) must still be RED on the pre-implementation tree ----
if [ "$MODE" = "revert-proof" ]; then
  [ -n "$TESTS_CSV" ] || { step revert-proof 1 "--tests <p1,p2,...> required"; finish; }
  wt="$TMP/rp-revert"; git worktree add --detach "$wt" "$REVERT_ORACLE" >/dev/null 2>&1 || { step revert-proof 1 "worktree at oracle failed"; finish; }
  paths="${TESTS_CSV//,/ }"
  ( cd "$wt" && git checkout "$HEAD_SHA" -- $paths 2>/dev/null; "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 -m "not journey" $paths ) >"$TMP/revert.log" 2>&1; rc=$?
  git worktree remove --force "$wt" >/dev/null 2>&1
  obs="green"; if [ "$rc" = "1" ] || [ "$rc" = "2" ]; then obs="red"; elif [ "$rc" != "0" ]; then obs="unrunnable"; fi
  REVERTRES="{\"oracle\":\"$REVERT_ORACLE\",\"observed\":\"$obs\",\"rc\":$rc}"; step revert-proof "$([ "$obs" = "red" ] && echo 0 || echo 1)" "$REVERTRES"
  finish
fi
# ---- helper: apicheck — every symbol/kwarg the card expects exists in the pinned wheels; import first, then the wheel SOURCE (C-16);
#      a symbol whose module needs torch and has no source under --libsrc is recorded unresolvable-needs-torch, never RED ----
apicheck_run() { # card_path base
"$PY" - "$1" "$2" "$LIBSRC" "$TMP/api-unresolved.json" <<'PYEOF'
import json, sys, importlib, inspect, re, subprocess, pathlib, ast
card_path, base, libsrc, unres_out = sys.argv[1:]
bad = 0; unresolved = []
def source_file(module):
    if not libsrc: return None
    rel = module.replace(".", "/"); base = pathlib.Path(libsrc)
    if not base.is_dir(): return None
    for root in [base] + sorted(p for p in base.iterdir() if p.is_dir()):        # libsrc/<pkg>/… or libsrc/<dist>/<pkg>/… or libsrc/<dist>/src/<pkg>/…
        for cand in (root / (rel + ".py"), root / rel / "__init__.py", root / "src" / (rel + ".py"), root / "src" / rel / "__init__.py"):
            if cand.exists(): return cand
    return None
def params_of(node):
    ps = set(); a = node.args
    for x in a.posonlyargs + a.args + a.kwonlyargs: ps.add(x.arg)
    if a.kwarg: ps.add("kwargs")
    return ps
def from_source(module, symbol):
    f = source_file(module)
    if f is None: return None, "no-source"
    tree = ast.parse(f.read_text(errors="ignore"))
    parts = symbol.split("."); node = None; scope = tree.body
    for i, part in enumerate(parts):
        node = next((n for n in scope if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name == part), None)
        if node is None: return None, "missing"
        scope = node.body if isinstance(node, ast.ClassDef) else []
    if isinstance(node, ast.ClassDef):
        init = next((n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "__init__"), None)
        ps = params_of(init) if init else {"kwargs"}
        ps |= {t.attr for n in ast.walk(node) for t in ([n.targets[0]] if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute) else [])}
        return ps, "source"
    return params_of(node), "source"
for a in json.load(open(card_path)).get("apis_expected", []):
    how = "import"; params = None; err = None
    try:
        obj = importlib.import_module(a["module"])
        for part in a["symbol"].split("."): obj = getattr(obj, part)
        if a["module"].startswith("transformers") and a["symbol"].endswith("GenerationConfig"): params = set(vars(obj()).keys())
        else:
            try: params = set(inspect.signature(obj).parameters)
            except (TypeError, ValueError): params = set(dir(obj))
    except Exception as e:
        err = e; params, how = from_source(a["module"], a["symbol"])
    if params is None:
        if how == "missing": bad += 1; print("MISSING symbol in wheel source:", a["module"], a["symbol"]); continue
        unresolved.append(f'{a["module"]}.{a["symbol"]}'); print("UNRESOLVABLE (needs torch or an unlocated module; recorded, not RED):", a["module"], a["symbol"], type(err).__name__ if err else ""); continue
    missing = [k for k in a.get("kwargs", []) if k not in params and "kwargs" not in params]
    if missing: bad += 1; print("MISSING", a["module"], a["symbol"], missing, f"(resolved via {how})")
    else: print("OK", a["module"], a["symbol"], f"(resolved via {how})")
led = pathlib.Path("plan/api-ledger.json")
if led.exists():
    diff = subprocess.run(["git", "diff", f"{base}..HEAD", "--", "*.py", ":!tests/"], capture_output=True, text=True).stdout
    added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    for kb in json.load(open(led)).get("known_bad", []):
        if re.search(kb["idiom"], added): bad += 1; print("KNOWN-BAD idiom added:", kb["idiom"], "-", kb.get("why", ""))
else:
    bad += 1; print("plan/api-ledger.json missing in this tree (the plan branch must be merged first)")
json.dump(sorted(unresolved), open(unres_out, "w"))
print("apicheck", "ok" if not bad else f"{bad} problems", f"unresolvable={len(unresolved)}"); sys.exit(1 if bad else 0)
PYEOF
}
# ---- MODE apicheck: the verifier's SEPARATE run over the card extended with the builder's apis_used (C-18); own ledger ----
if [ "$MODE" = "apicheck" ]; then
  apicheck_run "$APICARD" "$BASE" >"$TMP/api.log" 2>&1; step apicheck-extended $? "$(tail -c 300 "$TMP/api.log")"
  [ -f "$TMP/api-unresolved.json" ] && APIUNRES="$(cat "$TMP/api-unresolved.json")"
  finish
fi
# ---- 1. hygiene: line endings, LFS, blob size, junk -------------------------------------------------
bad="$(git ls-files --eol | grep -E 'i/(crlf|mixed)|w/(crlf|mixed)' | grep -vE '\.(png|jpg|gif|bin)$' | head -5)"; step eol "$([ -z "$bad" ] && echo 0 || echo 1)" "${bad:-all tracked text files are LF}"
lfs="$(git lfs ls-files 2>/dev/null | head -3)"; step lfs "$([ -z "$lfs" ] && echo 0 || echo 1)" "${lfs:-no LFS objects}"
big="$(git rev-list --objects "$BASE..HEAD" 2>/dev/null | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>5242880' | head -3)"; step blob-cap "$([ -z "$big" ] && echo 0 || echo 1)" "${big:-no blob > 5 MB in range}"
junk="$(git ls-files | grep -E '(^|/)__pycache__/|\.pyc$|(^|/)\.venv/|(^|/)\.gate/|\.whl$|\.log$|(^|/)idx\.json$|(^|/)runlog_tail\.txt$|(^|/)\.env' | head -5)"; step junk-paths "$([ -z "$junk" ] && echo 0 || echo 1)" "${junk:-no junk tracked}"
# ---- 2. undefined names + syntax under 3.12 (syntax check writes no bytecode, so the tree stays clean for the digest) ----
if [ "${CLAIM_ONLY:-0}" != "1" ]; then
"$VENV/bin/ruff" check --select F821,F811,F401,E9 --target-version py312 --output-format concise . >"$TMP/ruff.log" 2>&1; step ruff $? "$(tail -c 300 "$TMP/ruff.log")"
"$PY" - <<'PYEOF' >"$TMP/compile.log" 2>&1; step syntax-312 $? "$(tail -c 200 "$TMP/compile.log")"
import pathlib, sys, subprocess
bad = 0
for p in subprocess.run(["git", "ls-files", "--", "*.py"], capture_output=True, text=True).stdout.split():
    try: compile(pathlib.Path(p).read_bytes(), p, "exec", dont_inherit=True)
    except SyntaxError as e: bad += 1; print(p, e)
print("syntax ok" if not bad else f"{bad} files fail to compile"); sys.exit(1 if bad else 0)
PYEOF
# ---- 3. apicheck (C-16: import, then wheel source; unresolvable recorded) + known-bad idioms from the ledger ----
if [ -n "$CARD" ]; then
  apicheck_run "$CARD" "$BASE" >"$TMP/api.log" 2>&1; step apicheck $? "$(tail -c 300 "$TMP/api.log")"
  [ -f "$TMP/api-unresolved.json" ] && APIUNRES="$(cat "$TMP/api-unresolved.json")"
fi
# ---- 4. locked oracle (S-5): the builder may not modify or delete ANY test; the suite that runs is the author's ----
if [ -n "$ORACLE" ]; then
  viol="$(git diff --name-status "$ORACLE..HEAD" -- tests/ | grep -E '^(M|D)' | head -5)"
  step oracle-lock "$([ -z "$viol" ] && echo 0 || echo 1)" "${viol:-no pre-existing test modified or deleted since the oracle}"
  git checkout "$ORACLE" -- tests/ 2>/dev/null || true          # reset every path that existed at the oracle; builder-added files survive
fi
# ---- 5. the suite (journeys deselected), twice, scrubbed env, network blackholed; counts vs the pinned baseline; skip/xfail SET rule ----
rc1="$(run_pytest one)"; rc2="$(run_pytest two)"; C1="$(counts "$TMP/junit-one.xml")"; C2="$(counts "$TMP/junit-two.xml")"; PYCOUNTS="$C1"
v="$("$PY" - "$C1" "$C2" "$rc1" "$rc2" "$BASELINE" "$CARD" "$XFAIL_ALLOW" "$TESTS_REMOVED" <<'PYEOF'
import json, sys
c1, c2 = json.loads(sys.argv[1]), json.loads(sys.argv[2]); rc1, rc2 = int(sys.argv[3]), int(sys.argv[4])
base = json.load(open(sys.argv[5]))                                   # pinned by sha256 in the pre-step; never a fallback
card = json.load(open(sys.argv[6])) if sys.argv[6] else {}
allow = set(card.get("xfail_allowed", [])) | set(x for x in sys.argv[7].split(",") if x)
removed = int(card.get("tests_removed_expected", 0) or 0) + int(sys.argv[8] or 0)
probs = []
if rc1 != 0 or rc2 != 0: probs.append(f"exit {rc1}/{rc2} (only 0 is green; 5 = nothing collected)")
if c1.get("outcomes") != c2.get("outcomes"): probs.append("two runs disagree (flaky)")
if c1.get("collected", 0) < base["baseline_collected"] - removed: probs.append(f'collected {c1.get("collected")} < baseline {base["baseline_collected"]} - removed {removed}')
new_skips = sorted(set(c1.get("skip_ids", [])) - set(base.get("skipped_ids", [])) - allow)
if new_skips: probs.append("skip/xfail not in baseline or xfail_allowed: " + ",".join(new_skips[:5]))
print("0" if not probs else "1", "; ".join(probs) or f'collected={c1.get("collected")} passed={c1.get("passed")} identical twice')
PYEOF
)"; step pytest-x2 "${v%% *}" "${v#* }"
# ---- 6. import smoke (C-1): the CPU front is imported ONLY once app.py is the composition root (api/app.py arrives with card 03b);
#         before that the legacy monolith is never imported (it loads torch and the tokenizer at module level); worker with card 01's stubs ----
if [ -f api/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" timeout 20 "$PY" -c "import app" ) >"$TMP/imp.log" 2>&1; step import-app $? "$(tail -c 200 "$TMP/imp.log")"
else step import-app 0 "not yet a composition root (api/app.py absent; required after platform-03b-thin-slice)" 0; fi
if [ -f worker/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" PYTHONPATH="$REPO/tools/stubs" timeout 30 "$PY" -c "import worker.app" ) >"$TMP/impw.log" 2>&1; step import-worker $? "$(tail -c 200 "$TMP/impw.log")"; fi
fi # CLAIM_ONLY
# ---- 7. claim-vs-diff lint over every commit in the LINT range; waivers counted per Card: trailer (C-15) ----
"$PY" - "$LINT_BASE" <<'PYEOF' >"$TMP/claims.log" 2>&1; step claim-lint $? "$(tail -c 300 "$TMP/claims.log")"
import re, subprocess, sys, collections
base = sys.argv[1]; shas = subprocess.run(["git", "rev-list", "--reverse", f"{base}..HEAD"], capture_output=True, text=True).stdout.split()
waivers = collections.Counter(); bad = 0
for sha in shas:
    msg = subprocess.run(["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True).stdout
    diff = subprocess.run(["git", "show", "--format=", "-w", "--unified=0", sha], capture_output=True, text=True).stdout
    names = subprocess.run(["git", "show", "--format=", "--name-only", sha], capture_output=True, text=True).stdout
    hay = re.sub(r"\s+", "", diff + names)
    if "Renormalize-Only: yes" in msg:
        if subprocess.run(["git", "show", "--format=", "-w", "--numstat", sha], capture_output=True, text=True).stdout.strip(): bad += 1; print(sha[:9], "Renormalize-Only commit has non-whitespace changes")
        continue
    if "Claim-Waiver:" in msg:
        m = re.search(r"^Card:\s*(\S+)", msg, re.M); waivers[m.group(1) if m else "(no Card trailer)"] += 1; continue
    claims = set(re.findall(r"`([^`\n]{2,80})`", msg))
    claims |= set(re.findall(r"^\s*[-*]\s*(?:add|adds|added|define|defines|implement|implements|set|sets|fix|fixes)\s+(\S+)", msg, re.I | re.M))
    claims |= set(re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:tok/s|tokens?|s\b|sec|min|tests?)", msg))
    for c in sorted(claims):
        if re.sub(r"\s+", "", c) not in hay: bad += 1; print(sha[:9], "claim not in diff:", c)
for card, n in waivers.items():
    if n > 1: bad += 1; print(f"more than one Claim-Waiver for {card} in range ({n})")
print("claim-lint", "ok" if not bad else f"{bad} unsupported claims"); sys.exit(1 if bad else 0)
PYEOF
[ "${CLAIM_ONLY:-0}" = "1" ] && finish
# ---- 8. scope, protected files, plan/ immutability, builder-test tamper idioms, dod-command flags, dependency drift; diff_stats (C-13) ----
if [ -n "$CARD" ]; then
"$PY" - "$CARD" "$BASE" "$TMP/diffstats.json" <<'PYEOF' >"$TMP/scope.log" 2>&1; step scope-protected-tamper $? "$(tail -c 300 "$TMP/scope.log")"
import json, sys, subprocess, re, pathlib
card = json.load(open(sys.argv[1])); base = sys.argv[2]
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
changed = git("diff", "--name-only", f"{base}..HEAD").split()
added = git("diff", "--name-only", "--diff-filter=A", f"{base}..HEAD").split()
prot = [l.strip() for l in pathlib.Path("tests/protected.txt").read_text().splitlines() if l.strip()] if pathlib.Path("tests/protected.txt").exists() else []
allowed = set(card.get("files_allowed", [])) | set(card.get("new_modules", []))
req = set(card.get("new_modules", [])) | set(card.get("required_files", []))   # C-21: a card OWNS a protected path its manifest must deliver; platform-01-gate owns the rest via protected_touch
bad = []
for f in changed:
    if f.startswith("plan/") and not f.startswith("plan/status/"): bad.append(f"plan/ is immutable during a run (plan/fixes/ is written only by the integrator, outside any card range): {f}")
    elif f in prot and not (card.get("protected_touch") or f in req): bad.append(f"protected file touched outside its owner card: {f}")
    elif f not in allowed and not (f in added and f.startswith("tests/unit/")): bad.append(f"outside files_allowed: {f}")
for f in changed:
    if not f.endswith(".py") or not pathlib.Path(f).exists(): continue
    s = pathlib.Path(f).read_text(errors="ignore")
    if not f.startswith("tests/") and re.search(r'PYTEST_CURRENT_TEST|sys\.modules\.get\("pytest"\)|"pytest" in sys\.modules', s): bad.append(f"test-detection idiom in {f}")
    if f in added and f.startswith("tests/unit/") and re.search(r"pytest\.mark\.(xfail|skip|skipif)|pytest\.(skip|xfail)\(|except Exception:\s*(pass|return)|sys\.exit\(0\)", s): bad.append(f"tamper idiom in builder-added test {f}")
for d in card.get("dod", []):
    if re.search(r"(^|\s)(-k|-x|--deselect|--ignore|--lf)(\s|=)|\|\|\s*true", d.get("command", "")): bad.append(f"dod {d.get('id')} command narrows or masks pytest")
for f in changed:
    if re.match(r"(worker/)?requirements.*\.txt$", f):
        for line in git("diff", f"{base}..HEAD", "--", f).splitlines():
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip() and not line[1:].lstrip().startswith("#"):
                pkg = re.split(r"[<>=!~\[ ]", line[1:].strip())[0].lower()
                if pkg not in [d.lower() for d in card.get("deps_allowed", [])]: bad.append(f"dependency not in deps_allowed: {pkg}")
# diff_stats (C-13): whitespace-insensitive, excluding the pinned gate copy and fixtures; Renormalize-Only commits are whitespace-only and vanish under -w
ins = dele = files = 0
for line in git("diff", "-w", "--numstat", f"{base}..HEAD", "--", ".", ":!tools/gate.sh", ":!tests/fixtures/").splitlines():
    a, b, _ = line.split("\t", 2)
    if a.isdigit() and b.isdigit(): ins += int(a); dele += int(b); files += 1
json.dump({"files": files, "insertions": ins, "deletions": dele, "excluded": ["tools/gate.sh", "tests/fixtures/"]}, open(sys.argv[3], "w"), sort_keys=True)
print("\n".join(bad) or "scope/protected/plan/tamper/deps ok"); sys.exit(1 if bad else 0)
PYEOF
[ -f "$TMP/diffstats.json" ] && DIFFSTATS="$(cat "$TMP/diffstats.json")"
fi
# ---- 9. idiom lint over the LINT range, code only (tests/ excluded, comments stripped — C-15): blocking subset + warning subset counted ----
blockidioms='preexec_fn=|trust_remote_code=True|from gradio\.client import|prefill_chunk_size|continue_final_message=.*(think|reasoning)'
warnidioms='__wrapped__|shutil\.rmtree[^\n]*unload|lease_s *- *30|Chatbot\([^)]*type=|ChatInterface\([^)]*type=|spaces\.GPU\([^)]*gpu_size=|restart_space\([^)]*revision|read_text\([^)]*newline=|max_retries=[1-9]|assisted_generation|assistant_model=|presence_penalty=[1-9]'
addedcode="$(git diff "$LINT_BASE..HEAD" -- '*.py' ':!tests/' | grep -E '^\+' | grep -vE '^\+\+\+' | sed -E 's/#.*$//')"
bhits="$(printf '%s\n' "$addedcode" | grep -nE "$blockidioms" | head -8)"; step idiom-blocking "$([ -z "$bhits" ] && echo 0 || echo 1)" "${bhits:-no decision-level idiom added}"
whits="$(printf '%s\n' "$addedcode" | grep -nE "$warnidioms" | head -8)"; IDIOM_HITS="$(printf '%s' "$whits" | grep -c . || true)"
step idiom-lint 0 "IDIOM_HITS=$IDIOM_HITS ${whits:-no known-bad idiom added}" 0
# ---- 10. generated README, catalog provenance + admission, protected tests, persona-boundary fixture pin (present ⇒ run; required ⇒ manifest) ----
if [ -f tools/render_readme.py ]; then "$PY" tools/render_readme.py --check >"$TMP/readme.log" 2>&1; step readme-render $? "$(tail -c 200 "$TMP/readme.log")"; fi
if [ -f models.yaml ]; then "$PY" - <<'PYEOF' >"$TMP/cat.log" 2>&1; step catalog-provenance $? "$(tail -c 200 "$TMP/cat.log")"
import yaml, sys, pathlib, re
bad = []
for e in (yaml.safe_load(open("models.yaml")) or {}).get("models", []):
    p = e.get("provenance", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(e.get("revision", ""))): bad.append(f'{e.get("id")}: revision is not a 40-hex sha')
    if not all(p.get(k) for k in ("source_url", "fetched_at", "saved_path")): bad.append(f'{e.get("id")}: provenance incomplete')
    elif not pathlib.Path(p["saved_path"]).exists(): bad.append(f'{e.get("id")}: saved_path missing {p["saved_path"]} (must be inside the repo: evidence/catalog/)')
    if e.get("admission") not in ("pending", "passed", "failed"): bad.append(f'{e.get("id")}: admission must be pending|passed|failed')
    if e.get("backend") == "local" and "has_visual_tensors" not in e: bad.append(f'{e.get("id")}: local entry must record has_visual_tensors (VLM class)')
print("\n".join(bad) or "catalog provenance/admission ok"); sys.exit(1 if bad else 0)
PYEOF
fi
pt=""; for f in tests/test_constants_pin.py tests/test_import_contract.py tests/test_personas.py tests/test_python_eval_surfaces.py tests/test_catalog_policy.py; do [ -f "$f" ] && pt="$pt $f"; done
if [ -n "$pt" ]; then rc="$(run_pytest prot $pt)"; step protected-tests "$rc" "$(tail -c 200 "$TMP/pytest-prot.log")"; fi
if [ -f tests/fixtures/persona_boundary.json ] && [ -n "$BOUNDARY_SHA" ]; then   # C-21: the owner-generated fixture is pinned by sha256, never by protected.txt
  step boundary-fixture "$([ "$(sha256sum < tests/fixtures/persona_boundary.json | cut -d' ' -f1)" = "$BOUNDARY_SHA" ] && echo 0 || echo 1)" "tests/fixtures/persona_boundary.json vs owner_approvals.persona_boundary_fixture_sha256"
fi
# ---- 11. journeys (C-4): the ONLY run that selects the journey marker; needs=<card> skips are counted, any other skip or failure is RED;
#          a skipped seam whose card is merged is turned into a blocking finding by the script ----
if [ "$JOURNEYS" = "1" ] && [ -d tests/journeys ]; then
  if ls tests/journeys/test_*.py >/dev/null 2>&1; then
    rc="$(run_pytest_journeys journeys tests/journeys)"; JC="$(counts "$TMP/junit-journeys.xml")"
    JOURNEYRES="$("$PY" - "$JC" "$rc" "$TMP/pytest-journeys.log" <<'PYEOF'
import json, sys, re; c = json.loads(sys.argv[1]); rc = int(sys.argv[2]); log = open(sys.argv[3], errors="ignore").read()
needs = sorted(set(re.findall(r"needs=([A-Za-z0-9_-]+)", log)))
skipped = c.get("skipped", 0); other = max(0, skipped - len(re.findall(r"needs=", log)))
ok = rc == 0 and c.get("collected", 0) > 0 and c.get("failed", 0) == 0 and other == 0
print(json.dumps({"rc": rc, "ok": ok, "collected": c.get("collected", 0), "failed": c.get("failed", 0), "skipped": skipped, "skipped_other": other, "skipped_needs": needs}, sort_keys=True))
PYEOF
)"; step journeys "$("$PY" -c 'import json,sys; sys.exit(0 if json.loads(sys.argv[1])["ok"] else 1)' "$JOURNEYRES" && echo 0 || echo 1)" "$JOURNEYRES"
  else JOURNEYRES='{"rc":5,"ok":true,"collected":0,"failed":0,"skipped":0,"skipped_other":0,"skipped_needs":[]}'; step journeys 0 "no journeys yet (tests/journeys/test_*.py absent)" 0; fi
fi
# ---- 12. self-test (D-14): RED on the known-broken tree, RED on the false-claim fixture FROM THE CLAIM-LINT STEP (C-2); own exit code (C-37) ----
if [ "$SELFTEST" = "1" ]; then
  : "${BROKEN_SHA:?BROKEN_SHA (f88b120…) required with --self-test}"
  st_rc=0; rp='{'; wt="$TMP/rp-broken"
  if git worktree add --detach "$wt" "$BROKEN_SHA" >/dev/null 2>&1; then
    ( cd "$wt" && "$VENV/bin/ruff" check --select F821,F811,E9 --target-version py312 . >/dev/null 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
    rp="$rp\"broken_red\":$([ "$got" != "0" ] && echo true || echo false),"; [ "$got" = "0" ] && st_rc=1
  else rp="$rp\"broken_red\":false,\"broken_note\":\"worktree-failed\","; st_rc=1; fi
  if [ -f tests/fixtures/gate/false-claim.patch ]; then
    wt="$TMP/rp-claim"
    # The fixture message MUST yield claims under step 7's three regexes (backticks; "- add/set <token>" bullets; a number with a unit) and the
    # patch MUST NOT contain those tokens: 3 claims — `_resolve_image_urls`, TOK_PER_SEC, 9.2 — none in the diff → claim-lint RED.
    if git worktree add --detach "$wt" "$HEAD_SHA" >/dev/null 2>&1 && ( cd "$wt" && git apply "$REPO/tests/fixtures/gate/false-claim.patch" && git -c user.name=gate -c user.email=gate@local commit -qam "feat: add \`_resolve_image_urls\` and set TOK_PER_SEC" -m "- add _resolve_image_urls"$'\n'"- set TOK_PER_SEC to 9.2 tok/s" ) >/dev/null 2>&1; then
      ( cd "$wt" && CLAIM_ONLY=1 VENV="$VENV" bash "$0" --gate-sha256 "$GATE_SHA" --baseline "$BASELINE" --baseline-sha256 "$BASELINE_SHA" --base HEAD~1 --out "$TMP/claim.json" >"$TMP/claim.log" 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
      fc="$("$PY" - "$TMP/claim.json" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1])); s = next((s for s in d["steps"] if s["name"] == "claim-lint"), None)
    if s is None: print("no-claim-lint-step")
    elif s["exit_code"] != 0 and "unsupported claims" in s["summary"]: print("true")      # the RED must come from claim-lint itself
    else: print("false")
except Exception: print("inner-ledger-unreadable")
PYEOF
)"
      rp="$rp\"false_claim_red\":\"$fc\","; [ "$fc" = "true" ] || st_rc=1
    else rp="$rp\"false_claim_red\":\"worktree-failed\","; st_rc=1; fi
  elif [ "$PROFILE" = "bootstrap" ]; then rp="$rp\"false_claim_red\":\"fixture-not-yet-delivered\",";
  else rp="$rp\"false_claim_red\":\"fixture-missing\","; st_rc=1; fi
  REDPROOF="${rp%,}}"; step self-test "$st_rc" "$REDPROOF"
fi
# ---- 13. gate integrity: the repo copy (CI runs it) and its committed pin must equal this pinned copy ----
if [ -f tools/gate.sh ]; then step gate-integrity "$([ "$(sha256sum < tools/gate.sh | cut -d' ' -f1)" = "$GATE_SHA" ] && echo 0 || echo 1)" "tools/gate.sh vs pinned sha256"; fi
if [ -f tools/gate.pin ]; then step gate-pin "$([ "$(tr -d '[:space:]' < tools/gate.pin)" = "$GATE_SHA" ] && echo 0 || echo 1)" "tools/gate.pin (read by CI) vs pinned sha256"; fi
# ---- 14. secrets regex over the diff range, commit messages AND this run's own logs; the summary is a constant string ----
SECRET_RE='ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
if { git diff "$BASE..HEAD"; git log -p --format=%B "$BASE..HEAD"; } | grep -qE "$SECRET_RE" || grep -rqE "$SECRET_RE" "$TMP" 2>/dev/null; then
  step secrets-scan 1 "secret-shaped string in range or in this run's logs (value never printed)"; else step secrets-scan 0 "no secret-shaped strings"; fi
finish
```

### 7.3 Notes on the script (each is a design decision; v2 changes marked)

- **Pins.** `--gate-sha256` is mandatory (exit 66 otherwise); `--baseline <path> --baseline-sha256 <hex>` are mandatory in full mode and the baseline is `{base_sha, baseline_collected, skipped_ids[]}` (a SET of ids, not a count), so the skip rule is `new_skips = run_skips − baseline.skipped_ids − xfail_allowed = ∅` (J1 D2/CG9): an xfail in a new test file is fine only when the card lists it; a newly skipped pre-existing test is always red; no trailers exist any more. The in-repo copy is double-pinned (`args.gate_sha256` AND `tools/gate.pin`). **V2: `--boundary-sha256` pins the persona fixture's sha256 (C-21) — it is recorded as not-yet-delivered and non-blocking until card 13b is in the tree, then enforced.**
- **Oracle lock (S-5, A1 step 3).** With `--oracle <tests_head>` any M/D under `tests/` since the oracle is RED (the builder may only ADD under `tests/unit/`), then `git checkout <oracle> -- tests/` makes the author's suite the one that runs; builder-added files survive. The diff is against the **oracle**, not the base, so the merged tests are never a violation (the A1 defect J1 reproduced).
- **Profile.** `--profile bootstrap` skips only apicheck's known-bad read and tolerates a missing false-claim fixture in the self-test; it is recorded in the ledger and the digest, and `taskDone()` rejects it for every card but `platform-01-gate`.
- **Required files (`--require`).** V2: JS passes the union of the merged cards' `new_modules ∪ required_files` (C-14), validated at plan time against the design's `MANIFEST_MIN` (which is itself derived from the cards and made conditional on `args.torch_in_venv`, C-14) — the manifest and the plan can no longer contradict. Every path must exist or the gate is RED — the `-f` guards are therefore fail-open only until the owning card merges and fail-closed for the rest of the run (J1 CG10/CG11).
- **Apicheck (v2, C-16).** Import-first: each `apis_expected`/`apis_used` symbol is imported from the pinned venv; if that fails (e.g. a torch-only symbol), the gate ast-parses the symbol's module inside the pinned wheel SOURCE under `--libsrc` — a symbol that exists but lacks a used kwarg is RED; a module that cannot be located at all is recorded `unresolvable` (surfaced as `api_unresolvable[]`) and is **never RED**. `plan/api-ledger.json`'s `known_bad[]` regexes are checked in the same step and are always RED.
- **Claim lint with per-card waivers (v2).** Backticked symbols, bullet claims and number+unit claims from commit messages are matched against the diff; a `Claim-Waiver:` line is counted **per `Card:` trailer** (C-3/C-13), so two cards in one merge range cannot consume each other's waivers and a waiver without its card in range is itself a violation.
- **Idiom lint in two tiers (scoped, C-15).** Blocking: `preexec_fn=`, `trust_remote_code=True`, `from gradio.client import`, `prefill_chunk_size`, `continue_final_message=…(think|reasoning)` (each is a decided value). Warning: the remaining CORRECTED-line idioms. Both tiers scan **only `--lint-base..HEAD`**, over `*.py` excluding `tests/`, with comments stripped first — so an idiom fixed in an earlier wave is not re-counted and the rule cannot fire on a legitimate quote in a comment. The ledger carries `IDIOM_HITS=<n>` and `taskDone()` requires `warnings_cleared.length ≥ idiom_hits` (F-10 in code, A2 G14).
- **Journeys counting (v2, C-4).** `--journeys` selects only the `journey`-marked collection (the marker is applied by `tests/journeys/conftest.py`, delivered by card 01 with the exact path-scoped hook pinned in §4.8 — v2.1 V-2; `pytest.ini` registers it and deselects it from every default run). The gate parses skip reasons: `needs=<card-id>` is the only legal reason; `skipped_other = max(0, skipped − needs-matches)` is RED. At every merge gate the counting is what turns "merged but still skipped" into a finding (§6).
- **Scope and the ownership rule (v2, C-21).** Hunks outside `files_allowed ∪ new_modules`, any hunk under `plan/`, and requirement lines outside `deps_allowed` are RED. A hunk on a **protected** path is RED unless the card's own manifest (`MANIFEST_MIN[id]`) declares it or the card carries `protected_touch` (only `platform-01-gate`) — ownership, not a blanket ban, checked identically in `validateCards` and in the gate.
- **Diff stats (v2, C-25).** In `--card` mode the gate prints `LEDGER_DIFF_STATS` (insertions/deletions per file), **excluding `tools/gate.sh` and `tests/fixtures/`** so card 01's own gate-and-fixture payload cannot trip the size rule (C-13); JS fails the card closed when the stats are missing.
- **Stray listeners.** The pre-step kills only listeners whose `/proc/<pid>/cwd` equals the current tree; at cap ≥ 2 the other chain's server lives in a sibling worktree and is never touched (J1 CG2). Test harnesses pick a free port and tear down in `try/finally` (card 03b/06 rule).
- **Secrets.** `env -i` with a fixed `CANARY_SECRET` for every pytest; the secrets step scans the diff range, the commit messages **and this run's own logs** (A2 step 9) and reports a constant string; the JS layer redacts structured returns on top (CG3). **V2: the prompts fix a dummy-credential convention (`TESTTOKEN-…`) so a fixture cannot match the regex and park its own card (C-32).**
- **Self-test.** `--self-test` runs on every clean gate (A2 step 15): RED on the broken base via ruff, and RED on the false-claim fixture *verified from the inner ledger's `claim-lint` step* — a RED for any other reason does not count. **V2 (C-2), delivery corrected in v2.1 (V-4): the false-claim fixture pair (patch + target) is delivered by card 01 at `tests/fixtures/gate/` — the gate creates only the temp worktree and crafts the fixture's commit message to MATCH the claim-lint regexes ("feat: add `_resolve_image_urls` …") while the patch does not change the symbol — so the fixture really produces lint claims and the inner run can only go red through claim-lint; the step asserts `false_claim_red === 'true'`. P0's bootstrap-profile red-proof tolerates `fixture-not-yet-delivered` and proves `broken_red` live.**

---

## 8. Testability table

`verification_level` is a fixed enum on every DoD line and every finding: `local-mechanical | local-stub | staging-required | owner-required | unverified`. `STAGING_RE` (lease, quota, ZeroGPU, worker fork, Triton, fla, `x-ip-token`, MCP transport, Space rebuild, cold-start, tok/s, FP8, GPTQ, provider, requirements resolution, canary, rollback, OIDC, secret) raises the level **in JS at validation and at return time** (`raiseLevels`), regardless of what an agent wrote (F-37; A1 §13.1, A2 §13). Nothing at `staging-required` or above can be `pass` in R1. An API symbol the apicheck cannot resolve **without torch or outside the pinned wheels** is recorded `unresolvable-needs-torch` and is **never RED** (C-16): it surfaces per card as `api_unresolvable[]` in the checkpoint and in the synthesizer's report instead of failing the build.

| Level | Proven locally in R1 (3.12 venv, no GPU, no token, network blackholed) | Requires the staging Space (R2; CI writes files; the workflow reads them) | Requires the owner |
|---|---|---|---|
| **Static gate** | ruff F821/F811/F401/E9 @py312, compileall (`read()`-only, no exec), apicheck (import-first from the venv, else ast-parse of the wheel SOURCE under `--libsrc`; a missing kwarg or symbol is RED, an unlocatable module is `unresolvable`, recorded not RED) + `known_bad[]` regexes from `plan/api-ledger.json`, claim-vs-diff lint (backticked symbols + bullet claims + number+unit claims from commit messages vs the diff; `Claim-Waiver:` per `Card:` trailer), EOL/LFS/5 MB-blob/junk, secrets regex over the range, the commit messages and the gate's own logs (constant summary), import-contract test, scope step (protected paths owned via `MANIFEST_MIN` ∪ `protected_touch` — the ownership rule, C-21; `plan/` immutable; tamper idioms; `deps_allowed`), idiom lint in two tiers scoped to `--lint-base..HEAD` over `*.py` excluding `tests/` with comments stripped, README render check, `models.yaml` schema + provenance existence + admission enum + `has_visual_tensors` on local entries, boundary-fixture sha pin (`--boundary-sha256`, non-blocking until card 13b is in the tree), gate integrity vs `args.gate_sha256` AND `tools/gate.pin`, required-files manifest (`--require`, derived from the cards' `new_modules ∪ required_files`, validated against `MANIFEST_MIN`), LEDGER_DIFF_STATS printed per card (excludes `tools/gate.sh` and `tests/fixtures/`; insertions+deletions ≤ 2 × est_lines in JS, fail-closed on absence, C-25), journeys `needs=` counting (a journey skipped without `needs=` is RED; `skipped_other` vs `needs=` occurrences) | — | — |
| **Unit / stub** | the 73 existing tests + the 10 pins; `backends/fake` + conformance rows (`recorded-*` skipped-needs-owner until fixture #1, counted); `StreamParser` incl. tool_parse known-bads (`xfail_allowed`); `core/agent` cap/rejection/pairing; `SessionStore` TTL; `worker/encode` + `worker/lease` pure functions incl. **token-level continuation with a fake generate (seam integrity; greedy equality)**, the stop-event `StoppingCriteria` with a fake, the `find_spec` probe line; `python_eval` red-proofs with `CANARY_SECRET` (allowlist, `/proc/<ppid>/environ` unreadable, rlimit trips, `killpg`, **OFF on every surface: checkbox alone, `/v1`, MCP**); SSRF/regex/calculator/archive; `apply_patch` EOL; constants pin (every ship-but-flag row); persona absence test against shingle hashes (runs only when the boundary fixture is pinned — before card 13b merges the gate records it as not-yet-delivered instead); catalog policy (pending hidden); harness `--dry-run` zero-call; scripted mutants ×3 + revert-proof per card (both sides of confirm-RED honour `expected_green_tests`: an extra green new test is RED, a listed-not-green one is RED); `PresencePenalty` CPU test **only if the venv holds torch (§15 Q2)** — the default decision removes the placebo and `worker/penalty.py` from card 08a's manifest (C-14) | — | — |
| **Local integration** | FastAPI `TestClient(app)` for `/v1/*`, `/healthz` (sha from a fixture `build_info.json`; `unknown` rejected), `/status`, `/v1/preflight`; `gradio_client==2.6.1` against `demo.launch(prevent_thread_lock=True, server_port=<free>)`; MCP listing snapshot = 4 typed tools (if `gradio[mcp]` installs, else `deferred`); journeys J1 + H1-H7 on the fake backends — **collected only by `gate.sh --journeys`** (the `journey` marker is added by `tests/journeys/conftest.py`, delivered by card 01) and never by the default suite (card 03b's own gate command runs both collections — C-1/C-4) | — | — |
| **Platform behaviour** | nothing (`spaces.GPU` is a no-op off-platform) | CPU Space boot + `/healthz.git_sha == pushed sha` (CI wrote `build_info.json`); worker import-time load with the VLM class under CUDA emulation; lease sizing + measured cold-start margin; measured tok/s; quota bucket of `gradio_client` calls with the scoped token; **`find_spec('fla')` true and Triton JIT inside the first lease on the staging worker (card 08d)**; FP8-with-visual-tensors vs GPTQ on `large`; requirements resolution on rebuild vs `requirements.lock` (3.12.12 vs 3.12.3 — the evidence reader compares `build-log.txt`); `x-ip-token` presence; MCP over HTTP; canary pass^3; rollback rehearsal; the hardening self-test endpoint output (RLIMIT behaviour under the Spaces runtime, UNVERIFIED) | creates the two staging Spaces and the scoped token(s) per `token_topology`; sets the staging secrets |
| **Money / identity** | nothing | — | fixture #1 (cents; **precondition of card 04**); the real 12-prompt harness (≥ 1 `passed` entry before promotion); the VLM-class export HF Job if `needs_export`; GitHub repo + Trusted Publisher OIDC; the F-38 read of the production Space HEAD; revoking tokens; disabling the scheduled tasks; Dev Mode off; production promotion |

**How staging/promotion requests are represented.** (1) the checkpoint object (§2.2); (2) `plan/status/<id>.json` with `dod[i].status = 'deferred'`; (3) `evidence/staging/<sha>/EXPECTED.json` — the contract is defined by `tools/expected.py` (card 14) and the file is written **by CI at deploy** (agents never write evidence); R2's evidence verifier reports a finding per missing or contradicting number, never infers; `owner_approvals.production_space_head` is a required field of the promotion action (F-38 as data). **New owner field in v2:** `owner_approvals.persona_boundary_fixture_sha256` — the sha256 the gate pins (`--boundary-sha256`) so the persona card's fixture copy step is verifiable without the workflow ever seeing the clause (C-21).

---

## 9. Schemas for every stage (JSON Schema; `required ⊆ properties`; enum verdicts; `sha` wherever code was read)

Design rules: root `{type:'object', properties, required}`; every verdict an enum; **keyword set limited to `type / enum / required / properties / items / minItems / description`** — `pattern`, `maxLength`, `minLength`, `minimum`, `maximum` were removed because their support in the StructuredOutput validator is UNVERIFIED (J2 gap 5) and are enforced in JS instead (`isSha`, `isHex64`, `cap()`, `okSemantics`); `minItems` on evidence arrays (F-46); a shared fragment (`COMMON`) on every schema adds `git_common_dir` (F-1 prefix test + store identity). Mechanical walk (v2): **34 object nodes, 7 roots; `required ⊆ properties` holds everywhere; no empty enums; no cross-namespace collisions** — the walk script is `check_schemas.mjs` in the scratch dir and its numbers are asserted, not eyeballed.

```js
// design-v2 §9 — schemas. Keyword set deliberately limited to what the observed run exercised
// (type / enum / required / properties / items / minItems / description). No pattern, maxLength,
// minLength, minimum or maximum: their support in the StructuredOutput validator is UNVERIFIED
// (J2 gap 5), so every such constraint is enforced in JS instead (isSha, cap(), okSemantics).
const LEVELS = ['local-mechanical', 'local-stub', 'staging-required', 'owner-required', 'unverified']
const COMMON = {
  repo_toplevel: { type: 'string', description: 'output of git rev-parse --show-toplevel in the checkout you worked in ("" if you touched no checkout)' },
  git_common_dir: { type: 'string', description: 'output of git rev-parse --path-format=absolute --git-common-dir in that checkout ("" if none); must be <build_repo>/.git' },
  outward_actions_taken: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: any push/repo/Space/secret/HF-job/*.hf.space action' },
  installed_packages: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: pip/uv/npm installs are forbidden' },
  notes: { type: 'string', description: '<= 120 words; never a summary of another agent' },
}
const COMMON_REQ = ['repo_toplevel', 'git_common_dir', 'outward_actions_taken', 'installed_packages']
const CMD = { type: 'object', properties: { command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', description: '<= 40 lines verbatim; secret-shaped strings are redacted in JS' } }, required: ['command', 'exit_code', 'output_tail'] }
const GATE_STEP = { type: 'object', properties: { name: { type: 'string' }, exit_code: { type: 'integer' } }, required: ['name', 'exit_code'] }
const ROW_STATE = ['merged+gate-green', 'merged+gate-red', 'parked', 'reverted', 'revert-failed', 'blocked_on_owner', 'dropped_null', 'not_attempted', 'deferred']

// ---- 9.0 SETUP (integrator mode:setup; also the ONE live state probe per invocation) ----
const SETUP = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  venv_python: { type: 'string' }, nproc: { type: 'integer' },
  base_sha_ok: { type: 'boolean' }, gate_sha256: { type: 'string' }, baseline_sha256: { type: 'string' },
  baseline_collected: { type: 'integer' }, baseline_skipped: { type: 'integer' },
  red_proof: { type: 'object', properties: { broken_red: { type: 'boolean' }, false_claim_red: { type: 'string', enum: ['true', 'false', 'fixture-missing', 'fixture-not-yet-delivered', 'worktree-failed', 'inner-ledger-unreadable', 'no-claim-lint-step', 'not-run'] }, digest: { type: 'string' } }, required: ['broken_red', 'false_claim_red', 'digest'] },
  integration_head_live: { type: 'string', description: '40-hex of integration/<nonce> right now, or "none"' },
  plan_merged: { type: 'boolean', description: 'plan/<nonce> at plan_sha is an ancestor of integration/<nonce>' },
  branch_heads: { type: 'array', items: { type: 'object', properties: { branch: { type: 'string' }, sha: { type: 'string' } }, required: ['branch', 'sha'] }, description: 'every tests/*-<nonce> and task/*-<nonce> branch and its head (live)' },
  merged_on_integration: { type: 'array', items: { type: 'string' }, description: 'card ids whose plan/status/<id>.json on integration/<nonce> says merged (live git ls-tree)' },
  remotes: { type: 'array', items: { type: 'string' }, description: 'git remote -v lines; MUST be empty unless owner_approvals.github_repo_url is set' },
  prior_rows: { type: 'array', items: { type: 'object', properties: { task_id: { type: 'string' }, state: { type: 'string', enum: ROW_STATE }, head_sha: { type: 'string' }, reason: { type: 'string' } }, required: ['task_id', 'state', 'head_sha', 'reason'] }, description: 'rows of args.prior_status_path (previous invocation), [] if none' },
  seen_keys: { type: 'array', items: { type: 'string' }, description: 'review dedup keys from args.prior_status_path, [] if none' },
  toolchain_status_sha256: { type: 'string', description: 'sha256 of `git -C /workspaces/agent-skills-toolchain status --porcelain -- . ":!docs/grills"` (the grill sync loop writes docs/grills legitimately)' },
  worktrees_pruned: { type: 'integer' },
}, required: ['status', 'venv_python', 'nproc', 'base_sha_ok', 'gate_sha256', 'baseline_sha256', 'baseline_collected', 'baseline_skipped', 'red_proof', 'integration_head_live', 'plan_merged', 'branch_heads', 'merged_on_integration', 'remotes', 'prior_rows', 'seen_keys', 'toolchain_status_sha256', ...COMMON_REQ] }

// ---- 9.1 CARD_INDEX (planner → script; the cards themselves are files on plan/<nonce>; the index agent returns the same shape in R1+) ----
const CARD = { type: 'object', properties: {
  id: { type: 'string' }, path: { type: 'string', description: 'plan/cards/<id>.json (review fix cards: plan/fixes/<id>.json)' }, step: { type: 'integer' },
  depends_on: { type: 'array', items: { type: 'string' } },
  files_allowed: { type: 'array', items: { type: 'string' } }, tests_allowed: { type: 'array', items: { type: 'string' } },
  new_modules: { type: 'array', items: { type: 'string' } }, deps_allowed: { type: 'array', items: { type: 'string' } },
  required_files: { type: 'array', items: { type: 'string' }, description: 'non-module files this card must deliver; new_modules ∪ required_files = the required-files manifest after this card merges (C-14)' },
  xfail_allowed: { type: 'array', items: { type: 'string' }, description: 'test ids (file::name) that may be xfail/skip; the known-bads of lens-4 §F only' },
  expected_green_tests: { type: 'array', items: { type: 'string' }, description: 'test ids (module::name) that are green on the OLD tree by design (characterisation pins, contract tests); confirm-RED exempts exactly these (C-13)' },
  tests_removed_expected: { type: 'integer' }, est_lines: { type: 'integer' }, est_minutes: { type: 'integer' },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, command: { type: 'string' }, expect: { type: 'string' },
    verification_level: { type: 'string', enum: ['local-mechanical', 'local-stub', 'staging-required', 'owner-required'] } },
    required: ['id', 'command', 'expect', 'verification_level'] } },
  size: { type: 'string', enum: ['S', 'M'] }, risk: { type: 'string', enum: ['none', 'security', 'persona', 'catalog'] },
  protected_touch: { type: 'boolean' }, bootstrap: { type: 'boolean', description: 'must be false on every card in v2 (the bootstrap profile exists only for the setup red-proof at base_sha)' },
  decision_ids: { type: 'array', items: { type: 'string' } },
  finding_ids: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, corrected_text: { type: 'string' } }, required: ['id', 'corrected_text'] } },
  apis_expected: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } } }, required: ['module', 'symbol', 'kwargs'] } },
  owner_precondition: { type: 'string', description: 'owner_approvals field that must be non-null before this card may build ("" if none)' } },
  required: ['id', 'path', 'step', 'depends_on', 'files_allowed', 'tests_allowed', 'new_modules', 'deps_allowed', 'required_files', 'xfail_allowed', 'expected_green_tests', 'tests_removed_expected', 'est_lines', 'est_minutes', 'dod', 'size', 'risk', 'protected_touch', 'bootstrap', 'decision_ids', 'finding_ids', 'apis_expected', 'owner_precondition'] }
const CARD_INDEX = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  plan_sha: { type: 'string', description: '40-hex commit on plan/<nonce> holding plan/**' },
  decisions_path: { type: 'string' }, api_ledger_path: { type: 'string' }, preverified_path: { type: 'string' },
  decisions: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, decided_value: { type: 'string' }, against_recommendation: { type: 'boolean' }, consequences: { type: 'array', items: { type: 'string' } }, dq_line: { type: 'integer' } },
    required: ['id', 'decided_value', 'against_recommendation', 'consequences', 'dq_line'] } },
  preverified: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'refuted', 'unverified'] }, corrected_claim: { type: 'string' }, level: { type: 'string', enum: LEVELS } }, required: ['id', 'verdict', 'corrected_claim', 'level'] }, description: 'plan/preverified.json rows (R1+ reads them back through the index agent so checkPlan runs in every stage, C-19)' },
  cards: { type: 'array', minItems: 1, items: CARD },
  unmapped_finding_ids: { type: 'array', items: { type: 'string' }, description: 'confirmed/partially-confirmed finding ids no card cites (must be empty or explained)' },
}, required: ['status', 'plan_sha', 'decisions_path', 'api_ledger_path', 'preverified_path', 'decisions', 'preverified', 'cards', 'unmapped_finding_ids', ...COMMON_REQ] }

// ---- 9.2 TESTS (author, modes tests and journeys) ----
const TESTS = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'reused'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string' }, tests_head: { type: 'string' },
  test_paths: { type: 'array', minItems: 1, items: { type: 'string' } },
  commits_made: { type: 'integer' },
  red_command: { type: 'string' }, red_exit_code: { type: 'integer' }, red_excerpt: { type: 'string' },
  gate_exit_code: { type: 'integer', description: 'exit code of YOUR own gate.sh --only-tests run; 0 is required and the JS refuses a nonzero one for journeys (v2.1 V-11)' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST printed by gate.sh --only-tests, or ""' },
  known_bads_xfail: { type: 'array', items: { type: 'string' } },
  mutants_suggested: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, find: { type: 'string' }, replace: { type: 'string' } }, required: ['file', 'find', 'replace'] } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'tests_head', 'test_paths', 'commits_made', 'red_command', 'red_exit_code', 'red_excerpt', 'gate_exit_code', 'gate_digest', ...COMMON_REQ] }

// ---- 9.3 BUILD (builder, modes implement and fix) ----
const BUILD = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['done', 'partial', 'failed', 'reused'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string' }, head_sha: { type: 'string' },
  commits_made: { type: 'integer' },
  changed_files: { type: 'array', items: { type: 'string' } },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string' } },
    required: ['id', 'command', 'exit_code', 'output_tail'] } },
  apis_used: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } }, ledger_ref: { type: 'string', description: 'plan/api-ledger.json entry id or libsrc path:line' } }, required: ['module', 'symbol', 'kwargs', 'ledger_ref'] } },
  gate_exit_code: { type: 'integer', description: 'advisory: your own gate.sh run at head_sha on a clean tree; the verifier re-runs it' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST of your own full gate run at head_sha ("" if not run); the verifier must reproduce it' },
  gate_profile: { type: 'string', enum: ['full', 'bootstrap'] },
  gate_steps: { type: 'array', items: GATE_STEP, description: 'the steps[] {name, exit_code} of your gate ledger (.gate/last_run.json) — compared to the verifier\'s on a digest mismatch (C-18)' },
  remaining_dod_ids: { type: 'array', items: { type: 'string' } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'head_sha', 'commits_made', 'changed_files', 'dod', 'apis_used', 'gate_exit_code', 'gate_digest', 'gate_profile', 'gate_steps', 'remaining_dod_ids', ...COMMON_REQ] }

// ---- 9.4 VERDICT (verifier; every mode; the only schema with a verdict) ----
const FINDING = { type: 'object', properties: {
  id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' },
  severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
  kind: { type: 'string', enum: ['decision-fidelity', 'scope', 'correctness', 'tests-integrity', 'security', 'secrets', 'interaction', 'omitted-obligation', 'staging-evidence'] },
  reproduction: CMD,
  corrected_claim: { type: 'string' }, fix_hint: { type: 'string' },
  files_allowed: { type: 'array', items: { type: 'string' } },
  verification_level: { type: 'string', enum: LEVELS } },
  required: ['id', 'title', 'file', 'severity', 'kind', 'reproduction', 'verification_level'] }
const VERDICT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  mode: { type: 'string', enum: ['plan', 'red', 'verify', 'refute', 'review', 'veto', 'evidence', 'preverify', 'catalog'] },
  target_id: { type: 'string', description: 'card id, finding id, wave id, "tree" or "index"' },
  sha: { type: 'string', description: 'the exact revision you read/ran (40-hex), or "none"' },
  verdict: { type: 'string', enum: ['pass', 'fail', 'unverified', 'refuted', 'holds', 'veto', 'no-veto'] },
  ledger_sha256: { type: 'string' }, ledger_head_sha: { type: 'string' }, gate_exit_code: { type: 'integer' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST of the full gate run YOU executed with the SAME pinned command ("" if none)' },
  gate_profile: { type: 'string', enum: ['full', 'bootstrap', 'none'] },
  gate_sha256_observed: { type: 'string', description: 'sha256sum of the gate.sh you executed ("" if none)' },
  gate_steps: { type: 'array', items: GATE_STEP, description: 'steps[] {name, exit_code} of YOUR gate ledger' },
  checks: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string' } }, required: ['name', 'command', 'exit_code', 'output_tail'] } },
  dod_reruns: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, exit_code: { type: 'integer' } }, required: ['id', 'exit_code'] } },
  failures: { type: 'array', items: { type: 'object', properties: { test: { type: 'string' }, first_error_line: { type: 'string' }, dod_id: { type: 'string' } }, required: ['test', 'first_error_line'] } },
  hunks_cited: { type: 'array', items: { type: 'string', description: 'path:line@sha' } },
  idiom_hits: { type: 'integer', description: 'IDIOM_HITS from the ledger of your gate run' },
  warnings_cleared: { type: 'array', items: { type: 'object', properties: { idiom: { type: 'string' }, reason: { type: 'string' } }, required: ['idiom', 'reason'] } },
  mutants: { type: 'object', properties: { written: { type: 'integer' }, killed: { type: 'integer' }, path: { type: 'string' } }, required: ['written', 'killed'] },
  revert_proof: { type: 'object', properties: { observed: { type: 'string', enum: ['red', 'green', 'unrunnable', 'not-run'] }, command: { type: 'string' } }, required: ['observed', 'command'] },
  diff_stats: { type: 'object', properties: { files: { type: 'integer' }, insertions: { type: 'integer' }, deletions: { type: 'integer' }, moves_only: { type: 'boolean' } }, required: ['files', 'insertions', 'deletions'], description: 'verify: copy the LEDGER_DIFF_STATS line of your gate run (required; the script fails closed without it, C-25)' },
  apicheck_unresolvable: { type: 'array', items: { type: 'string' }, description: 'verify: apicheck_unresolvable[] of your ledgers (symbols needing torch with no wheel source; recorded, never a failure — C-16)' },
  findings: { type: 'array', items: FINDING },
  probes_used: { type: 'array', items: { type: 'string' }, description: 'review/veto: the commands or angles you used (fed to the inversion mandate)' },
  remotes: { type: 'array', items: { type: 'string' }, description: 'clean-gate/evidence: git remote -v lines of the build repo' },
  strongest_disagreement: { type: 'string', description: 'required even when the verdict is pass/holds' },
  judge_rail: { type: 'string', enum: ['claude-fresh'] },
}, required: ['status', 'mode', 'target_id', 'sha', 'verdict', 'ledger_sha256', 'ledger_head_sha', 'gate_exit_code', 'gate_digest', 'gate_profile', 'gate_sha256_observed', 'gate_steps', 'checks', 'dod_reruns', 'failures', 'hunks_cited', 'idiom_hits', 'warnings_cleared', 'mutants', 'revert_proof', 'findings', 'probes_used', 'strongest_disagreement', ...COMMON_REQ] }

// ---- 9.5 MERGE (integrator; modes merge, conflict, ff, revert, clean-gate, fixcards) ----
const MERGE = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['merged', 'conflict', 'gate-red', 'reverted', 'missing-ref', 'already-merged', 'written', 'ok', 'failed'] },
  mode: { type: 'string', enum: ['merge', 'conflict', 'ff', 'revert', 'clean-gate', 'fixcards'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  before_sha: { type: 'string' }, head_sha: { type: 'string' },
  merge_sha: { type: 'string', description: 'merge/ff/conflict: the merge commit itself (before the status commit) — the revert target (C-12); "" otherwise' },
  ledger_sha256: { type: 'string' }, gate_digest: { type: 'string' }, gate_exit_code: { type: 'integer' },
  gate_sha256_observed: { type: 'string' },
  cherry_unmerged: { type: 'array', items: { type: 'string' } }, patch_ids_missing: { type: 'array', items: { type: 'string' } },
  conflicts: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, ours: { type: 'string' }, theirs: { type: 'string' } }, required: ['file', 'ours', 'theirs'] } },
  bundle_path: { type: 'string' }, bundle_bytes: { type: 'integer' },
  journeys: { type: 'object', properties: { collected: { type: 'integer' }, failed: { type: 'integer' }, skipped_needs: { type: 'array', items: { type: 'string' } } }, required: ['collected', 'failed', 'skipped_needs'], description: 'from the ledger; {0,0,[]} when the gate ran without --journeys' },
  self_test: { type: 'object', properties: { broken_red: { type: 'boolean' }, false_claim_red: { type: 'string', enum: ['true', 'false', 'fixture-missing', 'fixture-not-yet-delivered', 'worktree-failed', 'inner-ledger-unreadable', 'no-claim-lint-step', 'not-run'] } }, required: ['broken_red', 'false_claim_red'], description: 'from the ledger; {false, "not-run"} when the gate ran without --self-test' },
  files_written: { type: 'array', items: { type: 'string' }, description: 'fixcards: the plan/fixes/<id>.json paths committed' },
  remotes: { type: 'array', items: { type: 'string' } },
  branch_count: { type: 'integer' },
  toolchain_status_sha256: { type: 'string' },
}, required: ['status', 'mode', 'head_sha', 'merge_sha', 'ledger_sha256', 'gate_digest', 'gate_exit_code', 'gate_sha256_observed', 'cherry_unmerged', 'patch_ids_missing', 'conflicts', 'journeys', 'self_test', 'files_written', 'remotes', ...COMMON_REQ] }

// ---- 9.6 REPORT (synthesizer; rows are checked against the script's ledger) ----
const REPORT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  report_path: { type: 'string' }, report_bytes: { type: 'integer' }, status_json_path: { type: 'string' },
  rows: { type: 'array', items: { type: 'object', properties: {
    task_id: { type: 'string' },
    state: { type: 'string', enum: ROW_STATE },
    reason: { type: 'string' }, next: { type: 'string' },
    head_sha: { type: 'string' }, dod_done: { type: 'integer' }, dod_total: { type: 'integer' }, dod_deferred: { type: 'integer' } },
    required: ['task_id', 'state', 'reason', 'next', 'head_sha', 'dod_done', 'dod_total', 'dod_deferred'] } },
  owner_actions: { type: 'array', items: { type: 'string' } },
  what_would_most_improve_confidence: { type: 'string' },
}, required: ['status', 'report_path', 'report_bytes', 'status_json_path', 'rows', 'owner_actions', 'what_would_most_improve_confidence', ...COMMON_REQ] }
```

Script-side semantic rules (F-46), all in code (§13): `taskDone()` = the twelve conditions of §5 — **condition 10 fails closed when `diff_stats` is absent (C-25) and condition 12 requires a `ledger_ref` on every `apis_used` entry**; `refute:holds` ⇒ `findings[0].reproduction` present **and its `exit_code` non-zero on the defect — a "holds" with an exit-0 or missing reproduction is ignored and logged (C-27)**; `review`/`veto` findings without a reproduction or at `unverified` are logged, never queued; `veto` needs a reproduction; `MERGE` is accepted only through `mergeOk()` (status, 40-hex head, **a real `merge_sha` (C-12)**, exit 0, 64-hex digest, pinned gate, no lost hunks — and an `already-merged` claim without that evidence is typed `already-merged-unproven` (C-20)); **v1's `RECEIPT_RE` rule is dropped in v2 (C-23): it nulled returns whose `notes` quoted a central design phrase, so a receipt-shaped fragment is now only logged — wording is not the anti-theatre signal, the two-execution digest equality is**; a `verify`-pair digest mismatch is typed as `digest_mismatch` carrying both ledgers' step lists (C-18); every string field that reaches a prompt is capped and secret-redacted.

---

## 10. Replay/resume, null-result, safeguard-kill and concurrency handling

### 10.1 Replay and resume (F-43, F-47, T-14..T-16, S-18; J2 gaps 1, 3, 6, 7; J1 CG7/CG8; C-8, C-22)

- **Two resume modes, chosen by `args.resume_mode`.** `git` (default): every invocation is a fresh workflow run; the setup prompt carries `launched_at`, so the probe is live; correctness and most of the speed come from git-state idempotency (author/builder `status:'reused'` on an existing green branch; integrator `already-merged` **with evidence** — the head must be unchanged, the gate exit 0 with its digest and the pinned gate sha, cherry/patch-id assertions empty (C-20); merged set from `plan/status/*.json` on the integration branch AND `git ls-tree`). `cache` (`{scriptPath, resumeFromRunId}`): allowed only after the smoke run's settling experiment (§2.0 step 7) showed that unchanged replays hit and a non-prompt knob change still hits; the setup prompt then omits `launched_at`. **Correctness never depends on the cache** (C-R): a stale cached sha is caught by `missing-ref` at merge time and re-driven with a `redrive:` suffix; `integration_sha_at_launch` is checked by the script against the live head (throws `stale-launch-args`).
- **Prior rows are detail, never truth (C-8).** On resume, a prior `parked` row is re-driven automatically when its reason matches `RETRYABLE_RE` (`agent-null`, `threw`, `timeout-or-dialog`, `not_attempted:…`, `starved:…`, `integration:not-merged:null`, `fixcards-unavailable`) — nobody ever judged that work; it stays parked otherwise and is re-driven only when named in `args.retry_parked` (the checkpoint's `retry_parked_suggested` computes exactly this list: parked rows whose reason is retryable). `not_attempted`, `blocked_on_owner`, `dropped_null` and `reverted` prior rows are never adopted — they are re-evaluated live. `last_clean_gate` seeds `lastClean` only when its head equals the live integration head.
- **Timeout ↔ replay divergence (J2 gap 1).** A timed-out call may still journal a result; on a cache resume it would return instantly and the retry branch would be skipped. Mechanism: any `timeout-or-dialog` receipt sets `REPLAY_RISK`, and `next_args.resume_mode` becomes `'git'` for the following invocation.
- **Completion-order call sequence (J1 CG8).** Barrier waves keep control flow independent of completion order at the wave level; inside a wave the two chains' `agent()` calls still interleave by completion — harmless in `git` mode, one more reason `cache` mode is opt-in.
- Every prompt is a pure function of `args` and prior results; arrays sorted by id before `JSON.stringify`; the ledger summary in the synthesizer prompt is sorted by `(role, mode, id, attempt)` (J2 gap 11); the integration head appears in every code-reading prompt; no timestamps except `launched_at` in the git-mode setup prompt.
- **Lifetime cap.** Replayed calls are assumed to count (J2 gap 3); `max_agents_this_run` slices with a per-chain reservation of 7 keep every invocation ≤ 110 agents at cap 2; in `git` mode each invocation is its own workflow run.

### 10.2 Null results (F-41, T-17, D-21; C-11, C-7)

Every `agent()` goes through `run()`: ledger row for every call including `null`/`threw`/`timeout-or-dialog`; one narrower retry (`attempt: 2` + `NARROW`); then a typed `{status:'null', reason}`. Downstream typing is per consumer, never a global revert: **a clean-gate null or malformed return is `gate-unavailable`** — the three-way type is `pass | fail | gate-unavailable` and only a genuine `fail` may revert (a wrong head, a missing digest, a contradictory self-test or a malformed shape is `unavailable`, never a revert, C-11); **a veto null is `veto-unavailable`** (not satisfied — fail closed); **an evidence null is `evidence-unavailable`**. A `threw` receipt whose detail matches the budget ceiling sets `HALT='budget-exhausted'` immediately (no retry, no fan-out of instant throws — J2 gap 8). Barrier results are never `.filter(Boolean)`-ed without a counted log line (lens drops, refute chain drops, wave chain drops). `pipeline` stage throws are caught inside `buildTask` and typed `threw`. **The synthesizer is exempt from the HALT branch and from the budget-reserve guard** (C-7/F-45: the reserve exists to pay for it, so it runs after every HALT and even on an exhausted budget; the invocation agent cap still applies to it).

### 10.3 Safeguard kills (F-31, F-42)

Hardening cards 09a/09b/09c and the persona card carry reading lists ≤ 6 files and defensive framing; their verifiers run at `xhigh`; builders commit per coherent step; the retry prompt begins with the salvage rule; two nulls → `blocked:'agent-null:<role>'`. `model` is never overridden (the session model is the model that succeeded on retry in the observed run); if the orchestrator ever launches on a different session model, adding `model` means editing the script AND the `meta.phases` Build entry (J2 gap 10) — a checklist item, not an arg.

### 10.4 Concurrency and timers (F-44, T-7, T-8; J2 gaps 2, 4, 9)

- `args.wave_size ≤ args.cap` is asserted at script start and the setup probe's `nproc` must give the same cap (`cap-mismatch` throws — J2 gap 9). Each chain is strictly serial, and **the wave itself is recomputed from the live status map after every wave** (C-5: a card whose dependency parked is never scheduled), so a wave never enqueues more than `wave_size ≤ cap` agents: **no FIFO queueing in Build**. Where a barrier does exceed the cap (3 review lenses at cap 2; the R0 trio + pre-verifiers), `tmo(mode, enqueued)` multiplies the base timeout by `ceil(enqueued / cap)` so queue wait cannot fire a timer on an agent that has not started (J2 gap 2).
- Base timeouts: author 25 min, red 10, build 50, fix 40, verify 30 (mutants + revert-proof added), merge 20, conflict 30, clean 25, journeys 25, review 30, refute 15, veto 25, plan 40, setup 30, synth 15, synthfix 10, fixcards 10.
- **Permission dialogs vs hangs (J2 gap 4).** The script cannot see a dialog. Mechanism + owner checkpoint: the smoke run (one card, owner attending) records the permission inventory into the allow-list before any full invocation; the runbook requires the owner to stay attached during the first wave of every invocation; a `timeout` receipt is logged as `timeout-or-dialog` and never retried more than once.
- The script logs per wave: cards built/blocked, merges with their merge shas, the stop reason, and the remaining waves.

### 10.5 Outward actions, toolchain and remotes (F-1, F-35; C-17)

`assertCommon` on every return: `repo_toplevel` must be the build repo or a path under `<repo>-wt/` (prefix test, J1 D1) and `git_common_dir` must be `<repo>/.git`; a non-empty `outward_actions_taken` sets `HALT` (every later `budgetOk()` is false; the synthesizer still runs; the checkpoint is `failed` with `halt`); the setup probe and every clean gate report `git remote -v` (non-empty without approval → `HALT`) and the toolchain status hash — computed as `git status --porcelain -- . ':!docs/grills'` on the toolchain repo, because the owner's grill sync loop legitimately writes `docs/grills` every five minutes and that is not a mutation of the executed fleet (C-17); a mismatch → `HALT`.

### 10.6 Secrets in structured returns (J1 CG3)

`redact()` walks every string in a return (depth ≤ 6) with `SECRET_RE`, replaces matches with `[REDACTED]`, logs the fact (never the value) and marks the return; `taskDone()` condition 11 blocks the card (reason `secret-shaped-output`, no fixer is launched); the fixer never receives an unredacted string; the synthesizer prompt carries only sorted ledger summaries and script-computed rows. The prompts additionally warn that dummy credentials must not match the secret regex (`TESTTOKEN-…`, never `hf_`/`ghp_`/`sk-ant-` with 20+ characters — C-32), so a fixture cannot park its own card.

---

## 11. Budget and effort plan by role; estimated agent counts and wall-clock (recomputed for v2)

| Role · mode | effort | timeout (base) | est. duration (UNVERIFIED extrapolation) |
|---|---|---|---|
| integrator · setup (+ live probe) | medium | 30 min | 10-15 min (first invocation), 3-5 min after |
| verifier · preverify (×5, R0) | medium | 20 min × queue factor | 6-10 min each |
| planner · api-ledger / verifier · catalog (R0) | medium / low | 25 / 15 min | 10-15 / 5-8 min |
| planner · plan (+ repair re-run) | high | 40 min | 15-25 min |
| verifier · plan / index | medium / low | 20 / 10 min | 8-10 / 2 min |
| author · tests / journeys | medium | 25 min | 8-12 min |
| verifier · red | low | 10 min | 3-4 min |
| builder · implement / fix | high | 50 / 40 min | 15-25 (S) · 25-40 (M) / 10-20 min |
| verifier · verify (gate + DoD re-runs + mutants + revert-proof + apicheck-extended + diff_stats) | medium (xhigh on security) | 30 min | 10-14 min |
| integrator · merge / ff / revert | low | 20 / 15 / 15 min | 3-5 min |
| integrator · conflict | high | 30 min | 10-15 min |
| integrator · clean-gate (`--self-test --journeys`) | low | 25 min | 8-11 min |
| integrator · fixcards | low | 10 min | 1-2 min |
| verifier · review (lens) / refute / veto | high / medium / xhigh | 30 / 15 / 25 min | 12-15 / 4-6 / 8-10 min |
| synthesizer · report / fix | low | 15 / 10 min | 5 / 2 min |

**Agent count (22 cards; fix mix re-derived honestly in v2.1 (V-10): 5 base + 0.4×2 (one fix) + 0.15×4 (two fixes) + 0.1×2 (author re-drive) + 0.05×1 (null retries) ⇒ ≈ 6.65 agents per card; the v2 confirm-RED two-execution rule and author re-drives (C-26) are inside that mix):** R0 = setup 1 + pre-verify 5 + api-ledger 1 + catalog 1 + planner 1 + plan check 1 + synth 1 = **11**, plus a repair re-run (+2: planner + plan check) when the plan needs repair. R1 = cards 22 × 6.65 ≈ 146 · merges 22 + conflicts ~3 + ff ~3 = 28 · clean gates ≈ 13 waves + ≈ 2 review pre-checks (C-10: only when the last clean gate is not a pass at the current head) ≈ 15 · journeys authors ≈ 6 + their merges 6 · setup + index per invocation ≈ 4 × 2 = 8 · review 3 rounds × 3 lenses = 9 · refuters ≈ 13 · fixcards integrator calls ≈ 3 · fix cards ≈ 7 × 6.65 ≈ 47 + merges 7 + clean gates ≈ 8 · veto 3 · synth ≈ 4 + fix ≤ 4 → **≈ 296 (range 280-315)**. R2 ≈ 27-32, R3 ≈ 9. Total across all runs ≈ **335-350**; every invocation ≤ 110 agents (slice) at cap 2 — far inside the 1000 cap even if replays count. Versus A3's ≈ 240: +≈ 35 for the R0 trio + pre-verifiers, journeys per seam wave, self-tests, the synth-fix probe, fixcards calls and review pre-check clean gates.

**Wall-clock (per-card chain without a fix ≈ author 10 + red 3.5 + builder 20 + verify 12 ≈ 46 min; with one fix ≈ 78 min; wave ≈ slowest chain + serial merges × 4 min + clean gate 10 min + journeys 12 min on the seam waves):**

| | cap 2 (this box) | cap 14 (after the resize) |
|---|---|---|
| Waves | ≈ 13 (22 cards, width 2, runtime DAG) | ≈ 10 (DAG depth; width 1-4 per level) |
| Build + integrate | ≈ 13 × ≈ 95-100 min ≈ 21-22 h (serial merges + clean gate + seam-wave journeys; v2.1 V-10 re-derivation) | ≈ 10 × ≈ 100 min ≈ 16-17 h (the slowest chain in a wide wave + more merges) |
| Review loop (3 rounds, ~7 fix cards + fixcards commits) | ≈ 5-6 h | ≈ 3 h |
| Setup + plan + synth (per invocation) | ≈ 2 h over 4-5 invocations | ≈ 1.5 h over 2-3 invocations |
| **Total R1** | **≈ 28-29 h, run as 5-7 resumable invocations (`max_agents_this_run` 110 ≈ 5.5 h each; v2.1 V-10: one more invocation than the v2 estimate) with owner stops at fixture #1, the boundary fixture and the worker decision** | **≈ 20-22 h in 2-3 invocations** (the same owner stops apply) |

Honest reading: versus A3 the grafts add ≈ 4-5 h at cap 2 (mandatory mutants + revert-proof per card, `--self-test` on every clean gate, journeys per seam wave, the pre-verification trio, the review pre-check clean gates, fixcards commits, author re-drives) and the fixture-#1 precondition adds one owner stop that A3 did not have. These remain UNVERIFIED extrapolations from A3's observed per-role durations — the v2 drive runs a fake harness and yields no timing evidence. The cap buys width, not depth: the DAG is 9-10 deep and the API lane cannot be deferred (G-3), so the critical path is the plan's. `budget.total` may be `null`; counters are the first guard, the reserve the second, `HALT` the third; **the synthesizer always runs** (it is exempt from the reserve guard precisely so the reserve can be spent on it).

---

## 12. COVERAGE MATRIX (all 136 v1 rows kept, mechanisms updated where v2 changed them; + §12.7 for the v2 mechanisms)

Legend for "phase": **P0** orchestrator pre-flight · **R0** plan · **R1** build inner loop · **G** `gate.sh` · **I** integration · **W** whole-tree review loop · **S** synthesizer · **X** script invariant (JS) · **O** owner checkpoint. ★ = changed from A3 because a judge reproduced a defect or listed a graft; **v2:** marks a cell rewritten by this revision (the gap id C-n refers to Appendix B).

### 12.1 Failure modes F-1..F-47 (research-4)

| id | Guard (mechanism) | Phase |
|---|---|---|
| F-1 wrong repo (cwd) | `PREAMBLE`; every git command `git -C`; no `isolation`; ★ `assertCommon`: `repo_toplevel === R ∨ startsWith(R + '-wt/')` AND `git_common_dir === R/.git` (prefix test + store identity, J1 D1); toolchain status hash (v2: computed with `docs/grills` excluded, C-17) asserted by setup and every clean gate → `HALT` | X, G, I |
| F-2 volatile build path | JS refuses `/tmp/*` and the toolchain path for `build_repo/tools_dir/libsrc/venv`; `libsrc` copied durable; ★ incremental bundles `<prev>..integration/<n>` (v2: into `/workspaces/space-build-bundles/<nonce>/`, never the grill tree, C-17) with `bundle_bytes` | P0, I |
| F-3 wrong base / snapshot mutated | full `base_sha`; setup asserts the clone's first commit; snapshots `chmod -R a-w`; base named in every card prompt | P0, R0, X |
| F-4 foreign CLAUDE.md | constant `PREAMBLE`; `AGENTS.md` written by the planner and named in every prompt | X, R0 |
| F-5 per-agent bootstrap | one idempotent setup; `gate.sh` refuses any other interpreter and a missing tool; `installed_packages` must be `[]` (card nulled otherwise); **v2: the venv is created once at P0 and every prompt says "it EXISTS — never create it, never install" (C-31)** | P0, G, X |
| F-6 "ask the owner" unattended | `args.owner_approvals` is data; ★ `owner_precondition` cards are typed `blocked_on_owner` **with `field`/`why`/`next`/`severity` on every row (C-22)**; every action computed in JS; never retried | X, S, **O** |
| F-7 secrets leak | P0 regex pre-scan; trigger message without secrets; `env -i` + `CANARY_SECRET`; ★ secrets step over range + commit messages + the gate's own logs with a constant summary; ★ `redact()` on every structured return; journal export scanned before copying; **v2: prompts fix the `TESTTOKEN-` dummy-credential convention (C-32)** | P0, G, X, S |
| F-8 hallucinated APIs | ★ R0 `planner mode:'api-ledger'` (≥ 30 symbols with libsrc anchors + `known_bad[]` regexes); `apis_expected` → gate apicheck imports each symbol from the pinned wheels (v2: import-first, else ast-parse of the wheel SOURCE under `--libsrc`; an unlocatable symbol is recorded `unresolvable-needs-torch` and never RED, C-16); ★ known-bad regexes RED in apicheck; two-tier idiom lint | R0, G |
| F-9 recommendation vs decision | ★ decision sheet in the design (§4.0) + planner rows with `against_recommendation`/`dq_line`; JS asserts the five ids are marked — **v2: `checkPlan()` runs in every stage, so a plan that loses its marks is refused again in R1 (C-19)**; owner C0; review lens `decision-fidelity` | R0, X, O, W |
| F-10 CORRECTED line ignored | ★ every cited finding carries `corrected_text` (JS throws otherwise); §4.2 inlines the ids per card; ★ `IDIOM_HITS` in the ledger and `warnings_cleared.length ≥ idiom_hits` in `taskDone()`; blocking idiom tier for decided values — **v2: scoped to `--lint-base..HEAD` so a fixed idiom is not re-counted (C-15)** | R0, X, G, R1 |
| F-11 UNVERIFIED findings / stale `file:line` | ★ `pipeline(args.unverified_finding_ids, verifier mode:'preverify')` with an executed, mechanically different probe before the planner; `plan/preverified.json`; a REFUTED id cannot be cited (JS — **v2: enforced by `checkPlan()` in every stage, C-19**); cards locate by symbol | R0, X |
| F-12 verification theater | ★ two-execution equality: `v.gate_digest === b.gate_digest` (timestamp-free canonical digest) at the same sha; gate pinned by sha256 (+ `tools/gate.pin`); verifiers run the gate themselves; pytest exit 5 red; `staging-required` never `pass`; **v2: confirm-RED is the same equality — `red.gate_digest === author.gate_digest` (C-29)** | G, X |
| F-13 monolithic items | `S/M` only (`L` throws at validation); 22 cards; `changed ≤ 2 × est_lines` in `taskDone()` — **v2: fail-closed when `diff_stats` is missing (C-25) and `est_lines` validated against the size class (C-13)**; `partial` is not built | R0, X |
| F-14 dependency order / collisions | `topoOrder` + ★ `rankCards` + `waves` with disjoint write sets (never throws; unschedulable typed); serial integration in **(−rank, id)** order (v2: C-24 — not raw id order, so the deeper subtree integrates first) with a gate after each merge; **v2: `readyWave()` recomputed from the LIVE status map before every wave — a card whose dependency parked/blocked/never merged is never scheduled (C-5)** | X, I |
| F-15 context loss between stages | carriers are files + git (`plan/**` merged into the integration branch so every worktree has the cards); typed returns; fixer gets typed failures only — **v2: a digest mismatch additionally carries both ledgers' step lists (`digest_mismatch`, C-18)** | X, R1 |
| F-16 scope creep | gate step 8: hunks outside `files_allowed ∪ new_modules`, any hunk under `plan/`, requirement lines outside `deps_allowed` → RED; `changed ≤ 2 × est_lines` (fail-closed, C-25); ship-but-flag defaults in `out_of_scope`; review lens `scope`; **v2: a protected-path hunk is legal only when the card's own manifest declares it (the ownership rule, C-21)** | G, X, W |
| F-17 persona boundary | ★ history-free clone for the persona card's worktrees (mechanical, not a prompt rule); ★ owner-generated shingle-hash fixture (v2: generated with card 01's `tools/make_boundary_fixture.py`, copied by an explicit FIXTURE COPY STEP, sha-pinned by `--boundary-sha256` and the owner field `persona_boundary_fixture_sha256`, C-21); absence test protected and in the required-files manifest; `AUTHORITY` forbids `git log/show` of `system_prompt.py`; synthesizer reports the result | R1, G, X, S, **O** |
| F-18 tests weakened/deleted | ★ oracle lock + reset (any M/D under `tests/` since the oracle → RED; `git checkout <oracle> -- tests/`); ★ author-range tamper rules in `--only-tests` (M/D outside `tests_allowed`, assertion-count drop, markers outside `xfail_allowed`); ★ collected floor vs the pinned baseline; ★ skip/xfail SET rule; test-detection idioms → RED; ★ builder-added tests with skip/xfail/`except: pass`/`sys.exit(0)` → RED; DoD commands with `-k/--deselect/…` rejected; mutants all killed; revert-proof; **v2: confirm-RED requires RED for everything except exactly the card's `expected_green_tests` — an extra green new test is RED, a listed-not-green one is RED, on BOTH executions (C-13)** | G, X |
| F-19 over-claiming commits | ruff F821/F811 + import smoke; claim lint per commit (`Claim-Waiver` counted **per `Card:` trailer**, v2 C-3/C-13); `dod[]` exit codes on **both** sides for every local DoD id; ★ `dod.length === card.dod.length`; synthesizer rows carry `dod_done/dod_total` | G, X, S |
| F-20 mocks testing the mock | conformance suite over `fake`/`recorded-*` with `provenance` (recorded rows counted as skipped-needs-owner); ★ mutants mandatory and all killed; ★ revert-proof red (**v2: including builder-added `tests/unit/*`, C-28**); ★ fixture #1 is a precondition of card 04 | R1, G, X, **O** |
| F-21 line-ending drift | card 01 `.gitattributes` + `Renormalize-Only: yes` commit (whitespace-only, checked); gate eol step; `apply_patch` EOL fix (09c) | R1, G |
| F-22 large files / LFS / junk | gate: LFS empty, blob cap 5 MB in range, junk paths incl. `.env*` | G |
| F-23 3.14 vs 3.12 drift | gate runs only under the 3.12 venv; `--target-version py312`; locks produced under 3.12; ★ R2 evidence reader compares `build-log.txt` resolution with `requirements.lock` (3.12.12 vs 3.12.3 caught there); Q6 | G, R1, R2, **O** |
| F-24 README / constants / claims | `tools/render_readme.py --check` (required after 13a); `tests/test_constants_pin.py` with a row per ship-but-flag flag — **v2: the pins are green within card 01's own run because card 01 ships the `config.py` skeleton and lists the pins as `expected_green_tests` (C-13)**; claim lint | G, R1 |
| F-25 catalog provenance | ★ R0 catalog agent saves raw Hub reads (`unresolved` after 3 tries, never a remembered value) incl. `has_visual_tensors`; gate step: 40-hex revision, provenance files exist, `admission` enum, `has_visual_tensors` on local entries; `tests/test_catalog_policy.py`; **v2: card 13a copies `evidence/catalog/` into the repo so the gate and CI can read it (C-34)** | R0, G, R1 |
| F-26 leaked servers / foreground launch | harness picks a free port, `prevent_thread_lock=True`, `try/finally` teardown; `/healthz` sha asserted; ★ gate kills only listeners whose cwd is the current tree; `AUTHORITY` | R1, G, X |
| F-27 infinite/oscillating fix loops | `MAX_AUTHOR`, `MAX_BUILD`, two-strikes, oscillation, `MAX_ROUNDS`, dry 2, `seen` (★ persisted across invocations), budget/agent slice, `HALT`; every exhaustion typed; **v2: the failure fingerprint is never empty, so two-strikes always has teeth (C-18); starvation is typed `not_attempted` and auto-retried on resume, never a permanent park (C-8)** | X |
| F-28 fixing the gate | ★ gate pinned by `args.gate_sha256` (self-check exit 66; repo copy compared **and `tools/gate.pin` present**); ★ baseline pinned; `plan/` immutable **except `plan/status/` (integrator) and `plan/fixes/` (`fixcards` mode only, C-3)**; protected paths only via the ownership rule (C-21); ★ `--self-test` red-proofs on every clean gate — **v2: the false-claim fixture is generated by the gate itself with a lint-matching commit message, so the proof is real (C-2)**; `--profile bootstrap` recorded and rejected for every other card | G, X |
| F-29 flaky / network tests | suite twice with identical sorted outcomes; `--disable-socket --allow-hosts=127.0.0.1`; blackhole proxy; `HF_HUB_OFFLINE`; `tests/live/` excluded by `pytest.ini` | G |
| F-30 critic captured by self-report | verifiers receive card + diff range + gate, never the builder's narrative or digest; must run `gate.sh` (`checks[]` regex) and cite hunks; `strongest_disagreement` required; ★ digest equality cannot be copied because the verifier never sees the builder's value; **v2: receipt-shaped fragments in `notes` are logged, not nulled (C-23) — the equality, not wording, is the signal** | R1, X |
| F-31 safeguard kill on security code | 09a/09b/09c ≤ 6-file reading lists; defensive framing; null → one narrower retry → typed park | R0, X |
| F-32 merge conflicts "pick one side" | integrator aborts on conflict; fresh `mode:'conflict'` in a **detached** worktree (`worktree add --detach`, C-30), re-gated; `mergeOk()` asserts cherry empty + patch-ids present + exit 0 + digest + pinned gate **+ a real `merge_sha` (C-12)** | I, X |
| F-33 worktree lifecycle | nonce in names; creator removes its worktree after verifying the head; setup prunes merged worktrees; `status:'reused'` on an existing green branch | R1, I |
| F-34 green on branch, red merged | gate after every merge; red → immediate revert **of the recorded `merge_sha`, never HEAD (C-12)** (`reverted` typed, result checked); clean gate per wave with ★ checked revert and `INTEG_DIRTY` on failure; **v2: a wave that merged nothing and whose last clean gate passed at this head is skipped (C-38)** | I, X |
| F-35 outward actions | `AUTHORITY`; `outward_actions_taken` → ★ `HALT` (works inside `parallel`/`pipeline` too — A3's throw was swallowed there); ★ `git remote -v` from setup and every clean gate (non-empty without approval → `HALT`); checkpoint kinds JS-computed; owner Hub post-checks in the runbook; no push ever | X, P0, S, **O** |
| F-36 harness burns money | card 12 defaults `--backend fake --dry-run`; `--i-accept-cost` + owner env var; `max_retries=0`; zero-call test; `max_retries=[1-9]` idiom; budgets in `owner_approvals`; the owner runs the real harness (C2 `run-harness`) | R1, G, **O** |
| F-37 staging-only "verified" | `verification_level` enum everywhere; ★ `STAGING_RE` applied in JS at validation and at return time; `deferred` lines in the checkpoint; R2 reads CI files only; **v2: an apicheck symbol that cannot be resolved without torch is recorded `unresolvable-needs-torch` and never fails (C-16)** | X, S, **O** |
| F-38 other agent resumes pushing | ★ `owner_approvals.production_space_head === base_sha` (or `adopted_delta_sha`) is a required field of `promote-production` (blocked otherwise); **v2: `promote-production` additionally requires `status === 'ready'`, which is false while a confirmed critical/high staging finding stands (C-6)**; owner checklist (stop notice, scheduled tasks, token rotation, NF4 secrets) | X, S, **O** |
| F-39 flaky fetch → fabricated values | catalog agent: 3 tries then `unresolved`; provenance files must exist (gate); estimator constants marked UNVERIFIED in config comments; `TODO(owner-verify)` never a number | R0, G |
| F-40 synthesizer summarises phantom work | rows computed in JS; ★ when the synthesizer's rows differ, `synthesizer mode:'fix'` rewrites the on-disk rows from the script's table; `rows_consistent` in the checkpoint; ledger summary sorted; **v2: the synthesizer runs after every HALT and even on an exhausted budget (C-7)** | S, X |
| F-41 null contract mishandled | `run()` types every `null`/`threw`/`timeout`; one narrower retry; ★ clean-gate null = `gate-unavailable` (no revert) — **v2: the three-way type `pass | fail | gate-unavailable` also covers malformed shapes, wrong heads and an exit 0 contradicted by the self-test (C-11)**; ★ veto null = `veto-unavailable` (not satisfied); ★ evidence null = `evidence-unavailable`; **★ v2: `fixcards` unavailable is typed `fixcards-unavailable` and auto-retried, never silent (C-3/C-8)**; drops counted at every barrier | X |
| F-42 mid-task kill | commit per step; salvage rule; gate pre-step (index.lock; scoped listener kill); two nulls → park | R1, G, X |
| F-43 stale resume cache | ★ resume modes (`git` default); ★ setup probe live (`launched_at`) → `stale-launch-args` throws; merged set from git; `missing-ref` → live re-drive with `redrive:` suffix; `attempt: 2` on retries; `REPLAY_RISK` forces `git` after any timeout; **v2: `last_clean_gate` seeds `lastClean` only at the same head (C-10) and retryable parks are re-driven automatically (C-8)** | X, P0 |
| F-44 cap-2 wall-clock / host stops | ★ `max_agents_this_run` slices with per-chain reservation; resumable invocations from git; waves never exceed the cap; owner keeps a client attached; idle timeout **O**; **v2: cards cut by the slice are `not_attempted` (retryable), never parked (C-8)** | X, **O** |
| F-45 budget exhaustion / agent cap | counters first; `RESERVE`; agent slice; ★ budget-throw → `HALT` (no fan-out); synthesizer always runs — **v2: `budgetOk(label, exemptFromHalt)`; the exemption is the synthesizer's, because the reserve exists to pay for it (C-7)** | X |
| F-46 schema-valid-but-empty | `minItems` on evidence arrays; ★ no unverified schema keywords — caps and shapes enforced in JS; twelve-condition `taskDone()` (**v2: condition 10 fail-closed on missing diff_stats, C-25**); `mergeOk()`; smoke run exercises every schema | X, P0 |
| F-47 script-level bugs | `meta` pure literal; every phase title called; no `Date.now/Math.random/new Date()`; ★ `node --check` + a fake-harness drive of every stage before launch — **v2.1: `drive.mjs`, 41 scenarios / 107 assertions including the critic's 21 adapted scenarios and S38-S41, all passing (Appendices C/D)**; `buildTask` never throws; synthesizer outside the main try | X, P0 |

### 12.2 Doctrine anti-patterns AP-1..AP-17 (research-1 §4)

| id | Guard | Phase |
|---|---|---|
| AP-1 receipt-as-result | `status` enum everywhere; `run()` types nulls; ★ **v2: `RECEIPT_RE` is dropped (C-23) — it nulled returns whose notes quoted a central design phrase; a receipt-shaped fragment is logged only, and the two-execution digest equality is the anti-theatre signal** | X |
| AP-2 digest theatre | the artifact is the branch + `.gate/last_run.digest` + `plan/status/<id>.json`; verifiers read `git diff` and re-run the gate | R1, S |
| AP-3 evidence-tag theatre | ★ the two signals are two executions of the same deterministic gate by two fresh agents, compared by value — **v2: also on confirm-RED (C-29)**; plus DoD re-runs on both sides | G, X |
| AP-4 silent-in-both detector | ★ `--self-test` on every clean gate (RED on `f88b120`; RED from the claim-lint step on the false-claim fixture — **v2: the fixture is generated by the gate with a lint-matching commit message so the claims are real, C-2**); confirm-RED; mutants; revert-proof | G |
| AP-5 Goodhart-green | tests before code; oracle lock + reset; `-k/--deselect` rejected in DoD commands; skip/xfail set rule; mutants; **v2: `expected_green_tests` pinned both ways (C-13)** | R1, G, X |
| AP-6 self-certification | distinct fresh `agent()` per role; builder returns evidence; only JS says done/satisfied; veto-only judge, fail closed on drop | X |
| AP-7 the grind | two-strikes → park (v2: the fingerprint is never empty, C-18); oscillation | X |
| AP-8 fat barrier, no timeout | pipeline per card; barriers only at wave end and review lenses; ★ timeouts sized by queue depth | X |
| AP-9 over-broad `required[]` | `required` is the floor; prose capped in JS | X |
| AP-10 mid-run contract edits | `plan_sha` frozen at C0; ★ `plan/` immutable during a run — **v2: the two declared exceptions are `plan/status/` (integrator) and `plan/fixes/` (`fixcards` only, C-3)**; schemas top-level consts | R0, G, X |
| AP-11 unbounded loop | `MAX_ROUNDS`, dry, `seen` (persisted), reserve, slice, `HALT`; every stop reason logged — **v2: including `tree-incomplete` (C-5), `blocked-on-owner:staging-evidence` (C-6), `plan-needs-repair` (C-19)** | X |
| AP-12 negative instructions in the implementer prompt | the builder prompt carries the card; every "do not" is a gate step | R1, G |
| AP-13 LLM doing mechanical comparison | DAG, rank, waves, dedup, fingerprints, predicates, digest equality, row table — all JS; lints — all gate | X, G |
| AP-14 parallel mutators / overlapping files | disjoint write sets per wave; agent-created worktrees; single serial integrator | X, I |
| AP-15 trusting "done" | `taskDone()` reads the verifier's digest against the builder's, never a status; `--clean` from a pristine detached checkout per wave — **v2: typed three ways, and a malformed return is never a revert (C-11)** | X, G |
| AP-16 performative agreement in the fix loop | fixer gets typed failures (v2: `digest_mismatch` carries both ledgers, C-18); `strongest_disagreement` required; refuted findings recorded | R1, W |
| AP-17 trailing limitations section | `verification_level` inline per line/finding; `dod_deferred` per row; `blocked_on_owner` first — **v2: every row also carries `reason` + `next` (C-22)** | S |

### 12.3 Tool-native anti-patterns T-AP-1..12 (research-2 §6)

| id | Guard | Phase |
|---|---|---|
| T-AP-1 consent-in-prompt | approvals are `args` data; outward actions → `HALT` | X |
| T-AP-2 secret-in-trigger | P0 pre-scan; `AUTHORITY` text; no token anywhere | P0 |
| T-AP-3 self-certifying implementer | builder's exit code advisory; its digest is one half of an equality; claim lint | G, X |
| T-AP-4 unbounded until-satisfied | five stop conditions (§6.2) — **v2 adds `tree-incomplete` (C-5), `blocked-on-owner:staging-evidence` (C-6), `clean-gate-unavailable`/`veto-unavailable` (C-10/C-11), `plan-needs-repair` (C-19), `max-rounds`, `dry`** | X |
| T-AP-5 dedup against `confirmed` | `seen` set of `fkey`s across rounds ★ and across invocations | X |
| T-AP-6 barrier between per-item stages | `pipeline(wave, buildTask)`; barriers only where cross-item context is needed | X |
| T-AP-7 parallel writers on one checkout | one worktree per mutating call; one serial integrator | R1, I |
| T-AP-8 worktree as the checkpoint | branch in the shared store + `plan/status/<id>.json` on the integration branch + incremental bundles; `reused`/`already-merged` idempotency — **v2: `already-merged` counts only with evidence (C-20)** | R1, I |
| T-AP-9 volatile prompt content | prompts from `args` + sorted results; ★ `launched_at` only in the git-mode setup prompt (deliberate); knobs never interpolated | X |
| T-AP-10 stale-sha evidence | `sha` on every verdict; integration head in every prompt; digest equality at one sha — **v2: reverts target the recorded `merge_sha` (C-12)** | X |
| T-AP-11 silent truncation | every cap/drop/park/deferral logged and in the ledger; ★ lens drops, refute-chain drops, wave-chain drops counted — **v2: `fixcards-unavailable` typed and counted (C-3); starved chains typed `not_attempted` with a reason (C-8)** | X |
| T-AP-12 one giant implementer | 22 `S/M` cards; `partial` not built; `L` throws — **v2: `est_lines` validated against the size class (C-13)** | R0, X |

### 12.4 External anti-patterns S-AP-1..14 (research-3 §3)

| id | Guard | Phase |
|---|---|---|
| S-AP-1 self-grading | fresh verifier per verdict; digest equality | R1, W |
| S-AP-2 early victory | the gate runs the complete suite twice; collected floor vs the pinned baseline | G |
| S-AP-3 oracle tampering | oracle lock + reset; protected paths; `plan/` immutable; gate pinned | G |
| S-AP-4 hollow feature-isolated implementation | ★ seams H1-H7 + J1 as journeys — **v2: a SEPARATE pytest collection (C-4): the `journey` marker is added by `tests/journeys/conftest.py` (card 01) and deselected from every default run, so a missing journey can never be a baseline skip; `--journeys` at every merge + clean gate; `needs=` the only legal skip and counted by the gate; a journey still skipped after its card merged is a synthetic blocking finding**; review lens `correctness` | R1, I, W, X |
| S-AP-5 telephone-game decomposition | one builder lineage per card; cards self-contained with CORRECTED text — **v2: fix cards likewise carry their finding's content verbatim in the prompt (C-3)** | R1 |
| S-AP-6 unbounded fix loop / thrash | `MAX_BUILD`, fingerprints (never empty, C-18), oscillation, revert-not-fix after a red merge — **v2: the revert targets the merge sha (C-12)** | X, I |
| S-AP-7 claims without diffs | claim lint; `dod[]` on both sides; reviewers treat claims as hypotheses | G, W |
| S-AP-8 secret sprawl | no `.env`; OIDC in CI with `permissions:` blocks; `env -i` + canary; ★ redaction of returns; **v2: the `TESTTOKEN-` dummy convention (C-32)**; token topology recorded by the owner | R1, G, X, O |
| S-AP-9 non-resumable script | §10.1 — **v2: retryable parks auto-retry, `not_attempted` re-evaluated live (C-8)** | X |
| S-AP-10 irreversible action inside the loop | `AUTHORITY`; `HALT`; remotes checked; CI + owner only | X, O |
| S-AP-11 biased judging protocol | binary evidence-backed verdicts; veto-only judge; `strongest_disagreement` — **v2: refutations must carry a non-zero-exit reproduction (C-27)** | W |
| S-AP-12 canary checks the wrong thing | ★ `EXPECTED.json` with sha echo (`unknown` rejected), 16-token ×3, `finish_reason`, p95 vs last-known-good, visibility `private`, log tail on failure (A1 contract); **v2: `build_info.json` written by CI, with a placeholder (`git_sha: "unknown"`) shipping in card 03b so `/healthz` is testable pre-CI (C-34); the contract lives in `tools/expected.py` (C-35)** | R1, R2 |
| S-AP-13 context overflow / kitchen sink | one card per builder; reading lists capped; typed returns | R1, X |
| S-AP-14 reviewer over-reporting → churn | findings need a reproduction that exits non-zero (C-27); owner-level findings become `blocked_on_owner` rows, not fix cards — **v2: medium/low ids the owner explicitly listed in `owner_approvals.accepted_findings` are typed `deferred` instead (C-6; policy §15 Q10); critical/high always block** | W |

### 12.5 DEEP anti-patterns SD-AP-1..12 (research-3-DEEP Appendix B)

| id | Guard | Phase |
|---|---|---|
| SD-AP-1 author-graded work | author ≠ builder ≠ verifier by role | R1 |
| SD-AP-2 green-by-weakening | oracle lock + reset; author-range tamper rules; builder-test tamper idioms; skip/xfail set rule; mutants; revert-proof (incl. builder-added tests/unit, C-28); **v2: the idiom lint is scoped to `--lint-base..HEAD` with comments stripped, so it fires on code, not on legitimate prose (C-15)** | G |
| SD-AP-3 vacuous/tautological tests | confirm-RED (rc 1/2 only; `expected_green_tests` both ways, C-13); mutants all killed; revert-proof | R1, G |
| SD-AP-4 unanimous-LLM "verification" | no verdict without an executed command; digest equality is a two-execution signal (confirm-RED included, C-29) | G, X |
| SD-AP-5 endless/oscillating fix loops | as S-AP-6 | X |
| SD-AP-6 summary-of-summary handoffs | schemas; decisions by path + sha; typed failures to the fixer (digest_mismatch with both ledgers, C-18) | X, R0 |
| SD-AP-7 parallel implementers on shared files | disjoint write sets; serial integration | X, I |
| SD-AP-8 phantom-change commits | claim lint; ruff; `taskDone()` (diff_stats fail-closed, C-25) | G, X |
| SD-AP-9 secrets in reach | `env -i` for every test run; canary; redaction; no token in any run | G, X |
| SD-AP-10 agent-executed irreversible actions | as S-AP-10 | X, O |
| SD-AP-11 non-replayable script | as S-AP-9 | X |
| SD-AP-12 scaffold maximalism | six roles, one gate, one script; every re-added mechanism names the judge evidence that forced it (§1.4); agent count logged per run — **v2: every new mechanism names its C-gap (Appendix B), and the drive proves each one runs** | X |

### 12.6 Common-gap rows (the union of J1 §7, J2 §7, J3 §8; each with a mechanism or an explicit owner checkpoint with reason)

| id | Gap (judge) | Guard | Phase |
|---|---|---|---|
| CG-1 | external `gate.sh` copy agent-writable and unpinned (J1 CG1) | `args.gate_sha256`; the gate verifies its own bytes (exit 66); repo copy compared in the integrity step **and `tools/gate.pin` present (v2)**; verifiers/integrators return `gate_sha256_observed`, compared in `taskDone()`/`mergeOk()`; baseline pinned the same way | P0, G, X |
| CG-2 | stray-listener kills cross-chain destructive or inert (J1 CG2) | kill scoped to `/proc/<pid>/cwd == $REPO` (the current worktree); harnesses own their ports and teardown | G, R1 |
| CG-3 | structured returns never secret-scanned before entering prompts (J1 CG3) | `redact()` in `run()`; `taskDone()` condition 11; fixer/synth prompts only see redacted, capped text — **v2: dummy credentials use the `TESTTOKEN-` convention so fixtures cannot self-match (C-32)** | X |
| CG-4 | persona history access only a prompt rule (J1 CG4) | history-free `git clone --depth 1 --single-branch` for the persona card's worktrees + local fetch back; `AUTHORITY` rule kept as a second layer | R1, X |
| CG-5 | outward-action detection self-report only (J1 CG5) | `git remote -v` from setup + every clean gate → `HALT`; branch count reported; owner Hub post-checks (`gh repo list`, namespace listing vs the P0 snapshot) in the runbook — **O** because the script must not hold a Hub token | X, S, **O** |
| CG-6 | the script cannot read files; no ledger-reader probe (J1 CG6) | declined as an extra agent: digest equality is the two-execution cross-check (a third reader would re-read a file an agent wrote); every value a decision rests on is either reproduced by a second agent or asserted by the gate itself | X |
| CG-7 | resume admissibility as orchestrator discipline (J1 CG7) | setup probe (live in `git` mode) reports `integration_head_live`; JS throws `stale-launch-args` on mismatch; merged set from git | X |
| CG-8 | completion-order dependence of the call sequence (J1 CG8) | barrier waves; sorted ids; `git` resume mode by default; `cache` only after the settling experiment | X, P0 |
| CG-9 | skip/xfail floors vs legitimate xfails (J1 CG9) | `xfail_allowed[]` per card (lens-4 §F known-bads only, refuted by `verifier mode:'plan'`); skip SET rule vs the pinned baseline; no trailers — **v2: journeys are outside the default suite entirely, so a missing journey cannot pollute the baseline (C-4)** | G, R0 |
| CG-10 | required-files-after-card manifest absent (J1 CG10) | **v2: the manifest IS the plan** — `--require` receives the merged cards' `new_modules ∪ required_files`, validated at plan time against `MANIFEST_MIN` (conditional on `args.torch_in_venv` for `worker/penalty.py`, C-14); absence is RED; the plan must contain every manifest card (JS) | X, G |
| CG-11 | worker import-smoke stubs delivered by no card (J1 CG11) | card 01 delivers `tools/stubs/{torch,transformers,spaces}`; in the manifest; `import worker.app` required after 08b | R1, G |
| CG-12 | F-38 "Space HEAD == base" as a runbook sentence (J1 CG12) | `owner_approvals.production_space_head` required for `promote-production`; blocked otherwise (v2: and `ready` additionally requires no confirmed critical/high staging finding, C-6); the read itself is **O** (read-only Hub read by the owner) | X, **O** |
| CG-13 | H6 timeout ↔ resume replay divergence (J2 1) | `REPLAY_RISK` on any timeout → `next_args.resume_mode='git'`; `git` mode has no replay | X |
| CG-14 | queue wait counted against timers (J2 2) | waves ≤ cap (asserted); `tmo()` multiplies by `ceil(enqueued/cap)` for barriers that exceed the cap | X |
| CG-15 | replayed calls vs the 1000-agent cap (J2 3) | assumed to count; slices ≤ 110 at cap 2; `git` mode = separate workflow runs | X |
| CG-16 | permission dialogs vs hangs (J2 4) | smoke-one-first with the allow-list inventory — **v2: the smoke skips the review loop so it stays one card wide (C-33)**; owner attends the first wave of every invocation (**O**, the script cannot see a dialog); `timeout-or-dialog` logged, one retry only | P0, **O** |
| CG-17 | validator support for `pattern/maxLength/minimum` (J2 5) | removed from every schema; `isSha`/`isHex64`/`cap()`/enums in JS | X |
| CG-18 | unmeasured cache-key composition (J2 6) | correctness independent of the cache (git idempotency); settling experiment gates `cache` mode | P0, X |
| CG-19 | `seen` not persisted across runs (J2 7) | `status.json` carries `seen_keys`; the setup probe returns them; JS seeds `seen` | X, S |
| CG-20 | budget-exhaustion throw fan-out (J2 8) | `HALT='budget-exhausted'` on the first budget throw; every later `budgetOk()` false; no retries — **v2: except the synthesizer, which is exempt so the report always gets written (C-7)** | X |
| CG-21 | `nproc` vs the cap arg (J2 9) | setup returns `nproc`; `min(16, nproc−2) === args.cap` or `cap-mismatch` throws; `wave_size ≤ cap` | X |
| CG-22 | `model` on meta phase entries (J2 10) | no `model` override anywhere; adding one is a script + `meta.phases` edit (checklist) | X |
| CG-23 | completion-order ledgers in synth prompts (J2 11) | ledger summary sorted by `(role, mode, id, attempt)`; rows sorted by id | S, X |
| CG-24 | unchecked revert-integrator results (J2 12) | `P.revert` builder; result checked (`merged` + 40-hex head + exit 0 + digest) else `revert-failed` + `INTEG_DIRTY` (no further merges; checkpoint `failed`) — **v2: the revert targets the recorded `merge_sha` (C-12)** | I, X |
| CG-25 | one scoped inference token vs two backends (J3 1) | decision-sheet clarification `G-24-clar`; card 08b env contract; C1 `set-staging-secrets` asks for `token_topology` (**O** approval) | R0, R1, **O** |
| CG-26 | `find_spec` probe + kernels card (J3 2) | card 08a boot probe line (CPU-testable); card 08d (staging worker only; Triton budget; no `kernels` without a build check) with `staging-required` DoD lines → runbook rows | R1, R2 |
| CG-27 | `presence_penalty` fate (J3 3) | decision row + card content per §15 Q2 (default: remove the placebo; API 400 unless 0); `presence_penalty=[1-9]` is a warning idiom; `known_bad` regex for passing it to `generate`; **v2: the decision is wired into `MANIFEST_MIN` via `args.torch_in_venv` (C-14)** | R0, R1, G |
| CG-28 | lens-4 §C duplication list not DoD lines (J3 4) | §4.7: ten mechanical DoD lines on cards 02/03a/04/05a; `verifier mode:'plan'` refutes a plan missing one — **v2: re-checked in every stage (C-19)** | R0, X |
| CG-29 | persona absence fragments vs the boundary (J3 5) | owner-generated shingle-hash fixture — **v2: generated with card 01's `tools/make_boundary_fixture.py`, copied by the FIXTURE COPY STEP, sha-pinned by `--boundary-sha256` + the owner field `persona_boundary_fixture_sha256` (C-21)**; card 13b blocked until it exists (**O**) | R1, **O** |
| CG-30 | fixture #1 ordering (J3 6) | card 04 `owner_precondition: fixture1_path` → `blocked_on_owner` (v2: with field/why/next/severity, C-22); downstream `not_attempted: dependency-blocked`; C0/C1 carry the action | X, **O** |
| CG-31 | `/healthz` git sha source inside a Space container (J3 7) | CI writes `build_info.json` at deploy (card 14); the app reads it (card 03b; fallback `git rev-parse`, else `unknown`, which the canary and the R2 evidence reader reject) — **v2: card 03b ships a placeholder `build_info.json` (`git_sha: "unknown"`) so `/healthz` is testable before CI exists (C-34)** | R1, R2 |
| CG-32 | `admission: pending` entries in the single release (J3 8) | `M-3-clar`: `core/catalog.visible()` hides pending; `tests/test_catalog_policy.py` (protected); C2 `run-harness` before promotion (**O**) | R0, R1, R2, **O** |
| CG-33 | worker checkpoint without visual tensors (J3 9) | R0 catalog agent records `has_visual_tensors`; C0 `decide-worker-checkpoint`; card 08c (export tool + runbook) blocked on the decision; C2 `run-hf-job-quantize` only if `needs_export` (**O**, paid) | R0, R1, R2, **O** |
| CG-34 | Python patch level 3.12.3 vs 3.12.12 (J3 10) | `python` in every ledger/digest; R2 evidence reader compares `space-runtime.json` + `build-log.txt` resolution with `requirements.lock` (finding on mismatch); §15 Q6 | G, R2, **O** |

**Rows guardable only with an owner checkpoint:** F-6, F-35 (Hub post-checks), F-36, F-37, F-38 (the read), F-44 (idle timeout), CG-5, CG-12, CG-16, CG-25, CG-29, CG-30, CG-32, CG-33, CG-34 (the interpreter choice), S-AP-8/S-AP-10/SD-AP-10 (the outward half). Everything else has a deterministic or script-level guard.

### 12.7 v2 mechanism rows (one per critic gap that is not already a rewritten cell above; gap ids = Appendix B)

| id | Gap (critic) | Guard (v2 mechanism) | Phase |
|---|---|---|---|
| V-1 | import-app RED by construction (C-1) | the apicheck's `import-app` step is conditional on `[ -f api/app.py ]`; card 03b ships `api/app.py` (with a placeholder `build_info.json`) and its own gate command runs both collections — no card is red because an earlier card has not delivered the file yet | G, R1 |
| V-2 | self-test false-claim fixture produced no claims (C-2) | the fixture pair is delivered by card 01 at `tests/fixtures/gate/` (v2.1 V-4 correction — the gate creates only the temp worktree); the gate crafts a commit message that matches the claim-lint regexes over a patch that does not change the symbol; the step asserts `false_claim_red === 'true'` from the inner ledger's `claim-lint` step; P0's bootstrap profile tolerates `fixture-not-yet-delivered` | G, P0 |
| V-3 | review fix cards had no writer and no cardRef (C-3) | `toFixCard()` writes `plan/fixes/<fixid>.json`; the integrator `mode:'fixcards'` commits them (the one mutable area of `plan/`); the author/builder prompts carry the card content AND the finding verbatim; the gate is invoked with `--card plan/fixes/<fixid>.json` | I, W, X |
| V-4 | journeys collected by the wrong suite (C-4) | `tests/journeys/conftest.py` (card 01) marks the collection; `pytest.ini` deselects `journey` from every default run; `--journeys` on every merge and clean gate; `needs=<card-id>` the only legal skip; `skipped_other` RED; a still-skipped merged journey becomes a synthetic blocking finding | G, R1, I, X |
| V-5 | DAG enforced only at plan time (C-5) | `readyWave()` recomputed from the live status map before every wave; `markDependencyBlocked` types every unscheduled dependent `not_attempted: dependency-blocked:<dep>(<state>)`; the review pre-check stops `tree-incomplete` before a single lens is spent | X, W |
| V-6 | R2/R3 could emit promote/ready over confirmed staging findings (C-6) | `ready` requires `blocked_on_owner` empty ∧ `ownerCritical === 0`; the stop is `blocked-on-owner:staging-evidence`; `rollback` only on confirmed critical/high evidence — an unavailable evidence read blocks, never rolls back | X, S |
| V-7 | synthesizer skipped after HALT (C-7) | `budgetOk(label, exemptFromHalt)`: after the invocation agent-cap check the exempt call returns true even under `HALT`/exhaustion — the reserve exists to pay for the report | X |
| V-8 | starvation became permanent parks; rows had no reasons (C-8, C-22) | starvation typed `starved` → `not_attempted` (retryable); `RETRYABLE_RE` auto-retries such parks on resume; `retry_parked_suggested[]` in the checkpoint; every row and parked entry carries `reason` + `next` | X, S |
| V-9 | `next_args.stage` advanced over unfinished stages (C-9) | the nextStage table: `plan → build|plan`, `build → stage|build`, `stage → promote|stage`, `promote → done|promote` — never past a stage that did not finish | X |
| V-10 | no clean gate before reviewing a stale tree (C-10) | the review pre-check runs ONE clean gate when the last one is not a pass at the current head; fail/unavailable stops before any lens | W, I |
| V-11 | malformed clean gates reverted good merges (C-11) | three-way typing `pass | fail | gate-unavailable`; a dropped agent, a malformed shape, a wrong head or an exit 0 contradicted by the self-test is `unavailable` — never a revert; `satisfied()` stays false | X, I |
| V-12 | reverts targeted HEAD (C-12) | every merge records `merge_sha`; gate-red-after-merge, clean-gate fail and the journeys case all revert that exact commit; the revert result is checked | I, X |
| V-13 | card 01 could not satisfy its own gate (C-13) | `expected_green_tests[]` (green-by-design ids, honoured both ways), the `config.py` skeleton with all eight flags, card 01 size M, `LEDGER_DIFF_STATS` excluding `tools/gate.sh` and `tests/fixtures/` | G, X, R0 |
| V-14 | REQUIRED_AFTER contradicted the plan (C-14) | `MANIFEST_MIN` derived from the cards' `new_modules ∪ required_files` with `worker/penalty.py` conditional on `args.torch_in_venv`; the four CI filenames pinned in card 14's manifest; `validateCards` checks plan-vs-manifest coverage | X, R0, P0 |
| V-15 | idiom lint re-scanned all history (C-15) | two tiers scoped `--lint-base..HEAD`, `tests/` excluded, comments stripped; per-`Card:` `Claim-Waiver` counting; `--lint-base` = the last clean pass | G |
| V-16 | apicheck could not resolve torch symbols (C-16) | import-first from the venv, else ast-parse of the pinned wheel SOURCE under `--libsrc`; a missing kwarg is RED; an unlocatable symbol is `unresolvable-needs-torch` — recorded (`api_unresolvable[]`), never RED | G, X |
| V-17 | toolchain-status HALT fired on grill syncs (C-17) | the hash is `git status --porcelain -- . ':!docs/grills'`; bundles live under `/workspaces/space-build-bundles/` with only their manifest in the grill tree | X, P0 |
| V-18 | digest equality fragile; fingerprints could be empty (C-18) | the builder runs the gate LAST on the committed clean tree; `apicheck-extended` is a separate `checks[]` entry with its own ledger; `digest_mismatch` carries both ledgers' steps; the fingerprint is never empty | R1, G |
| V-19 | plan checks only ran in R0 (C-19) | `checkPlan(idx, preverified)` in every stage; a defect yields `repair-plan` + `next_args.plan_defects` (R0) or `FAILED:plan-needs-repair` before any author/builder (R1); the relaunch runs the planner in REPAIR MODE | X, R0, R1 |
| V-20 | `already-merged` bypassed every check (C-20) | it counts only with evidence: head unchanged + gate exit 0 + digest + pinned gate + cherry/patch-id empty; otherwise `already-merged-unproven` blocks the card; `merged` + red gate → checked revert-now | I, X |
| V-21 | persona pipeline incomplete (C-21) | card 01 delivers `tools/make_boundary_fixture.py`; the author prompt carries the FIXTURE COPY STEP; the gate pins `--boundary-sha256` (= the new owner field `persona_boundary_fixture_sha256`); protected paths are governed by the ownership rule (manifest ∪ `protected_touch`) | R1, G, P0, **O** |
| V-22 | minors batch (C-23..C-38) | C-23 RECEIPT_RE dropped, fragments logged · C-24 integration in `(−rank, id)` order · C-25 `diff_stats` fail-closed (ok[10]) · C-26 the second author attempt carries the red verdict · C-27 reproductions must exit non-zero · C-28 `--revert-proof` includes builder-added `tests/unit/*` · C-29 confirm-RED requires digest equality · C-30 conflict worktrees are detached · C-31 the venv is created only at P0, agents assert it exists · C-32 `TESTTOKEN-` dummy credentials · C-33 smoke mode skips the review loop · C-34 placeholder `build_info.json` + `evidence/catalog/` in-repo + the four CI filenames · C-35 `tools/expected.py` is the `EXPECTED.json` contract CI writes · C-36 `core/engine.py` owned by card 03a · C-37 `run()` maps timeout → `timeout-or-dialog` and types revert reasons · C-38 a clean gate is skipped when nothing merged and the last one passed at this head | X, G, I, W |

---

## 13. The script (exact contents)

The `meta` literal of §13.0, the §9 schemas pasted verbatim at the marker, and the body below are assembled into one file; `node --check` passes on the assembled file (checked in its ESM-factory form and as an async-IIFE wrap, since the plain body contains top-level `await` by design) and the fake-harness drive (`drive.mjs`, §Appendix C: 41 scenarios, 107 assertions including the v2.1 S38-S41) passes 107/107. The `pipeline`/`parallel` thunks, the four stages, the counters and the checkpoint are all here; every v2 mechanism named in §2-§6 is a named function or constant in this text.

```js
export const meta = {
  name: 'space-rebuild-v2',
  description: 'Implementation workflow for the qwen38 heretic Space (design-v2 = A3 base + judge grafts + critic fixes): plan (pre-verify findings → api ledger → catalog provenance → planner → JS checkPlan → plan verifier; repair path) → per card (author → confirm-RED with expected_green exceptions → build → verify with digest equality, mutants, revert-proof → bounded fix with typed digest-mismatch) in runtime DAG waves → serial integrate by merge sha + clean gate typed pass|fail|unavailable with self-test + journeys → review/refute/fix cards on plan/fixes → veto loop → synthesizer always; outward actions only as owner checkpoints between runs',
  phases: [
    { title: 'Setup', detail: 'idempotent + the one live state probe per invocation: durable clone at base_sha, pinned venv/gate/baseline verified (never created here), red-proof, plan merged into integration, live heads, remotes, prior rows with reasons' },
    { title: 'Plan', detail: 'pre-verify UNVERIFIED findings (executed reproduction) ‖ api-ledger with known_bad ‖ catalog provenance saved raw → planner writes decisions.json (against_recommendation, dq_line) + cards + index → checkPlan (JS, every stage) → verifier mode:plan refutes; a defective plan yields repair-plan, never approve-plan' },
    { title: 'Build', detail: 'per card: author → red (expected_green_tests exempt) → builder → verifier (gate digest must equal the builder\'s on a clean tree; mutants all killed; revert-proof red; every local DoD id exit 0 on both sides) → bounded fix with typed failures; waves computed one at a time from the live status map (dependents of a parked card are never built)' },
    { title: 'Integrate', detail: 'serial single-writer merges in rank order, gate on the merged tree with --journeys, conflict call, revert by merge sha (checked), bundle, clean-gate --self-test --journeys per wave typed pass|fail|gate-unavailable, journeys author when a seam card merged' },
    { title: 'Review', detail: 'tree-complete + passing clean gate at head required before any lens; 3 lenses → dedup vs persisted seen → refute with a non-zero-exit reproduction → fix cards written to plan/fixes by the integrator → satisfied() predicate → veto-only judge (fail closed on drop; probesUsed to the inversion mandate); MAX_ROUNDS/dry/budget/agent caps; evidence stages stop on a confirmed critical/high staging finding' },
    { title: 'Synthesize', detail: 'script-computed row table (with reason + next per row) rendered; rows re-written on disk by a probe when they differ; checkpoint object returned by the script; runs after every HALT' },
  ],
  whenToUse: 'One run per args.stage (plan | build | stage | promote); launch only from the orchestrator turn that holds the owner\'s approval words; never with a secret in args or the trigger message',
}

// ---------------------------------------------------------------------------------------------
// args contract — every value computed by the orchestrator with git rev-parse / sha256sum right
// before invocation; NEED lists every arg a prompt interpolates for that stage (J2: complete NEED)
// ---------------------------------------------------------------------------------------------
const A = args || {}
const NEED_ALL = ['stage', 'run_nonce', 'launched_at', 'cap', 'wave_size', 'build_repo', 'snapshot_dir', 'venv', 'wheels_dir', 'libsrc', 'tools_dir', 'gate_sh', 'gate_sha256', 'baseline_path', 'baseline_sha256', 'base_sha', 'toolchain_status_sha256', 'resume_mode', 'max_agents_this_run']
const NEED_BY_STAGE = {
  plan: ['decision_queue_path', 'lens4_path', 'findings_path', 'redteam_path', 'unverified_finding_ids', 'against_recommendation_ids', 'catalog_candidates'],
  build: ['plan_sha', 'owner_approvals'],
  stage: ['plan_sha', 'owner_approvals', 'integration_sha_at_launch', 'last_clean_gate'],
  promote: ['plan_sha', 'owner_approvals', 'integration_sha_at_launch', 'last_clean_gate'],
}
if (!NEED_BY_STAGE[A.stage]) throw new Error('args.stage must be plan|build|stage|promote')
for (const k of NEED_ALL.concat(NEED_BY_STAGE[A.stage])) if (A[k] === undefined || A[k] === null || A[k] === '') throw new Error('args.' + k + ' is required for stage ' + A.stage)
const isSha = s => typeof s === 'string' && /^[0-9a-f]{40}$/.test(s)
const isHex64 = s => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s)
if (!isSha(A.base_sha)) throw new Error('args.base_sha must be a full 40-hex sha')
if (!isHex64(A.gate_sha256) || !isHex64(A.baseline_sha256)) throw new Error('args.gate_sha256 / baseline_sha256 must be 64-hex (the orchestrator pins both at P0)')
if (A.plan_sha && !isSha(A.plan_sha)) throw new Error('args.plan_sha must be a full 40-hex sha')
if (A.integration_sha_at_launch && !isSha(A.integration_sha_at_launch)) throw new Error('args.integration_sha_at_launch must be a full 40-hex sha')
const TOOLCHAIN = '/workspaces/agent-skills-toolchain'
for (const k of ['build_repo', 'tools_dir', 'libsrc', 'venv']) if (String(A[k]).startsWith('/tmp/') || String(A[k]).startsWith(TOOLCHAIN)) throw new Error('args.' + k + ' must be durable and outside the toolchain repo (F-1, F-2)')
if (!['git', 'cache'].includes(A.resume_mode)) throw new Error('args.resume_mode must be git|cache (cache only after the smoke-run settling experiment, §10.1)')
if (!(A.wave_size >= 1 && A.wave_size <= A.cap)) throw new Error('args.wave_size must be 1..cap so a wave never enqueues more agents than the cap (CG: queue wait vs timers)')
const OA = A.owner_approvals || {}                                           // F-6: approvals are DATA
const R = A.build_repo, WT = R + '-wt', TOOLS = A.tools_dir, GRILL = A.grill_dir || '/home/codespace/grills/2026-09-19-qwen38-heretic-space'
const BUNDLES = (A.bundles_dir || '/workspaces/space-build-bundles') + '/' + A.run_nonce      // C-17: bundles live OUTSIDE the rsynced grill tree; the grill gets the manifest
const STATUS_JSON = GRILL + '/build-bundles/' + A.run_nonce + '/status.json', BUNDLE_MANIFEST = GRILL + '/build-bundles/' + A.run_nonce + '/bundles-manifest.json'
const CAP = A.cap, WAVE = A.wave_size, MAX_ROUNDS = A.max_rounds || 3, MAX_BUILD = A.max_build || 3, MAX_AUTHOR = 2
const RESERVE = A.reserve_tokens || 120000, AGENT_SOFT_CAP = 800, MAX_AGENTS_RUN = A.max_agents_this_run, RESERVE_PER_CHAIN = 7
const INTEG = 'integration/' + A.run_nonce, PLAN_BRANCH = 'plan/' + A.run_nonce
// v2.1 V-6: mode key 'tests' (run('author','tests',…) looks up TIMEOUT['tests']) — 25 min, matching the role-named prose in §10.4/§11
const TIMEOUT = { author: 1500000, tests: 1500000, red: 600000, build: 3000000, fix: 2400000, verify: 1800000, merge: 1200000, conflict: 1800000, ff: 900000, revert: 900000, clean: 1500000, journeys: 1500000, review: 1800000, refute: 900000, veto: 1500000, plan: 2400000, setup: 1800000, synth: 900000, synthfix: 600000, preverify: 1200000, apiledger: 1500000, catalog: 900000, evidence: 900000, index: 600000, fixcards: 600000 }
const tmo = (mode, enqueued) => (TIMEOUT[mode] || 1800000) * Math.max(1, Math.ceil((enqueued || 1) / CAP))   // CG: queue wait counts against the timer → size it by queue depth
const AGAINST = A.against_recommendation_ids                                 // ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'] — the five decisions taken against the recommendation
const STAGING_RE = /\b(lease|quota|ZeroGPU|worker fork|Triton|fla|x-ip-token|MCP transport|Space rebuild|cold[- ]start|tok\/s|FP8|GPTQ|provider|requirements resolution|canary|rollback|OIDC|secret)\b/i
const RECEIPT_RE = /started in the background|Check \/codex:status|as a follow-up task|will report back when/i      // C-23: "based on the digest" dropped — it is the design's central phrase
const SECRET_RE = /ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/
const RETRYABLE_RE = /^(not_attempted|starved):|agent-null|threw|timeout-or-dialog|integration:not-merged:null|fixcards-unavailable/   // C-8: reasons that mean "nobody judged the work" — retried on resume without retry_parked
const TOOLCHAIN_STATUS_CMD = 'git -C ' + TOOLCHAIN + ' status --porcelain -- . ":!docs/grills"'   // C-17: the grill sync loop writes docs/grills every 5 min; that is not a mutation of the toolchain
// C-21 / C-14: protected paths and the design's minimum required-files manifest per card. PROTECTED here is THE single list: card 01 writes
// tests/protected.txt from it verbatim (one path per line) and the plan verifier refuses any divergence (v2.1 V-5 — one list, two renderings, never two lists).
// Ownership: a card may write a protected path only when its own MANIFEST_MIN declares it; only platform-01-gate carries protected_touch.
// The persona-boundary fixture is ALSO pinned by owner_approvals.persona_boundary_fixture_sha256 (gate step boundary-fixture).
const PROTECTED = ['tests/test_personas.py', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/test_python_eval_surfaces.py', 'tests/test_catalog_policy.py', 'tests/fixtures/gate/false-claim.patch', 'tests/fixtures/gate/false-claim-target.txt', 'tests/fixtures/persona_boundary.json', 'tests/journeys/conftest.py', 'tests/protected.txt', 'tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tools/baseline.pin', 'tools/make_boundary_fixture.py', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig', '.gitignore']
const MANIFEST_MIN = {
  'platform-01-gate': ['tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tools/baseline.pin', 'tests/protected.txt', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/fixtures/gate/false-claim.patch', 'tests/fixtures/gate/false-claim-target.txt', 'tests/journeys/conftest.py', 'tools/make_boundary_fixture.py', 'tools/stubs/torch/__init__.py', 'tools/stubs/transformers/__init__.py', 'tools/stubs/spaces/__init__.py', 'config.py', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig', '.gitignore'],
  'platform-03a-types-fake': ['core/types.py', 'core/engine.py', 'backends/base.py', 'backends/fake.py', 'tools/record_fixture.py', 'tests/conformance/conftest.py'],
  'platform-03b-thin-slice': ['app.py', 'api/app.py', 'backends/hosted.py', 'models.yaml', 'build_info.json'],
  'platform-04-streamparser': ['core/parsing.py', 'core/events.py'],
  'platform-05a-registry': ['core/tools/registry.py', 'tests/test_python_eval_surfaces.py'],
  'platform-05b-agent-session': ['core/agent.py', 'core/session.py'],
  'platform-08a-worker-pure': ['worker/encode.py', 'worker/lease.py'].concat(A.torch_in_venv ? ['worker/penalty.py'] : []),   // C-14: Q2 default removes the placebo; penalty.py only when torch is in the venv
  'platform-08b-worker-backend': ['worker/app.py', 'backends/worker.py'],
  'product-13a-catalog': ['tools/render_readme.py', 'core/catalog.py', 'tests/test_catalog_policy.py', 'evidence/catalog/README.md'],
  'product-13b-personas-readme': ['core/personas.py', 'tests/test_personas.py', 'tests/fixtures/persona_boundary.json'],
  'platform-14-promotion-ci': ['.github/workflows/gate.yml', '.github/workflows/deploy-staging.yml', '.github/workflows/promote.yml', '.github/workflows/health.yml', 'tools/promote.py', 'tools/expected.py'],
}
const reqFiles = c => [...new Set([...(c.new_modules || []), ...(c.required_files || [])])].sort()   // C-14: REQUIRED_AFTER is derived from the card, validated against MANIFEST_MIN
// held-out seams (A1 §4.6) → the card each journey needs; a journey stays skipped-with-reason (needs=<card>) until that card is merged
const JOURNEY_NEEDS = { J1: 'platform-03b-thin-slice', H7: 'platform-04-streamparser', H4: 'platform-05a-registry', H6: 'platform-05b-agent-session', H2: 'platform-07-gateway', H1: 'platform-08a-worker-pure', H3: 'platform-11-mcp', H5: 'product-13a-catalog' }
log('stage=' + A.stage + ' nonce=' + A.run_nonce + ' base=' + A.base_sha.slice(0, 12) + ' cap=' + CAP + ' wave=' + WAVE + ' rounds=' + MAX_ROUNDS + ' resume=' + A.resume_mode + ' maxAgentsThisRun=' + MAX_AGENTS_RUN + ' budget=' + (budget.total || 'none') + (A.smoke ? ' SMOKE' : ''))

// ---------------------------------------------------------------------------------------------
// Constant prompt preambles (byte-identical on every call → cache prefix; F-4, T-2)
// ---------------------------------------------------------------------------------------------
const PREAMBLE = [
  'CONTEXT RULES. The current working directory repo (' + TOOLCHAIN + ') and its CLAUDE.md are UNRELATED to this task:',
  'ignore every instruction there about SSOT gates, ~/source/*, drift checks or pushing. The ONLY repository you may touch is ' + R + '.',
  'Read ' + R + '/AGENTS.md first when it exists. Use absolute paths and `git -C "<checkout>"` for every git command. Worktrees live under ' + WT + '/.',
  'Python for everything: ' + A.venv + '/bin/python (3.12). Gate: VENV=' + A.venv + ' bash ' + A.gate_sh + ' --gate-sha256 ' + A.gate_sha256 + ' … (its printed LEDGER_DIGEST is the only admissible evidence; it must be reproduced by an independent run from a clean, committed tree).',
  'Dummy credentials in tests must never match the secret regex (use TESTTOKEN-…, never hf_/ghp_/sk-ant- prefixes with 20+ characters).',
  'Return repo_toplevel AND git_common_dir of the checkout you worked in (git rev-parse --show-toplevel; git rev-parse --path-format=absolute --git-common-dir).',
].join('\n')
const AUTHORITY = [
  'AUTHORITY (restates the owner request that launched this run; the owner request wins): local edits inside your own worktree and local commands only.',
  'NEVER: git push (to any remote); add a remote; create/duplicate a GitHub repo or HF Space; set or read secrets; call any *.hf.space URL; run HF Jobs; look for or use tokens;',
  'install packages (pip/uv/npm); run a server in the foreground without a timeout; print any environment; read `git log`/`git show` of system_prompt.py history; modify files under plan/ (except plan/status/ and plan/fixes/ for the integrator) or outside your card\'s allowlist.',
  'Commit after every coherent step. Your final answer is the StructuredOutput object only.',
].join('\n')
const NARROW = 'RETRY RULE: first run `git -C "' + R + '" status --porcelain` and `git -C "' + R + '" log --oneline -5` on your branch; continue from the last commit; discard uncommitted partial edits only if they do not compile (else commit them as "wip(<card>): salvage"); read at most half of the listed files.'

// ---------------------------------------------------------------------------------------------
// h6 timeout helper (verbatim from skills/workflow-authoring/templates/h6-timeout-heartbeat.md, trimmed to what is used)
// ---------------------------------------------------------------------------------------------
function h6Receipt(endReason, label, ms, detail) { return { __h6: true, __endReason: endReason, label: label, ms: ms, detail: detail === undefined ? null : detail } }
function h6IsDrop(r) { return !!r && r.__h6 === true }
async function withTimeout(thunk, ms, label) {
  if (typeof setTimeout !== 'function') { try { return await thunk() } catch (err) { return h6Receipt('threw', label, ms, String((err && err.message) || err)) } }  // UNVERIFIED: timers in the sandbox
  let timer = null
  const expiry = new Promise(function (resolve) { timer = setTimeout(function () { resolve(h6Receipt('timeout', label, ms, null)) }, ms) })
  try { return await Promise.race([Promise.resolve().then(thunk), expiry]) }
  catch (err) { return h6Receipt('threw', label, ms, String((err && err.message) || err)) }
  finally { if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer) }
}

// ---------------------------------------------------------------------------------------------
// Pure helpers (D-19: algorithms, not agents)
// ---------------------------------------------------------------------------------------------
const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
const J = o => JSON.stringify(o, null, 1)
const cap = (s, n) => String(s === undefined || s === null ? '' : s).slice(0, n)      // string caps enforced in JS, not by maxLength
const fkey = f => (f.file || '') + '::' + String(f.title || '').toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim()
const fingerprint = fails => (fails || []).map(f => f.test + '|' + String(f.first_error_line || '').replace(/[0-9a-f]{7,40}/g, 'SHA').replace(/\d+/g, 'N').replace(/\/\S+/g, 'P').trim()).sort().join(';')
const ledgerKey = l => [l.role, l.mode, l.id, String(l.attempt)].join('|')
function redact(r, label) {                            // CG3: secret-shaped strings never enter a prompt, a ledger row or a report
  let hit = false
  const walk = (o, depth) => {
    if (depth > 6 || !o || typeof o !== 'object') return o
    for (const k of Object.keys(o)) {
      const v = o[k]
      if (typeof v === 'string') { if (SECRET_RE.test(v)) { hit = true; o[k] = v.replace(new RegExp(SECRET_RE.source, 'g'), '[REDACTED]') } }
      else if (typeof v === 'object') walk(v, depth + 1)
    }
    return o
  }
  walk(r, 0)
  if (hit) { log('SECRET-SHAPED STRING redacted in return of ' + label + ' (value never logged)'); r.__secret_redacted = true }
  return r
}
function topoOrder(cards) {
  const byKey = new Map(cards.map(c => [c.id, c])), out = [], state = new Map()
  const visit = id => {
    if (state.get(id) === 2) return
    if (state.get(id) === 1) throw new Error('dependency cycle at ' + id)
    const c = byKey.get(id); if (!c) throw new Error('unknown dependency ' + id)
    state.set(id, 1); for (const d of [...c.depends_on].sort()) visit(d); state.set(id, 2); out.push(c)
  }
  for (const c of [...cards].sort(byId)) visit(c.id)
  return out
}
function rankCards(cards) {                            // A2 §4d: rank = longest path to a sink in estimated minutes; deps strictly outrank dependents
  const by = new Map(cards.map(c => [c.id, c])), children = new Map(cards.map(c => [c.id, []]))
  for (const c of cards) for (const d of c.depends_on) if (children.has(d)) children.get(d).push(c.id)
  const memo = new Map()
  const rank = id => { if (memo.has(id)) return memo.get(id); const c = by.get(id); const own = (c.est_minutes || (c.size === 'M' ? 35 : 20)) + 14
    const r = own + Math.max(0, ...children.get(id).map(rank)); memo.set(id, r); return r }
  cards.forEach(c => rank(c.id)); return memo
}
const writeSet = c => new Set([...(c.files_allowed || []), ...(c.tests_allowed || []), ...(c.new_modules || []), ...(c.required_files || [])])
const byRank = rank => (a, b) => (rank.get(b.id) - rank.get(a.id)) || byId(a, b)         // C-24: (−rank, id) for scheduling AND integration order
function raiseLevels(items, textOf) {                  // A2/A1 (F-37): keyword-forced verification level, in code, at return time
  let raised = 0
  for (const it of items || []) if (STAGING_RE.test(textOf(it)) && String(it.verification_level || '').startsWith('local')) { it.verification_level = 'staging-required'; raised++ }
  return raised
}
function validateCards(cards) {                        // throws on a plan that cannot be built (A1 §13.1; D-1); called through checkPlan in EVERY stage (C-19)
  const ids = new Set(cards.map(c => c.id)); if (ids.size !== cards.length) throw new Error('duplicate card ids')
  for (const c of cards) {
    if (!/^(platform|product)-[0-9]{2}[a-d]?-[a-z0-9-]+$/.test(c.id)) throw new Error(c.id + ': bad id')
    if (!(c.step >= 1 && c.step <= 14)) throw new Error(c.id + ': step out of range')
    if (!c.dod.length || c.dod.length > 8 || c.dod.some(d => !d.command || d.command.length < 3)) throw new Error(c.id + ': dod must have 1..8 runnable lines')
    if (c.dod.some(d => /(^|\s)(-k|-x|--deselect|--ignore|--lf)(\s|=)|\|\|\s*true/.test(d.command))) throw new Error(c.id + ': a dod command narrows or masks pytest')
    if (c.size === 'L') throw new Error(c.id + ': size L is not a card')
    if ((c.size === 'S' && c.est_lines > 120) || (c.size === 'M' && c.est_lines > 300)) throw new Error(c.id + ': est_lines exceeds its size class (S ≤ 120, M ≤ 300)')
    if (c.protected_touch && c.id !== 'platform-01-gate') throw new Error(c.id + ': only platform-01-gate may touch protected paths')
    if (c.bootstrap) throw new Error(c.id + ': bootstrap must be false on every card (the profile exists only for the setup red-proof at base_sha)')
    const protHit = (c.tests_allowed || []).concat(c.files_allowed || [], c.new_modules || [], c.required_files || []).filter(p => PROTECTED.includes(p))
    const unowned = protHit.filter(p => !(MANIFEST_MIN[c.id] || []).includes(p))   // C-21: ownership, not a 01-only ban — a card may write a protected path its MANIFEST_MIN declares
    if (unowned.length && !c.protected_touch) throw new Error(c.id + ': write set intersects the protected list outside its owner manifest (' + unowned.join(',') + ') without protected_touch (C-21)')
    if ((c.expected_green_tests || []).some(t => !/^[A-Za-z0-9_.\/-]+::[A-Za-z0-9_\[\]-]+$/.test(t))) throw new Error(c.id + ': expected_green_tests must be module::name ids')
    if (c.finding_ids.some(f => !f.corrected_text || f.corrected_text.length < 20)) throw new Error(c.id + ': every cited finding must carry its CORRECTED text (F-10)')
    if (c.risk === 'security' && !c.dod.some(d => /surface|operator|flag|unreachable/i.test(d.expect + ' ' + d.command))) throw new Error(c.id + ': a security card needs a surface/operator-flag DoD line (G-15 point 5)')
    if (MANIFEST_MIN[c.id]) { const miss = MANIFEST_MIN[c.id].filter(p => !reqFiles(c).includes(p) && !(c.files_allowed || []).includes(p)); if (miss.length) throw new Error(c.id + ': required-files manifest not declared by the card (' + miss.join(',') + ') — new_modules/required_files must cover MANIFEST_MIN (C-14)') }
    for (const pre of ['platform-04-streamparser:fixture1_path', 'product-13b-personas-readme:persona_boundary_fixture_path', 'platform-08c-worker-checkpoint:worker_checkpoint_decision']) { const [id, field] = pre.split(':'); if (c.id === id && c.owner_precondition !== field) throw new Error(c.id + ': owner_precondition must be ' + field) }
    raiseLevels(c.dod, d => d.command + ' ' + d.expect)
  }
  topoOrder(cards)
}
function checkPlan(idx, preverified) {                 // C-19: the plan-level checks, run in EVERY stage; returns defects[] (R0 records them, R1+ throws)
  const defects = []
  try { validateCards(idx.cards) } catch (e) { defects.push(String(e.message)) }
  for (const id of AGAINST) { const row = (idx.decisions || []).find(d => d.id === id); if (!row || row.against_recommendation !== true) defects.push('decision ' + id + ' must be marked against_recommendation (F-9)') }
  const refuted = new Set((preverified || []).filter(p => p.verdict === 'refuted').map(p => p.id))
  idx.cards.forEach(c => c.finding_ids.forEach(f => { if (refuted.has(f.id)) defects.push(c.id + ' cites REFUTED finding ' + f.id) }))
  for (const cid of Object.keys(MANIFEST_MIN)) if (!idx.cards.some(c => c.id === cid)) defects.push('required-files manifest names card ' + cid + ' which the plan lacks')
  if ((idx.unmapped_finding_ids || []).length) defects.push('unmapped findings: ' + idx.unmapped_finding_ids.join(','))
  return defects
}
function assertCommon(r, what) {                       // F-1, F-5, F-35: script-level invariants on every return
  if (!r || h6IsDrop(r) || r.status === 'null') return r
  const top = r.repo_toplevel || '', cdir = r.git_common_dir || ''
  if (top && !(top === R || top.startsWith(WT + '/'))) { log('BLOCK ' + what + ': worked in ' + top); return { status: 'null', reason: 'wrong-repo' } }          // D1: prefix test — sibling worktrees pass
  if (cdir && cdir !== R + '/.git') { log('BLOCK ' + what + ': common dir ' + cdir); return { status: 'null', reason: 'wrong-store' } }
  if ((r.outward_actions_taken || []).length) { HALT = 'outward-action:' + what; log('HALT ' + HALT + ': ' + r.outward_actions_taken.join(',') + ' — no further agents; synthesizer still runs'); return { status: 'null', reason: 'outward-action' } }
  if ((r.installed_packages || []).length) { log('BLOCK ' + what + ': installed ' + r.installed_packages.join(',')); return { status: 'null', reason: 'installed-packages' } }
  const rc = RECEIPT_RE.exec(r.notes || '') || RECEIPT_RE.exec(r.strongest_disagreement || '')
  if (rc) log('NOTE ' + what + ': receipt-shaped fragment (matched "' + rc[0] + '") — logged only, the return stands (C-23)')   // v2.1 V-1: LOG-ONLY — a receipt phrase never nulls the card; §9 / §12.2 AP-1 / §12.7 V-22 are the law and assertCommon now agrees
  return r
}

// ---------------------------------------------------------------------------------------------
// The single agent wrapper: ledger for every call, one narrower retry on null, typed results (F-41, F-42),
// early halt on budget exhaustion or an outward action (CG), secret redaction (CG3), sorted ledger keys
// ---------------------------------------------------------------------------------------------
const ledger = []; let agentCount = 0, HALT = null
function budgetOk(label, exemptFromHalt) {
  if (agentCount >= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN)) { log('AGENT CAP: ' + agentCount + ' >= ' + Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) + ' before ' + label); return false }
  if (exemptFromHalt) return true                                   // C-7/F-45: the synthesizer runs after every HALT and even on an exhausted budget — that reserve is what it is FOR
  if (HALT) { log('HALTED (' + HALT + ') before ' + label); return false }
  if (!budget.total) return true
  const ok = budget.remaining() > RESERVE; if (!ok) log('BUDGET GUARD before ' + label + ': remaining ' + budget.remaining() + ' < reserve ' + RESERVE)
  return ok
}
function agentsOk(label, need) {                       // A2 §13: per-chain reservation so a wave never starts a chain it cannot finish inside this invocation
  const ok = agentCount + need <= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN)
  if (!ok) log('AGENT SLICE: ' + label + ' needs ' + need + ' agents; ' + agentCount + ' used of ' + Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) + ' — deferred to the next invocation')
  return ok
}
async function run(role, mode, id, prompt, opts, enqueued) {
  const label = role + ':' + mode + ':' + id, ms = tmo(mode, enqueued)
  for (let attempt = 1; attempt <= 2; attempt++) {
    if (!budgetOk(label, role === 'synthesizer')) { const why = HALT && role !== 'synthesizer' ? 'halt' : (agentCount >= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) ? 'agent-slice' : 'budget'); ledger.push({ role, mode, id, attempt, status: why }); return { status: 'null', reason: why } }
    agentCount++
    const p = attempt === 1 ? prompt : prompt + '\n' + NARROW + '\nattempt: 2'     // attempt suffix → cache miss by construction (F-43)
    const r = await withTimeout(() => agent(p, Object.assign({ label: label + (attempt === 2 ? ':retry' : '') }, opts)), ms, label)
    if (r && !h6IsDrop(r)) {
      redact(r, label)
      ledger.push({ role, mode, id, attempt, status: r.status || r.verdict || 'ok', sha: r.head_sha || r.sha || r.tests_head || null })
      return assertCommon(r, label)
    }
    const why = r ? (r.__endReason === 'timeout' ? 'timeout-or-dialog' : r.__endReason) : 'null', detail = r ? cap(r.detail, 200) : null   // C-37: the promised label
    ledger.push({ role, mode, id, attempt, status: why, detail })
    if (why === 'threw' && /budget|ceiling|spent/i.test(String(detail))) { HALT = 'budget-exhausted'; log('HALT budget-exhausted at ' + label + ' — no retries, loops wind down, synthesizer runs'); return { status: 'null', reason: 'halt' } }
    if (why === 'timeout-or-dialog') REPLAY_RISK = true   // CG: a timed-out call may still journal a result; cache resume would diverge → next_args.resume_mode = 'git'
    log('DROP ' + label + ' attempt ' + attempt + ': ' + why + (attempt === 1 ? ' — retrying narrower' : ' — parking'))
  }
  return { status: 'null', reason: 'agent-null' }
}
let REPLAY_RISK = false

// SCHEMAS: §9 pasted verbatim here (LEVELS, COMMON, COMMON_REQ, CMD, GATE_STEP, ROW_STATE, SETUP, CARD, CARD_INDEX, TESTS, BUILD, FINDING, VERDICT, MERGE, REPORT).

// ---------------------------------------------------------------------------------------------
// Prompt builders (pure functions of args + sorted results; the sha pins the cache)
// ---------------------------------------------------------------------------------------------
const testsBranch = id => 'tests/' + id + '-' + A.run_nonce
const taskBranch = id => 'task/' + id + '-' + A.run_nonce          // ONE helper for every merged branch — journeys use it too (J2 A3-1)
const cardPath = c => c.path || 'plan/cards/' + c.id + '.json'
const cardRef = c => 'CARD: ' + R + '/' + cardPath(c) + ' (plan sha ' + A.plan_sha + '; plan/ is merged into ' + INTEG + ' so the file is in every worktree' + (c.finding ? '; this is a REVIEW FIX CARD written by the integrator to plan/fixes/' : '') + '). CARD CONTENT (verbatim from that file): ' + J({ id: c.id, files_allowed: [...(c.files_allowed || [])].sort(), new_modules: [...(c.new_modules || [])].sort(), required_files: [...(c.required_files || [])].sort(), tests_allowed: [...(c.tests_allowed || [])].sort(), expected_green_tests: [...(c.expected_green_tests || [])].sort(), xfail_allowed: [...(c.xfail_allowed || [])].sort(), dod: c.dod, finding_ids: c.finding_ids, risk: c.risk, owner_precondition: c.owner_precondition }) + (c.finding ? '\nFINDING (confirmed by an independent refuter): ' + J({ id: c.finding.id, title: c.finding.title, file: c.finding.file, severity: c.finding.severity, kind: c.finding.kind, corrected_claim: cap(c.finding.corrected_claim, 600), fix_hint: cap(c.finding.fix_hint, 400), reproduction: c.finding.reproduction }) : '') + '\nDECISIONS: plan/decisions.json. API LEDGER: plan/api-ledger.json. PRE-VERIFIED FINDINGS: plan/preverified.json.'
const PINS = ' --gate-sha256 ' + A.gate_sha256 + ' --baseline ' + A.baseline_path + ' --baseline-sha256 ' + A.baseline_sha256 + ' --libsrc ' + A.libsrc
const gateCmd = extra => 'VENV=' + A.venv + ' bash ' + A.gate_sh + PINS + ' ' + extra
const redriveLine = k => (k ? '\nredrive: ' + k : '')                 // D4: a stale re-drive is a different prompt → cache miss by construction
const boundaryArg = () => (OA.persona_boundary_fixture_sha256 && isHex64(OA.persona_boundary_fixture_sha256) ? ' --boundary-sha256 ' + OA.persona_boundary_fixture_sha256 : '')
function mergedArgs(mergedIds) {                                     // --require / --xfail-allow / --tests-removed for gates on trees that contain merged cards (C-14: from the cards)
  const ids = [...mergedIds].sort()
  const cards = ids.map(id => CARD_BY_ID.get(id)).filter(Boolean)
  const req = [...new Set(cards.flatMap(reqFiles))].sort()
  const xf = [...new Set(cards.flatMap(c => c.xfail_allowed || []))].sort(), removed = cards.reduce((n, c) => n + (c.tests_removed_expected || 0), 0)
  return (req.length ? ' --require ' + req.join(',') : '') + (xf.length ? ' --xfail-allow ' + xf.join(',') : '') + (removed ? ' --tests-removed ' + removed : '') + boundaryArg()
}
const CARD_BY_ID = new Map()
const P = {
  setup: () => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:setup (idempotent) + the live state probe of this invocation (launched_at ' + (A.resume_mode === 'git' ? A.launched_at : 'n/a') + '). Ensure and report:',
    '(1) ' + R + ' is a clone of the read-only snapshot ' + A.snapshot_dir + ' whose first commit is ' + A.base_sha + ' (create it if missing; never modify the snapshot; `chmod -R a-w` the snapshot and ' + A.libsrc + ');',
    '(2) the venv ' + A.venv + ' EXISTS (P0 created it; `python -V` must be 3.12.*; NEVER create it or install anything — report status FAILED if absent); report nproc;',
    '(3) sha256sum of ' + A.gate_sh + ' and of ' + A.baseline_path + ' (both created at P0; report both — the script compares them to args; never create or rewrite either);',
    '(4) BROKEN_SHA=' + A.base_sha + ' run ' + gateCmd('--self-test --profile bootstrap --base ' + A.base_sha) + ' in a detached worktree at ' + A.base_sha + ' and report red_proof {broken_red, false_claim_red, digest};',
    A.stage === 'plan' ? '(5) branch ' + PLAN_BRANCH + ' exists or is created at ' + A.base_sha + ';' : '(5) branch ' + INTEG + ' exists (create at ' + A.base_sha + ' if missing) and ' + PLAN_BRANCH + ' at ' + A.plan_sha + ' is merged into it (`git merge --no-ff ' + A.plan_sha + '` as its first commit if not yet; plan/** only); report plan_merged and integration_head_live (40-hex);',
    '(6) report branch_heads for every tests/*-' + A.run_nonce + ' and task/*-' + A.run_nonce + ' branch, merged_on_integration from `git ls-tree ' + INTEG + ' plan/status/` (ids whose json says merged), and `git remote -v` lines (expected: none);',
    '(7) if ' + (A.prior_status_path || 'no prior status file') + ' exists, return its rows (task_id, state, head_sha, reason) as prior_rows and its seen_keys; else [] and [];',
    '(8) `git -C ' + R + ' worktree prune`; remove worktrees under ' + WT + ' whose branch is already merged into ' + INTEG + '; mkdir -p ' + BUNDLES + ' ' + GRILL + '/build-bundles/' + A.run_nonce + ';',
    '(9) report toolchain_status_sha256 = sha256 of `' + TOOLCHAIN_STATUS_CMD + '` (must equal ' + A.toolchain_status_sha256 + '; docs/grills is excluded because the owner\'s sync loop writes there) — report base_sha_ok=false if any assertion fails. Never install into any interpreter.'].join('\n'),
  preverify: fid => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:preverify (refute-first). Finding ' + fid + ' in ' + A.findings_path + ' is UNVERIFIED. Reproduce or refute it at ' + A.base_sha + ' in a detached worktree of ' + R + ' with a probe mechanically different from the finder\'s (the finder read source; you execute: render the chat template with jinja2, run the code path with a fake, diff the checkpoint index — whatever applies). Never print environment variables; never call any URL. Return verdict holds|refuted|unverified with the executed reproduction, corrected_claim, and verification_level; findings[0] carries the result.'].join('\n'),
  apiLedger: () => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:api-ledger. In a worktree of ' + R + ' on branch ' + PLAN_BRANCH + ' (create ' + WT + '/apiledger-' + A.run_nonce + ' with `git -C ' + R + ' worktree add`), from ' + A.libsrc + ' ONLY (gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0, gradio_client 2.6.1) write plan/api-ledger.json: every symbol the design §4.2 cards need with module, symbol, kwargs, libsrc path:line (≥ 30 entries: gr.Blocks/ChatInterface/Chatbot/mount_gradio_app/api, spaces.GPU(size=,duration=), GenerationConfig fields incl. max_time and the ABSENCE of presence_penalty, continue_final_message bool|str, HfApi.restart_space/duplicate_repo/fetch_space_logs/wait_for_space, gradio_client.Client) plus known_bad[] as regexes with why and libsrc anchor: gr.Chatbot(type=…), gr.ChatInterface(type=…), @spaces.GPU(gpu_size=…), presence_penalty to generate, restart_space(revision=…), from gradio.client import, Path.read_text(newline=…), preexec_fn=, trust_remote_code=True, prefill_chunk_size with the VLM class, continue_final_message for thinking resumes. Commit on ' + PLAN_BRANCH + ', remove the worktree, and return VERDICT (mode plan, verdict pass, sha = that commit, checks[] listing the files written, hunks_cited = the ledger path@sha).'].join('\n'),
  catalog: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:catalog (read-only Hub reads via ToolSearch: hub_repo_details / hf_fs cat of model.safetensors.index.json and config.json). For each candidate in ' + J(A.catalog_candidates) + ' save the RAW response under ' + GRILL + '/evidence/catalog/<owner>__<name>.json with fetched_at, record revision (40-hex), inferenceProviderMapping, has_visual_tensors (any weight key starting with model.visual.), quant format; on any fetch failure after 3 tries record status unresolved for that entry — never a remembered value. (Card product-13a-catalog later copies these files into the repo at evidence/catalog/ so the gate and CI can read saved_path.) Return VERDICT with findings[] one per candidate (kind omitted-obligation, verification_level local-mechanical, reproduction = the tool call you made and the saved path).'].join('\n'),
  plan: (pre, defects) => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:plan. Inputs: ' + A.decision_queue_path + ' (Resolved decisions ONLY — decided values, never recommendations; record the DQ line number of each), ' + A.lens4_path + ' (§B layout, §C duplication list, §D 14 steps, §E ship-but-flag, §F pins), ' + A.findings_path + ' (use ONLY the CORRECTED CLAIM / CORRECTED RECOMMENDATION lines), ' + A.redteam_path + ' §1-§3, plan/api-ledger.json, and these pre-verified findings (a REFUTED id must not become a card; an UNVERIFIED one may only be cited at verification_level unverified):', J(pre),
    defects && defects.length ? 'REPAIR MODE: the previous plan on ' + PLAN_BRANCH + ' was rejected by the script for these defects — fix every one, keep everything else, commit on the same branch:\n' + J(defects) : '',
    'On branch ' + PLAN_BRANCH + ' write: plan/decisions.json (one row per G-/M- id and per clarification the design §4.0 lists: id, decided_value, against_recommendation, consequences[], dq_line; the ids ' + J(AGAINST) + ' are against_recommendation=true); plan/preverified.json (the list above); plan/cards/<id>.json for the design §4.2 split (22 cards, S/M only, path, files_allowed/tests_allowed/new_modules/required_files (together they must cover the design\'s MANIFEST_MIN for that card)/deps_allowed/xfail_allowed (lens-4 §F known-bads only)/expected_green_tests (characterisation pins and contract tests that are green on the old tree BY DESIGN — nothing else)/tests_removed_expected/est_lines (S ≤ 120, M ≤ 300)/est_minutes, dod[] ≤ 8 runnable CPU commands with expect and verification_level, risk, protected_touch only on platform-01-gate, bootstrap false everywhere, decision_ids, finding_ids with corrected_text, apis_expected, owner_precondition: fixture1_path on platform-04-streamparser, persona_boundary_fixture_path on product-13b-personas-readme, worker_checkpoint_decision on platform-08c-worker-checkpoint); plan/index.json (cards + decisions + preverified); AGENTS.md (this preamble + gate usage). Locate code by symbol (`git grep -n "def <name>"`), never by line. Card platform-01-gate (size M) delivers the config.py skeleton with every §4.6 default, tools/stubs, tools/make_boundary_fixture.py, the false-claim fixture pair, pytest.ini registering `journey:` under markers, and tests/journeys/conftest.py pinned BYTE-FOR-BYTE to:\nimport pathlib\nimport pytest\n\ndef pytest_collection_modifyitems(config, items):\n    for it in items:\n        if it.path.is_relative_to(pathlib.Path(__file__).parent):\n            it.add_marker(pytest.mark.journey)\n(a PATH-SCOPED, SELF-CONTAINED hook — it imports its own pytest: a conftest naming pytest without importing it is ruff F821 and NameErrors at collection — while a bare pytestmark in a conftest is inert (pytest reads pytestmark only from test modules) and an unscoped hook marks every item in the session, so -m "not journey" deselects the whole default suite; all three dead ends are RED, caught here at card 01). Card 01\'s dod must include a BOTH-collections line: the gate with --journeys over a one-file smoke journey under tests/journeys/ AND the default suite, both green. Card platform-05a-registry quotes G-15 point (5) verbatim. Cards 08a/08b quote the token-level continuation (gpu-lease-3 CORRECTED + critic-4), the VLM-class precondition (inference-perf-2/-5/-7 CORRECTED), the find_spec probe (inference-perf-4 CORRECTED) and the presence_penalty decision (' + (A.torch_in_venv ? 'torch IS in the venv: worker/penalty.py with a CPU test' : 'torch is NOT in the venv: remove the placebo; API 400 unless 0') + '). The persona card lists only the G-19 role names and forbids reading system_prompt.py history. Commit and return CARD_INDEX (decisions[] echoes the sheet rows; preverified[] echoes plan/preverified.json).'].join('\n'),
  planCheck: idx => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:plan (refute-first). Read every card under ' + R + '/plan/cards at ' + idx.plan_sha + ', plan/decisions.json and plan/preverified.json. REFUTE: (a) any DoD command that is not runnable on CPU under the venv (run it — it may fail, it must not be unrunnable); (b) any card whose text contradicts a decided value or quotes an original recommendation instead of the CORRECTED line; (c) any decision row whose decided_value or dq_line does not match ' + A.decision_queue_path + '; (d) any confirmed finding id no card cites, any REFUTED id a card cites; (e) any staging/quota/lease claim at a local verification_level; (f) any xfail_allowed id that is not a lens-4 §F known-bad; (g) any lens-4 §C duplication item without a DoD line on some card; (h) any expected_green_tests id that is not a characterisation pin (lens-4 §F) or a contract test green on the old tree by construction; (i) any card whose est_lines exceeds its size class. Return findings with reproduction (the command you ran) and verdict pass|fail.'].join('\n'),
  index: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence. Read ' + R + '/plan/index.json, plan/decisions.json and plan/preverified.json at ' + A.plan_sha + ' and return them as the `cards`, `decisions` and `preverified` arrays of CARD_INDEX (no changes); status FAILED if the sha or a file is missing.'].join('\n'),
  author: (c, base, k, rd, redInfo) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:tests for ' + c.id + ' (attempt ' + k + '). ' + cardRef(c), 'Base: ' + base + '. Create worktree ' + WT + '/tests-' + c.id + '-' + A.run_nonce + ' on NEW branch ' + testsBranch(c.id) + ' from the base (if the branch exists and its tests already exist, verify them and return status reused).',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: create the worktree as a history-free clone instead: `git clone --depth 1 --single-branch --branch ' + INTEG + ' file://' + R + ' ' + WT + '/tests-' + c.id + '-' + A.run_nonce + '` at ' + base + ', commit there, then `git -C "' + R + '" fetch "' + WT + '/tests-' + c.id + '-' + A.run_nonce + '" HEAD:refs/heads/' + testsBranch(c.id) + '`. FIXTURE COPY STEP: copy the owner-generated file ' + (OA.persona_boundary_fixture_path || '<owner_approvals.persona_boundary_fixture_path>') + ' verbatim to tests/fixtures/persona_boundary.json (its sha256 must equal ' + (OA.persona_boundary_fixture_sha256 || '<owner_approvals.persona_boundary_fixture_sha256>') + '; the gate pins it) and commit it with the tests. The absence test reads ONLY that fixture (hashed 6-word shingles) and asserts no persona text shingle matches; it never contains or reads the excluded clause.' : '',
    'Write ONLY the tests that prove the card\'s DoD lines (files listed in tests_allowed, or new files under tests/); no implementation code; never modify a protected path this card\'s own manifest does not declare (the PROTECTED list / tests-protected.txt — only platform-01-gate carries protected_touch); xfail/skip markers only for ids in the card\'s xfail_allowed. Every new test must be RED on the base for the expected reason (assertion / NotImplemented, or ImportError only for modules in new_modules) EXCEPT the ids listed in expected_green_tests, which must be green (they characterise the old tree). Commit "tests(' + c.id + '): …" with trailer "Card: ' + c.id + '". Run ' + gateCmd('--only-tests <your test paths> --card ' + cardPath(c) + ' --base ' + base) + ' on the committed, clean tree and quote its confirm-red line, its exit code as gate_exit_code, and its LEDGER_DIGEST; suggest up to 3 one-line mutants (file, find, replace) in files_allowed that your tests should catch. Remove your worktree (branch survives).',
    redInfo ? 'PREVIOUS ATTEMPT REJECTED by the independent red verifier — do not return the same tests: ' + J(redInfo) : '', redriveLine(rd)].join('\n'),
  red: (c, t, base, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:red for ' + c.id + '. ' + cardRef(c), 'Detached worktree ' + WT + '/red-' + c.id + '-' + A.run_nonce + ' at ' + t.tests_head + '. Run ' + gateCmd('--only-tests ' + t.test_paths.join(' ') + ' --card ' + cardPath(c) + ' --base ' + base) + ' yourself (return its LEDGER_DIGEST as gate_digest — it must equal the author\'s) and `pytest --collect-only -q` on the rest of the suite. verdict pass ONLY if the gate\'s confirm-red step is green: every new test fails for the expected reason (rc 1 or 2; not SyntaxError; ImportError only for new_modules; not rc 5) except the expected_green_tests, which are green, and the author-tamper step is green. Remove the worktree.' + redriveLine(rd)].join('\n'),
  build: (c, t, base, k, fails, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: builder mode:' + (fails ? 'fix' : 'implement') + ' for ' + c.id + ' (build call ' + k + '/' + MAX_BUILD + '). ' + cardRef(c),
    'Branch ' + taskBranch(c.id) + (fails ? ' already exists: worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + '-fix' + k + ' on it' : ': create worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + ' on that NEW branch from ' + testsBranch(c.id) + ' (head ' + t.tests_head + '); if the branch already exists and is green on the card\'s DoD, report status reused') + '.',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: use a history-free clone (`git clone --depth 1 --single-branch --branch ' + testsBranch(c.id) + ' file://' + R + ' <worktree>`) and `git -C "' + R + '" fetch <worktree> HEAD:refs/heads/' + taskBranch(c.id) + '` when done.' : '',
    'Make the card\'s tests pass by implementing exactly the card (files_allowed/new_modules/required_files only; you may ADD tests under tests/unit/ but never modify or delete an existing test; never touch plan/). Every gradio/spaces/transformers/huggingface_hub call must cite plan/api-ledger.json (apis_used[].ledger_ref) — never memory. Commit per coherent step; each message has a "Claims:" block naming symbols/files that ARE in that diff, and trailer "Card: ' + c.id + '". Run every DoD command, then run the gate LAST, at your final commit, on a clean tree (`git status --porcelain` empty — the gate refuses a dirty tree): ' + gateCmd('--card ' + cardPath(c) + ' --base ' + t.tests_head + ' --oracle ' + t.tests_head + mergedArgs(mergedIds)) + ' (advisory; return its LEDGER_DIGEST as gate_digest, its profile, and its steps[] {name, exit_code} as gate_steps). Return head_sha, dod[] with one row per card DoD id and exit codes, apis_used[], changed_files. Remove your worktree at the end.',
    fails ? 'FAILING EVIDENCE (typed, from an independent verifier; fix the cause, never the test):\n' + J(fails) : '', redriveLine(rd)].join('\n'),
  verify: (c, t, b, k, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:verify for ' + c.id + ' (verify ' + k + '). ' + cardRef(c), 'Detached worktree ' + WT + '/verify-' + c.id + '-' + A.run_nonce + '-' + k + ' at ' + b.head_sha + '. Do NOT trust the builder: (1) run EXACTLY ' + gateCmd('--card ' + cardPath(c) + ' --base ' + t.tests_head + ' --oracle ' + t.tests_head + mergedArgs(mergedIds)) + ' yourself and return its LEDGER_DIGEST as gate_digest, its LEDGER_SHA256, the head_sha in the ledger, the profile, IDIOM_HITS as idiom_hits, its steps[] as gate_steps, its LEDGER_DIFF_STATS as diff_stats (required), its apicheck_unresolvable[] and `sha256sum ' + A.gate_sh + '` as gate_sha256_observed;',
    '(1b) SEPARATELY: write .gate/card-' + c.id + '.json = the card with apis_expected extended by the builder-reported APIS_USED below and run ' + gateCmd('--apicheck .gate/card-' + c.id + '.json --base ' + t.tests_head + ' --out .gate/apicheck-' + c.id + '.json') + ' — record it in checks[] as name "apicheck-extended" (this run has its own ledger and never changes the digest of (1)); APIS_USED: ' + J([...(b.apis_used || [])].sort((x, y) => (x.module + x.symbol < y.module + y.symbol ? -1 : 1))) + '; (2) re-run every DoD command (dod_reruns[] one per card DoD id); (3) read `git diff ' + t.tests_head + '..' + b.head_sha + '` and cite hunks; (4) write .gate/mutants/' + c.id + '.json ({"tests":[the author\'s test paths],"mutants":[3 one-line breaks inside files_allowed that the card\'s tests must catch; start from the author\'s suggestions if any]}) and run ' + gateCmd('--mutants .gate/mutants/' + c.id + '.json --tests ' + t.test_paths.join(',') + ' --out .gate/mutants-' + c.id + '.json') + ' (written ≥ 1, ALL killed); (5) run ' + gateCmd('--revert-proof ' + t.tests_head + ' --tests ' + [...new Set(t.test_paths.concat((b.changed_files || []).filter(f => /^tests\/unit\/.*\.py$/.test(f))))].sort().join(',') + ' --out .gate/revert-' + c.id + '.json') + ' (the author\'s tests plus the builder-added tests/unit files) and report revert_proof.observed;',
    '(6) clear every idiom-lint warning by idiom with a reason, or fail; (7) verdict fail on ANY failure, on a bootstrap profile, on collected 0, on a missing DoD row. Default to fail when uncertain; state your strongest disagreement even on pass. Remove the worktree.' + redriveLine(rd)].join('\n'),
  merge: (c, b, head, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:merge (single writer of ' + INTEG + '). In ' + R + ': ensure ' + INTEG + ' is at ' + head + '; if ' + b.head_sha + ' is already an ancestor (`git merge-base --is-ancestor`; exit 128 = unknown → status missing-ref) run ' + gateCmd('--base ' + head + '~1 --journeys' + mergedArgs([...mergedIds, c.id])) + ' at the CURRENT head and return status already-merged with head_sha = ' + head + ' (the head never moves on already-merged), its LEDGER_DIGEST, exit code, and the cherry/patch-id assertions; else `git merge --no-ff ' + taskBranch(c.id) + '` (head ' + b.head_sha + '). If the ref is missing → status missing-ref. On ANY conflict: `git merge --abort`, return status conflict with the hunks (ours/theirs) — do not resolve.',
    'On a clean merge: record the merge commit as merge_sha; run ' + gateCmd('--base ' + head + ' --journeys' + mergedArgs([...mergedIds, c.id])) + ' (the journeys, when present, run at every merge); if red → `git revert -m 1 <merge_sha>` immediately and return status reverted with merge_sha and the ledger; if green → assert `git cherry ' + INTEG + ' ' + taskBranch(c.id) + '` is empty and every `git patch-id` of the task commits appears in ' + head + '..HEAD; write plan/status/' + c.id + '.json {state:"merged", head_sha, merge_sha, gate_digest} and commit "status(' + c.id + '): merged"; `git bundle create ' + BUNDLES + '/' + c.id + '.bundle ' + head + '..' + INTEG + '` (incremental) and append {id, path, sha256, bytes} to ' + BUNDLE_MANIFEST + '; remove worktrees of ' + taskBranch(c.id) + ' and ' + testsBranch(c.id) + '; return status merged + head_sha (after the status commit) + merge_sha + LEDGER_DIGEST as gate_digest + gate_sha256_observed + journeys {collected, failed, skipped_needs[]} from the ledger + `git remote -v` lines.'].join('\n'),
  conflict: (c, b, head, hunks) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:conflict (fresh). `git -C ' + R + ' worktree add --detach ' + WT + '/conflict-' + c.id + '-' + A.run_nonce + ' ' + head + '` (detached: ' + INTEG + ' is checked out in ' + R + '). Merge ' + taskBranch(c.id) + ' (' + b.head_sha + ') resolving ONLY these hunks so that this card\'s DoD AND the already-merged cards still hold; run ' + gateCmd('--base ' + head + ' --journeys') + '; commit the merge; return head_sha = merge_sha = that commit + LEDGER_DIGEST (status merged) or gate-red. ' + cardRef(c), 'HUNKS:', J(hunks)].join('\n'),
  ff: (c, sha, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:ff. Fast-forward ' + INTEG + ' in ' + R + ' to ' + sha + ' (a merge commit made in a worktree; merge_sha = ' + sha + '); run ' + gateCmd('--base ' + sha + '~1 --journeys' + mergedArgs([...mergedIds, c.id])) + '; cherry/patch-id assertions for ' + taskBranch(c.id) + '; write plan/status/' + c.id + '.json and commit; bundle to ' + BUNDLES + '/' + c.id + '.bundle and append to ' + BUNDLE_MANIFEST + '; return status merged + head_sha + merge_sha + LEDGER_DIGEST + journeys from the ledger.'].join('\n'),
  revert: (id, head, mergeSha, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:revert (single writer of ' + INTEG + '). In ' + R + ' on ' + INTEG + ' at ' + head + ': `git revert -m 1 ' + mergeSha + '` (the merge commit of ' + id + '; also remove plan/status/' + id + '.json in the same commit if it exists); run ' + gateCmd('--base ' + head + ' --journeys' + mergedArgs(mergedIds)) + ' on the result; return status merged with the new head_sha (merge_sha = "") and LEDGER_DIGEST when the gate is green, else status gate-red with the ledger. Do nothing else.'].join('\n'),
  fixcards: (cards, head, round) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:fixcards (single writer of ' + INTEG + '). In ' + R + ' on ' + INTEG + ' at ' + head + ': write each of these review fix cards VERBATIM to its path (plan/fixes/ is the mutable area for review fix cards; plan/cards/ stays immutable), commit them together as "plan(fixes): review round ' + round + '" and return status written, head_sha (the new head) and files_written[] (every path). CARDS: ' + J(cards.map(c => ({ path: cardPath(c), content: Object.assign({}, c, { finding: undefined }) })))].join('\n'),
  clean: (w, head, mergedIds, lintBase) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:clean-gate for wave ' + w + '. `git -C ' + R + ' worktree add --detach ' + WT + '/clean-w' + w + '-' + A.run_nonce + ' ' + head + '`; inside it run BROKEN_SHA=' + A.base_sha + ' ' + gateCmd('--clean --self-test --journeys --base ' + A.base_sha + ' --lint-base ' + lintBase + mergedArgs(mergedIds)) + ' (full suite twice, conformance on the fake backend, journeys with needs= skips counted, README check, red-proofs, gate integrity); return LEDGER_DIGEST as gate_digest, head_sha, journeys {collected, failed, skipped_needs[]}, self_test {broken_red, false_claim_red} from the ledger, gate_exit_code, gate_sha256_observed, `git -C ' + R + ' remote -v` lines and `git -C ' + R + ' branch --list | wc -l` as branch_count; remove the worktree. Also report toolchain_status_sha256 = sha256 of `' + TOOLCHAIN_STATUS_CMD + '` (must equal ' + A.toolchain_status_sha256 + ').'].join('\n'),
  journeys: (tag, head, seams) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:journeys (' + tag + ') at ' + head + '. Seams whose card merged this wave: ' + seams.join(', ') + '. On NEW branch ' + taskBranch('journeys-' + tag) + ' from ' + head + ' write composition tests under tests/journeys/ (tests/journeys/conftest.py from card 01 marks them `journey`; they are deselected from every default pytest run and selected only by gate.sh --journeys) for those seams (H1 tool loop × streaming × Continue at TOKEN level: turn 2 contains turn 1\'s tool results, finish_reason length → Continue resumes from prefix_ids; H2 /v1 × identity: x-ip-token bound inside the generator body, 429 on the non-blocking semaphore; H3 MCP ask→poll→status→preflight with chat hidden; H4 python_eval × operator flag × every surface: UI checkbox alone cannot enable it, unreachable over /v1 and MCP; H5 catalog admission × models.yaml schema × harness zero-call × pending entries hidden; H6 session isolation × TTL sweep × no rmtree on unload; H7 error taxonomy quota/illegal-duration/abort → titled notice in UI, {"error":…} event on /v1, partial text kept; J1 QWEN_STUB=1 boot serves UI + /healthz{git_sha from build_info.json} in < 10 s on a free port). Each journey that needs an unmerged card is marked `pytest.mark.skip(reason="needs=<card-id>")` — no other skip reason is allowed. Commit, run ' + gateCmd('--only-tests tests/journeys --base ' + head) + ' (composition tests are allowed to be green; the step journeys-only-tests reports them), return its LEDGER_DIGEST as gate_digest and its exit code as gate_exit_code (must be 0), plus tests_head and test_paths — a red journeys-only run is refused by the script, never merged.'].join('\n'),
  review: (lens, head, seenKeys, round) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:review, lens ' + lens + ', round ' + round + '. Branch ' + INTEG + ' at ' + head + ' in a detached worktree ' + WT + '/review-' + lens + '-r' + round + '-' + A.run_nonce + '. Read plan/decisions.json, plan/index.json and `git diff ' + A.base_sha + '..' + head + '` (use --color-moved to skip pure moves).',
    'Report ONLY problems that affect correctness, a decided value, scope, test integrity, security or secrets — each with a reproduction at ' + head + ' whose command EXITS NON-ZERO while the defect exists and 0 once it is fixed (e.g. `! grep -q …`, a pytest invocation, a python -c assertion; never a bare `grep` that exits 0 on a hit), plus a files_allowed[] for its fix; no style findings. List probes_used[] (the commands/angles you used). Known finding keys to skip: ' + J(seenKeys) + '. Remove the worktree.'].join('\n'),
  refute: (f, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:refute. Try to REFUTE this finding at ' + head + ' in a detached worktree; default to refuted if uncertain; holds ONLY with a reproduction you executed whose command exits NON-ZERO on the defect (and would exit 0 once fixed) — rewrite the command if the reviewer\'s does not have that shape. Return the finding back as findings[0] with your corrected_claim.', J(f)].join('\n'),
  veto: (head, rows, last, probes) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:veto (you may only VETO with a reproduction; you can never approve). ' + INTEG + ' at ' + head + '. Inputs: plan/decisions.json, plan/index.json, the clean-gate ledger, and this status table: ' + J(rows), last ? 'LAST ROUND MANDATE (DoD inversion): start from the decided values and the cards; independently try to falsify every claimed end-state or find an omitted obligation; you may NOT reuse these probes: ' + J(probes) : 'Cite hunks; each veto is a finding with a reproduction (non-zero exit on the defect); otherwise return verdict no-veto with your strongest disagreement.'].join('\n'),
  evidence: (dir, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence for stage ' + A.stage + '. Read ONLY files under ' + dir + ' (space-runtime.json, healthz.json, canary.json, build-log.txt, rollback-drill.json, hardening-selftest.json) and ' + R + '/evidence/staging/' + head + '/EXPECTED.json (written by CI with tools/expected.py). For every expected number report a finding (kind staging-evidence, verification_level staging-required, severity critical for a failed canary / wrong sha / visibility not private, high for a missing file) with reproduction (the jq/python command you ran on the file, exiting non-zero on the defect) when the evidence is missing or contradicts EXPECTED; healthz.git_sha must equal the pushed sha and must not be "unknown"; the python version in space-runtime.json and the resolved requirements in build-log.txt must match requirements.lock (a difference is a finding at verification_level local-mechanical). Never call any URL.'].join('\n'),
  synth: (rows, checkpoint, stop, seenKeys, ledgerSummary) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer (never edits code). Write ' + GRILL + '/RUN-REPORT-' + A.run_nonce + '.md and ' + STATUS_JSON + ' ({rows (with reason and next), seen_keys, head_sha, last_clean_gate, halt, stop}) from ONLY these mechanical inputs: STOP=' + stop + '; ROWS=' + J(rows) + '; CHECKPOINT=' + J(checkpoint) + '; SEEN_KEYS=' + J(seenKeys) + '; LEDGER (sorted by role,mode,id,attempt)=' + J(ledgerSummary) + '; ledgers under ' + R + '/.gate and ' + R + '/plan/status; the bundle manifest ' + BUNDLE_MANIFEST + '. Rows in your return must equal the ROWS given (they will be overwritten otherwise). Include the persona absence-test result, deferred DoD lines by verification_level, blocked_on_owner first, the suggested retry_parked list, unresolvable API symbols per card, the owner\'s Hub post-checks (`gh repo list`, namespace listing unchanged), and "what would most improve confidence". Return report_path, report_bytes, status_json_path.'].join('\n'),
  synthFix: (path, rows) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer mode:fix (bash). The rows table in ' + path + ' differs from the script\'s ledger. Rewrite ONLY the rows table (and the matching rows in ' + STATUS_JSON + ') from these rows, nothing else: ' + J(rows) + '. Return report_path, report_bytes, status_json_path and the same rows.'].join('\n'),
}

// ---------------------------------------------------------------------------------------------
// Inner loop per card (§5) — returns a typed result, never throws; rd = re-drive counter (prompt suffix)
// ---------------------------------------------------------------------------------------------
const localLevel = lvl => !/staging|owner|unverified/.test(String(lvl))
const starved = r => r && r.status === 'null' && /^(budget|halt|agent-slice)$/.test(String(r.reason))   // C-8: nobody judged the work → retryable, never parked
function okSemantics(c, t, b, v) {                     // taskDone(): every condition a judge asked for, in code; returns the failed condition ids
  const ok = []
  ok[1] = v.verdict === 'pass' && v.gate_exit_code === 0 && v.status !== 'null'
  ok[2] = v.ledger_head_sha === b.head_sha && isSha(b.head_sha) && v.sha === b.head_sha
  ok[3] = isHex64(v.gate_digest) && v.gate_digest === b.gate_digest                                   // A1 G1: two independent executions agree (F-12)
  ok[4] = v.gate_sha256_observed === A.gate_sha256 && v.gate_profile === 'full' && b.gate_profile === 'full'   // pinned gate; the bootstrap profile is never a card profile (CG1, A2 G9)
  ok[5] = (v.hunks_cited || []).length >= 1 && (v.checks || []).some(x => /gate\.sh/.test(x.command || ''))
  ok[6] = !!v.mutants && v.mutants.written >= 1 && v.mutants.killed === v.mutants.written               // mutants mandatory, all killed (F-20)
  ok[7] = !!v.revert_proof && v.revert_proof.observed === 'red'                                          // negative control (A1 ok[7]/ok[8])
  ok[8] = (b.dod || []).length === c.dod.length && c.dod.every(d => !localLevel(d.verification_level) || ((b.dod || []).some(x => x.id === d.id && x.exit_code === 0) && (v.dod_reruns || []).some(x => x.id === d.id && x.exit_code === 0)))   // every local DoD id exit 0 on BOTH sides (A1 ok[6])
  ok[9] = (v.warnings_cleared || []).length >= (v.idiom_hits || 0)                                     // F-10 in code (A2 G14)
  ok[10] = !!v.diff_stats && Number.isInteger(v.diff_stats.insertions) && Number.isInteger(v.diff_stats.deletions) && (v.diff_stats.insertions + v.diff_stats.deletions) <= 2 * (c.est_lines || 300)   // scope expansion, fail closed without stats (A2 G8, C-25)
  ok[11] = !b.__secret_redacted && !v.__secret_redacted                                               // CG3: a secret-shaped output blocks the card
  ok[12] = (b.commits_made >= 1 || b.status === 'reused') && b.status !== 'partial' && (b.apis_used || []).every(a => !!a.ledger_ref)   // F-8: every API the builder used is anchored in the ledger
  const failed = [1,2,3,4,5,6,7,8,9,10,11,12].filter(k => !ok[k])
  log(c.id + ' taskDone: ' + [1,2,3,4,5,6,7,8,9,10,11,12].map(k => k + (ok[k] ? '✓' : '✗')).join(' '))
  return failed
}
function typedFailures(c, b, v, failedConds) {         // C-18: the fixer always receives an actionable, typed object; a digest mismatch carries both ledgers' steps
  const f = { conditions_failed: failedConds, failures: v.failures || [], checks_failed: (v.checks || []).filter(x => x.exit_code !== 0), dod_reruns_failed: (v.dod_reruns || []).filter(x => x.exit_code !== 0), strongest_disagreement: cap(v.strongest_disagreement, 600) }
  if (failedConds.includes(3)) {
    const bs = (b.gate_steps || []).map(s => s.name + '=' + s.exit_code), vs = (v.gate_steps || []).map(s => s.name + '=' + s.exit_code)
    f.digest_mismatch = { kind: 'digest-mismatch', builder_head: b.head_sha, verifier_head: v.ledger_head_sha, builder_steps: bs, verifier_steps: vs, steps_only_in_builder: bs.filter(x => !vs.includes(x)), steps_only_in_verifier: vs.filter(x => !bs.includes(x)), hint: 'the builder\'s advisory gate did not run at the final commit on a clean tree, or a step differs (see steps_only_in_*); re-run the gate LAST on the committed tree and return its digest' }
  }
  if (failedConds.includes(6)) f.mutants = v.mutants
  if (failedConds.includes(7)) f.revert_proof = v.revert_proof
  if (failedConds.includes(10)) f.scope = { diff_stats: v.diff_stats || null, est_lines: c.est_lines, hint: 'insertions + deletions must be ≤ 2 × est_lines (LEDGER_DIFF_STATS excludes tools/gate.sh and tests/fixtures/)' }
  return f
}
const failFingerprint = (v, failedConds, tf) => (fingerprint(v.failures) + '|cond:' + failedConds.join(',') + (tf.digest_mismatch ? '|dm:' + tf.digest_mismatch.steps_only_in_builder.concat(tf.digest_mismatch.steps_only_in_verifier).sort().join(',') : '')).replace(/[0-9a-f]{7,40}/g, 'SHA')
async function buildTask(c, base, mergedIds, rd) {
  const trail = []; let t = null, redInfo = null
  try {
    for (let k = 1; k <= MAX_AUTHOR; k++) {
      const a = await run('author', 'tests', c.id + ':' + k, P.author(c, base, k, rd, redInfo), { phase: 'Build', schema: TESTS, effort: 'medium' })
      if (starved(a)) return { card: c, state: 'starved', reason: 'starved:' + a.reason + ':author', trail }
      if (a.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:author:' + a.reason, trail }
      if (!isSha(a.tests_head) || !(a.commits_made >= 1 || a.status === 'reused')) return { card: c, state: 'blocked', reason: 'author-no-commit', trail }
      const red = await run('verifier', 'red', c.id + ':' + k, P.red(c, a, base, rd), { phase: 'Build', schema: VERDICT, effort: 'low' })
      trail.push({ author: k, red: red.verdict || red.status })
      if (starved(red)) return { card: c, state: 'starved', reason: 'starved:' + red.reason + ':red', trail }
      if (red.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:red', trail }
      if (red.verdict === 'pass' && red.gate_exit_code === 0 && red.sha === a.tests_head && isHex64(red.gate_digest) && red.gate_digest === a.gate_digest) { t = a; break }   // C-29: confirm-RED is a two-execution equality too
      if (k === MAX_AUTHOR) return { card: c, state: 'blocked', reason: 'tests-not-red', trail }
      redInfo = { verdict: red.verdict, digest_equal: red.gate_digest === a.gate_digest, failures: (red.failures || []).slice(0, 8), checks_failed: (red.checks || []).filter(x => x.exit_code !== 0).slice(0, 5), strongest_disagreement: cap(red.strongest_disagreement, 400) }   // C-26
      log(c.id + ': confirm-RED failed (' + k + '/' + MAX_AUTHOR + ') — re-driving the author with the red verdict')
    }
    let b = null, v = null, fails = null, prevFp = null, fps = []
    for (let k = 1; k <= MAX_BUILD; k++) {
      b = await run('builder', k === 1 ? 'build' : 'fix', c.id + ':' + k, P.build(c, t, base, k, fails, mergedIds, rd), { phase: 'Build', schema: BUILD, effort: 'high' })
      if (starved(b)) return { card: c, state: 'starved', reason: 'starved:' + b.reason + ':builder', trail, tests: t }
      if (b.status === 'null' || b.status === 'failed') return { card: c, state: 'blocked', reason: 'agent-null:builder:' + (b.reason || b.status), trail, tests: t }
      if (!(b.commits_made >= 1) && b.status !== 'reused') return { card: c, state: 'blocked', reason: 'no-commits', trail, tests: t }
      v = await run('verifier', 'verify', c.id + ':' + k, P.verify(c, t, b, k, mergedIds, rd), { phase: 'Build', schema: VERDICT, effort: c.risk === 'security' ? 'xhigh' : 'medium' })
      if (starved(v)) return { card: c, state: 'starved', reason: 'starved:' + v.reason + ':verifier', trail, tests: t, build: b }
      if (v.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:verifier', trail, tests: t, build: b }
      raiseLevels(v.findings, f => f.title + ' ' + (f.reproduction || {}).command)
      const failedConds = okSemantics(c, t, b, v)
      trail.push({ build: k, verdict: v.verdict || v.status, digestOk: v.gate_digest === b.gate_digest, failed: failedConds })
      if (!failedConds.length) break
      if (b.__secret_redacted || v.__secret_redacted) return { card: c, state: 'blocked', reason: 'secret-shaped-output', trail, tests: t, build: b, verify: v }
      const tf = typedFailures(c, b, v, failedConds), fp = failFingerprint(v, failedConds, tf); fps.push(fp)
      if (fp === prevFp) return { card: c, state: 'blocked', reason: 'no-progress', trail, tests: t, build: b, verify: v }          // two strikes (D-8) — never empty now (C-18)
      if (fps.length >= 3 && fps[fps.length - 1] === fps[fps.length - 3]) return { card: c, state: 'blocked', reason: 'oscillation', trail, tests: t, build: b, verify: v }
      if (k === MAX_BUILD) return { card: c, state: 'blocked', reason: 'fix-exhausted', trail, tests: t, build: b, verify: v }
      prevFp = fp; fails = tf
      log(c.id + ': verify FAILED (' + k + '/' + MAX_BUILD + ') conditions ' + failedConds.join(',') + ' fp=' + fp.slice(0, 60) + ' — fixing')
    }
    const deferred = c.dod.filter(d => !localLevel(d.verification_level)).map(d => d.id)
    return { card: c, state: 'built', tests: t, build: b, verify: v, deferred, apiUnresolvable: (v.apicheck_unresolvable || []).slice().sort(), trail }        // taskDone() true
  } catch (e) { log(c.id + ': stage threw ' + String(e && e.message)); return { card: c, state: 'blocked', reason: 'threw', trail } }
}

// ---------------------------------------------------------------------------------------------
// Serial integration of one built card (§4.5) — mutates `head` via the returned value only; every merge is logged with its merge sha (C-12)
// ---------------------------------------------------------------------------------------------
const mergeOk = m => m.status === 'merged' && isSha(m.head_sha) && isSha(m.merge_sha) && m.gate_exit_code === 0 && isHex64(m.gate_digest) && m.gate_sha256_observed === A.gate_sha256 && !(m.cherry_unmerged || []).length && !(m.patch_ids_missing || []).length
const alreadyOk = (m, head) => m.status === 'already-merged' && m.head_sha === head && m.gate_exit_code === 0 && isHex64(m.gate_digest) && m.gate_sha256_observed === A.gate_sha256 && !(m.cherry_unmerged || []).length && !(m.patch_ids_missing || []).length   // C-20: an ancestor never moves the head; gate + cherry evidence required
const mergeLog = []                          // [{id, merge_sha, head_after}] in order — the revert target is always the LAST entry (journeys included)
const journeyChecks = []                     // journeys skipped after their card merged → synthetic findings (collected at merge and clean gates)
function noteJourneys(cg, where) {
  const stillSkipped = ((cg.journeys || {}).skipped_needs || []).filter(n => mergedSet().has(n)).sort()
  if (stillSkipped.length) { log(where + ': journeys still skipped although their card merged: ' + stillSkipped.join(',') + ' → synthetic finding'); journeyChecks.push({ id: 'journey-needs-' + stillSkipped.join('+'), title: 'journey skipped after its card merged', file: 'tests/journeys', severity: 'high', kind: 'interaction', reproduction: { command: gateCmd('--clean --journeys'), exit_code: 1, output_tail: 'skipped_needs=' + stillSkipped.join(',') }, verification_level: 'local-stub', files_allowed: ['tests/journeys'] }) }
}
async function checkedRevert(id, head, mergeSha, why) {   // CG-24 + C-12/C-20: revert by merge sha; the result is checked; failure dirties the branch
  const rv = await run('integrator', 'revert', id + ':revert', P.revert(id, head, mergeSha, [...mergedSet()].filter(x => x !== id)), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (rv.status === 'merged' && isSha(rv.head_sha) && rv.gate_exit_code === 0 && isHex64(rv.gate_digest) && rv.gate_sha256_observed === A.gate_sha256) { log(id + ': reverted (' + why + ') → ' + rv.head_sha.slice(0, 12)); return { ok: true, head: rv.head_sha } }
  INTEG_DIRTY = true; log('REVERT FAILED for ' + id + ' (' + why + ', ' + (rv.status || rv.reason) + ') — integration branch marked dirty; no further merges (CG-24)'); return { ok: false, head }
}
async function integrate(r, head, mergedIds) {
  let m = await run('integrator', 'merge', r.card.id, P.merge(r.card, r.build, head, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (m.status === 'conflict') {
    log(r.card.id + ': conflict in ' + m.conflicts.map(x => x.file).join(',') + ' — fresh conflict call')
    const res = await run('integrator', 'conflict', r.card.id, P.conflict(r.card, r.build, head, m.conflicts), { phase: 'Integrate', schema: MERGE, effort: 'high' })
    m = res.status === 'merged' ? await run('integrator', 'ff', r.card.id + ':ff', P.ff(r.card, res.head_sha, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' }) : res
  }
  if (starved(m)) return { head, state: 'starved', reason: 'starved:' + m.reason + ':integrator' }
  if (m.status === 'missing-ref') { log(r.card.id + ': ref missing (stale sha) — will re-drive live'); return { head, state: 'stale' } }
  if (m.status === 'already-merged') { if (alreadyOk(m, head)) return { head, state: 'merged', digest: m.gate_digest, already: true }; log(r.card.id + ': already-merged WITHOUT evidence (head ' + String(m.head_sha).slice(0, 12) + ' vs ' + head.slice(0, 12) + ', exit ' + m.gate_exit_code + ', cherry ' + (m.cherry_unmerged || []).length + ') — not counted (C-20)'); return { head, state: 'blocked', reason: 'integration:already-merged-unproven' } }
  if (m.status === 'reverted') return { head: isSha(m.head_sha) ? m.head_sha : head, state: 'reverted', reason: 'integration:gate-red-after-merge(reverted)' }
  if (m.status === 'merged' && m.gate_exit_code !== 0 && isSha(m.merge_sha)) {            // C-20: "merged + red" is a revert-now case, checked
    const rv = await checkedRevert(r.card.id, isSha(m.head_sha) ? m.head_sha : head, m.merge_sha, 'merge gate red')
    return rv.ok ? { head: rv.head, state: 'reverted', reason: 'integration:gate-red-after-merge(reverted)' } : { head: rv.head, state: 'revert-failed', reason: 'integration:gate-red-after-merge(revert-failed)' }
  }
  if (!mergeOk(m)) { log(r.card.id + ': NOT integrated (' + m.status + (m.reason ? ':' + m.reason : '') + ')'); return { head, state: 'blocked', reason: 'integration:not-merged:' + (m.status === 'null' ? String(m.reason || 'null') : m.status) } }
  if ((m.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:' + r.card.id; log('HALT ' + HALT) }   // CG5: mechanical post-check, not self-report
  mergeLog.push({ id: r.card.id, merge_sha: m.merge_sha, head_after: m.head_sha })
  noteJourneys(m, 'merge ' + r.card.id)
  return { head: m.head_sha, state: 'merged', digest: m.gate_digest, merge_sha: m.merge_sha }
}
// clean gate, typed three ways (C-11): pass | fail | gate-unavailable(reason) — a malformed return never reverts anything
async function cleanGate(tag, head, mergedIds) {
  const lintBase = lastClean.verdict === 'pass' && isSha(lastClean.head_sha) ? lastClean.head_sha : A.base_sha        // C-15: lint only what this wave added
  const cg = await run('integrator', 'clean', tag, P.clean(tag, head, mergedIds, lintBase), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (cg.status === 'null') { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: null, wave: tag, why: cg.reason }; log(tag + ': clean-gate UNAVAILABLE (' + cg.reason + ') — no revert; satisfied() stays false'); return lastClean }
  const st = cg.self_test || {}, shaped = isSha(cg.head_sha) && isHex64(cg.gate_digest) && cg.gate_sha256_observed === A.gate_sha256 && typeof st.broken_red === 'boolean' && typeof st.false_claim_red === 'string' && !!cg.journeys && Number.isInteger(cg.gate_exit_code)
  if (!shaped || cg.head_sha !== head) { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: null, wave: tag, why: !shaped ? 'malformed' : 'wrong-head:' + String(cg.head_sha).slice(0, 12) }; log(tag + ': clean-gate MALFORMED (' + lastClean.why + ') — treated as unavailable, no revert (C-11)'); return lastClean }
  if (cg.toolchain_status_sha256 && cg.toolchain_status_sha256 !== A.toolchain_status_sha256) { HALT = 'toolchain-mutated'; log('HALT ' + HALT + ' (F-1; docs/grills excluded from the comparison)') }
  if ((cg.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:clean-gate'; log('HALT ' + HALT) }
  noteJourneys(cg, tag)
  const pass = cg.gate_exit_code === 0 && st.broken_red === true && st.false_claim_red === 'true'
  if (cg.gate_exit_code === 0 && !pass) { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: cg.gate_digest, wave: tag, why: 'exit0-but-self-test-not-red:' + st.broken_red + '/' + st.false_claim_red }; log(tag + ': clean-gate exit 0 but self-test contradicts it — treated as unavailable (C-11)'); return lastClean }
  lastClean = { verdict: pass ? 'pass' : 'fail', head_sha: head, digest: cg.gate_digest, wave: tag }
  return lastClean
}

// ---------------------------------------------------------------------------------------------
// Build + integrate a list of cards — waves computed ONE AT A TIME from the live status map (C-5); used for the plan and for review fix tasks
// ---------------------------------------------------------------------------------------------
const status = new Map()                    // card id → typed state (the script's own row table; F-40); every entry carries a reason (C-22)
let lastClean = { verdict: 'gate-unavailable', head_sha: null, digest: null, why: 'never-run' }, INTEG_DIRTY = false
const mergedSet = () => new Set([...status.entries()].filter(([, s]) => s.state === 'merged').map(([id]) => id))
const stateOf = id => (status.get(id) || {}).state || null
const PARKED_RE = /^(parked|reverted|revert-failed|dropped_null)$/
function readyWave(cards, rank) {           // cards with no status whose deps are all merged, by (−rank, id), disjoint write sets, ≤ WAVE; the waiters are logged
  const ready = cards.filter(c => !status.has(c.id) && c.depends_on.every(d => mergedSet().has(d))).sort(byRank(rank))
  const wave = [], used = new Set(), waited = []
  for (const c of ready) { const ws = writeSet(c), clash = [...ws].some(f => used.has(f)); if (!clash && wave.length < WAVE) { wave.push(c); ws.forEach(f => used.add(f)) } else waited.push(c.id) }
  if (waited.length) log('wave: ' + waited.join(',') + ' wait (size or write-set overlap)')   // T-AP-11: never silent
  return wave
}
function markDependencyBlocked(cards) {     // after the loop: every card still without a status has a dependency that is not merged
  for (const c of cards) if (!status.has(c.id)) { const unmet = c.depends_on.filter(d => !mergedSet().has(d)); if (unmet.length) { status.set(c.id, { state: 'not_attempted', reason: 'dependency-blocked:' + unmet.map(d => d + '(' + (stateOf(d) || 'unscheduled') + ')').join('/'), next: 'resolve the dependency; relaunch stage=' + A.stage }); log(c.id + ': not attempted (deps ' + unmet.join('/') + ')') } }
}
async function buildAndIntegrate(cards, head, tag) {
  cards.forEach(c => CARD_BY_ID.set(c.id, c))
  for (const c of cards) { const pre = c.owner_precondition; if (pre && !OA[pre] && !status.has(c.id)) { status.set(c.id, { state: 'blocked_on_owner', field: pre, reason: 'owner-precondition:' + pre, next: 'owner records owner_approvals.' + pre + '; relaunch stage=' + A.stage }); log(c.id + ': blocked on owner_approvals.' + pre) } }
  const rank = rankCards(cards)
  let w = 0
  while (true) {
    const wave = readyWave(cards, rank)
    if (!wave.length) break
    w++
    if (INTEG_DIRTY || !budgetOk(tag + ' wave ' + w) || !agentsOk(tag + ' wave ' + w, RESERVE_PER_CHAIN * wave.length + 4)) {   // C-8: starvation is not_attempted (retryable), never parked
      const why = INTEG_DIRTY ? 'integration-dirty' : (HALT ? 'halt:' + HALT : 'agent-slice-or-budget')
      cards.filter(c => !status.has(c.id)).forEach(c => status.set(c.id, { state: 'not_attempted', reason: why === 'integration-dirty' ? 'blocked:integration-dirty' : 'not_attempted:' + why, next: why === 'integration-dirty' ? 'owner inspects ' + INTEG + ' (revert failed); relaunch after repair' : 'relaunch stage=' + A.stage + ' with next_args' }))   // v2.1 V-8: the dirty reason sits OUTSIDE RETRYABLE_RE so a resume never auto-retries over its own owner-inspect next
      log(tag + ': wave ' + w + ' and the rest NOT attempted (' + why + ')'); break
    }
    log(tag + ' wave ' + w + ': ' + wave.map(c => c.id).join(', ') + ' on ' + head.slice(0, 12))
    const mergedBefore = [...mergedSet()]
    const results = await pipeline(wave, c => buildTask(c, head, mergedBefore, 0))
    let dropped = 0; results.forEach((r, i) => { if (!r) { dropped++; status.set(wave[i].id, { state: 'dropped_null', reason: 'chain-null', next: 'retry_parked' }) } })
    if (dropped) log(tag + ' wave ' + w + ': ' + dropped + ' chain(s) resolved null (typed dropped_null)')
    phase('Integrate')
    const merged = []
    for (const r of results.filter(Boolean).sort((x, y) => byRank(rank)(x.card, y.card))) {      // C-24: serial, rank order, ties by id
      if (r.state === 'starved') { status.set(r.card.id, { state: 'not_attempted', reason: r.reason, next: 'relaunch stage=' + A.stage + ' with next_args (branches survive; author/builder return reused)', trail: r.trail }); continue }
      if (r.state !== 'built') { status.set(r.card.id, { state: 'parked', reason: r.reason, next: RETRYABLE_RE.test(r.reason) ? 'retry_parked' : 'inspect the trail; a review fix card or a plan repair', head_sha: r.build ? r.build.head_sha : null, dod: r.build ? r.build.dod : [], trail: r.trail }); continue }
      let it = await integrate(r, head, [...mergedSet()])
      if (it.state === 'stale') { const again = await buildTask(r.card, head, [...mergedSet()], 1); it = again.state === 'built' ? await integrate(again, head, [...mergedSet()]) : { state: again.state === 'starved' ? 'starved' : 'blocked', reason: again.reason, head } }
      if (it.state === 'merged') { head = it.head; merged.push(r.card.id); status.set(r.card.id, { state: 'merged', reason: it.already ? 'already-merged(proven)' : 'merged', next: 'none', head_sha: head, merge_sha: it.merge_sha || null, dod: r.build.dod, deferred: r.deferred, digest: it.digest, api_unresolvable: r.apiUnresolvable }); log(r.card.id + ' merged → ' + head.slice(0, 12)) }
      else if (it.state === 'starved') status.set(r.card.id, { state: 'not_attempted', reason: it.reason, next: 'relaunch stage=' + A.stage + ' (built branch survives)', head_sha: r.build.head_sha, dod: r.build.dod })
      else { if (isSha(it.head)) head = it.head; status.set(r.card.id, { state: it.state === 'reverted' ? 'reverted' : it.state === 'revert-failed' ? 'revert-failed' : 'parked', reason: it.reason, next: RETRYABLE_RE.test(it.reason) ? 'retry_parked' : 'review fix card', head_sha: r.build.head_sha, dod: r.build.dod }) }
    }
    const seams = Object.keys(JOURNEY_NEEDS).filter(s => merged.includes(JOURNEY_NEEDS[s])).sort()
    let journeysMerged = false
    if (seams.length && !A.smoke) {
      const jw = await run('author', 'journeys', tag + ':w' + w, P.journeys(tag + '-w' + w, head, seams), { phase: 'Integrate', schema: TESTS, effort: 'medium' })
      if (jw.status === 'SUCCESS' && isSha(jw.tests_head) && jw.gate_exit_code === 0 && isHex64(jw.gate_digest)) { const jm = await integrate({ card: { id: 'journeys-' + tag + '-w' + w }, build: { head_sha: jw.tests_head } }, head, [...mergedSet()]); if (jm.state === 'merged') { head = jm.head; journeysMerged = true } else log('journeys ' + tag + '-w' + w + ' NOT merged: ' + jm.reason) }   // v2.1 V-11: the author's own journeys-only gate run must be green WITH a digest — a SUCCESS over a red gate is refused HERE, one merge+revert earlier than the merge gate
      else log('journeys author ' + tag + '-w' + w + ' dropped/failed/refused (needs SUCCESS, tests_head, gate_exit_code 0, 64-hex gate_digest): ' + (jw.reason || jw.status || 'gate_exit_code=' + jw.gate_exit_code))
    }
    if (!merged.length && !journeysMerged && lastClean.verdict === 'pass' && lastClean.head_sha === head) { log(tag + ' wave ' + w + ': nothing merged, clean gate already passing at ' + head.slice(0, 12) + ' — skipped (C-38)'); phase('Build'); continue }
    const cg = await cleanGate(tag + ':w' + w, head, [...mergedSet()])
    if (cg.verdict === 'fail') {
      const last = mergeLog[mergeLog.length - 1]; log(tag + ' wave ' + w + ': clean-gate RED at ' + head.slice(0, 12) + (last ? ' — reverting the last merge ' + last.id + ' (' + String(last.merge_sha).slice(0, 12) + ')' : ' — nothing to revert'))
      if (last) {
        const rv = await checkedRevert(last.id, head, last.merge_sha, 'clean-gate red')
        mergeLog.pop()
        if (rv.ok) { head = rv.head; if (status.has(last.id)) status.set(last.id, { state: 'reverted', reason: 'clean-gate-red', next: 'review fix card', head_sha: head }); lastClean = { verdict: 'fail-reverted', head_sha: head, digest: null, wave: tag + ':w' + w } }   // C-10: not a pass — the review pre-check re-runs a clean gate
        else if (status.has(last.id)) status.set(last.id, { state: 'revert-failed', reason: 'revert:clean-gate-red', next: 'owner inspects ' + INTEG, head_sha: head })
      }
    }
    phase('Build')
  }
  markDependencyBlocked(cards)
  return head
}

// ---------------------------------------------------------------------------------------------
// satisfied() — the ONLY way the run says the tree is done (D-24, C-D); evidence stages use the same predicate
// ---------------------------------------------------------------------------------------------
const openBlocking = [], seen = new Set(), probesUsed = new Set(), ownerFindings = []
function treeIncomplete(allCards) {         // C-5: any card not merged and not a parked LEAF makes the tree incomplete; dependents of a parked card count
  const parked = allCards.filter(c => PARKED_RE.test(stateOf(c.id) || ''))
  const parkedCritical = parked.filter(p => allCards.some(c => c.depends_on.includes(p.id) && stateOf(c.id) !== 'merged')).map(p => p.id)
  const pending = allCards.filter(c => !status.has(c.id) || /^(not_attempted|blocked_on_owner)$/.test(stateOf(c.id))).map(c => c.id)
  return { parkedCritical, pending, reasons: parkedCritical.map(id => 'parked-with-dependents:' + id).concat(pending.map(id => stateOf(id) ? stateOf(id) + ':' + id : 'unscheduled:' + id)) }
}
function satisfied(head, allCards) {
  const inc = treeIncomplete(allCards)
  const ownerCritical = ownerFindings.filter(f => /^(critical|high)$/.test(f.severity)).length
  const ok = !HALT && !INTEG_DIRTY && lastClean.verdict === 'pass' && lastClean.head_sha === head && openBlocking.length === 0 && inc.reasons.length === 0 && ownerCritical === 0
  log('satisfied()=' + ok + ' clean=' + lastClean.verdict + '@' + String(lastClean.head_sha).slice(0, 12) + ' openBlocking=' + openBlocking.length + ' incomplete=' + inc.reasons.length + ' ownerCritical=' + ownerCritical + (HALT ? ' HALT=' + HALT : ''))
  return ok
}
const toFixCard = (f, round, i) => { const id = 'platform-00-rf' + round + '-' + String(i + 1).padStart(2, '0') + '-' + f.id.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 24); return { id, path: 'plan/fixes/' + id + '.json', step: 1, depends_on: [], files_allowed: f.files_allowed || [f.file], tests_allowed: [], new_modules: [], required_files: [], deps_allowed: [], xfail_allowed: [], expected_green_tests: [], tests_removed_expected: 0, est_lines: 120, est_minutes: 20,
  dod: [{ id: 'D1', command: f.reproduction.command, expect: 'exit 0 once fixed (the reproduction exits non-zero on the defect)', verification_level: localLevel(f.verification_level) ? f.verification_level : 'local-stub' }], size: 'S', risk: f.kind === 'security' || f.kind === 'secrets' ? 'security' : 'none', protected_touch: false, bootstrap: false, decision_ids: [], finding_ids: [{ id: f.id, corrected_text: cap(f.corrected_claim || f.title, 600) }], apis_expected: [], owner_precondition: '', finding: f } }

// ---------------------------------------------------------------------------------------------
// Whole-tree review loop (§6.2)
// ---------------------------------------------------------------------------------------------
async function reviewLoop(head, allCards) {
  phase('Review')
  const LENSES = ['decision-fidelity+scope', 'correctness+tests-integrity', 'security+secrets']
  let round = 0, dry = 0, stop = null, vetoes = []
  if (A.smoke) { log('SMOKE: review loop skipped (C-33)'); return { head, stop: 'smoke-skip-review', round } }
  const inc = treeIncomplete(allCards)
  if (inc.reasons.length) { log('review loop NOT started: tree incomplete (' + inc.reasons.slice(0, 6).join(', ') + ') — no lenses spent (C-5)'); return { head, stop: 'tree-incomplete', round } }
  if (!HALT && !INTEG_DIRTY && !(lastClean.verdict === 'pass' && lastClean.head_sha === head)) {   // C-10: never review a tree without a passing clean gate at its head
    log('review pre-check: last clean gate is ' + lastClean.verdict + '@' + String(lastClean.head_sha).slice(0, 12) + ' vs head ' + head.slice(0, 12) + ' — re-running one clean gate before any lens')
    if (!budgetOk('review pre-check clean gate')) return { head, stop: HALT ? 'halt:' + HALT : 'budget-or-agent-cap', round }
    const cg = await cleanGate('review-pre', head, [...mergedSet()])
    if (cg.verdict !== 'pass') { log('review loop NOT started: clean gate ' + cg.verdict + (cg.why ? ' (' + cg.why + ')' : '')); return { head, stop: 'clean-gate-' + (cg.verdict === 'fail' ? 'red' : 'unavailable'), round } }
  }
  while (true) {
    if (satisfied(head, allCards) && vetoes.length === 0 && round > 0) { stop = 'satisfied'; break }
    if (HALT) { stop = 'halt:' + HALT; break }
    if (INTEG_DIRTY) { stop = 'integration-dirty'; break }
    if (round >= MAX_ROUNDS) { stop = 'max-rounds(' + MAX_ROUNDS + ')'; break }
    if (dry >= 2) { stop = 'dry(2)'; break }
    if (!budgetOk('review round ' + (round + 1)) || !agentsOk('review round ' + (round + 1), 3 + 4)) { stop = 'budget-or-agent-cap'; break }
    round++
    const seenKeys = [...seen].sort()
    const reviews = await parallel(LENSES.map(lens => () => run('verifier', 'review', lens + ':r' + round, P.review(lens, head, seenKeys, round), { phase: 'Review', schema: VERDICT, effort: 'high' }, LENSES.length)))   // barrier: dedup needs all
    const lensDrops = reviews.filter(r => !r || r.status === 'null').length
    reviews.filter(r => r && r.status !== 'null').forEach(r => (r.probes_used || []).forEach(p => probesUsed.add(cap(p, 200))))
    const found = reviews.filter(r => r && r.status !== 'null').flatMap(r => r.findings || []).concat(journeyChecks.splice(0), syntheticFindings.splice(0)).filter(f => f.reproduction && f.verification_level !== 'unverified').sort(byId)
    raiseLevels(found, f => f.title + ' ' + (f.reproduction || {}).command)
    const fresh = found.filter(f => !seen.has(fkey(f))); fresh.forEach(f => seen.add(fkey(f)))
    log('review r' + round + ': ' + found.length + ' found, ' + fresh.length + ' fresh, ' + lensDrops + ' lens(es) dropped')
    const judged = fresh.length ? await pipeline(fresh, f => run('verifier', 'refute', f.id + ':r' + round, P.refute(f, head), { phase: 'Review', schema: VERDICT, effort: 'medium' }, fresh.length).then(v => ({ f, v }))) : []
    const judgeDrops = judged.filter(j => !j).length; if (judgeDrops) log('review r' + round + ': ' + judgeDrops + ' refute chain(s) resolved null (counted, not queued)')   // J1 D5
    const confirmed = judged.filter(Boolean).filter(({ v }) => v.status !== 'null' && v.verdict === 'holds' && v.findings && v.findings[0] && v.findings[0].reproduction && v.findings[0].reproduction.exit_code !== 0).map(({ f, v }) => Object.assign({}, f, v.findings[0]))   // C-27: a reproduction that exits 0 proves nothing
    const shapeless = judged.filter(Boolean).filter(({ v }) => v.status !== 'null' && v.verdict === 'holds' && !(v.findings && v.findings[0] && v.findings[0].reproduction && v.findings[0].reproduction.exit_code !== 0)).length; if (shapeless) log('review r' + round + ': ' + shapeless + ' "holds" verdict(s) without a non-zero-exit reproduction ignored (C-27)')
    log('review r' + round + ': ' + confirmed.length + '/' + fresh.length + ' hold after refutation')
    const accepted = new Set(OA.accepted_findings || [])                                   // owner data: medium/low evidence findings the owner explicitly accepts (never critical/high)
    const ownerOnly = confirmed.filter(f => !localLevel(f.verification_level) && !(accepted.has(f.id) && /^(medium|low)$/.test(f.severity)))
    confirmed.filter(f => !localLevel(f.verification_level) && accepted.has(f.id) && /^(medium|low)$/.test(f.severity)).forEach(f => { log('finding ' + f.id + ' (' + f.severity + ') accepted by owner_approvals.accepted_findings — recorded, not blocking'); if (!status.has('finding:' + f.id)) status.set('finding:' + f.id, { state: 'deferred', reason: 'accepted-by-owner:' + f.id, next: 'none' }) })
    ownerOnly.forEach(f => { if (!status.has('finding:' + f.id)) { status.set('finding:' + f.id, { state: 'blocked_on_owner', field: A.stage === 'promote' ? 'production_evidence_dir' : 'staging_evidence_dir', reason: 'finding ' + f.id + ' (' + f.severity + ', ' + f.kind + ') is ' + f.verification_level, next: A.stage === 'promote' ? 'rollback, then fix on staging' : 'fix on staging; re-run the CI evidence job; relaunch stage=' + A.stage, severity: f.severity }); ownerFindings.push({ id: f.id, severity: f.severity, kind: f.kind, title: f.title }) } })
    if ((A.stage === 'stage' || A.stage === 'promote') && ownerOnly.some(f => /^(critical|high)$/.test(f.severity))) { stop = 'blocked-on-owner:staging-evidence'; log('review r' + round + ': confirmed critical/high staging finding(s) ' + ownerOnly.filter(f => /^(critical|high)$/.test(f.severity)).map(f => f.id).join(',') + ' → stop; no promotion can be emitted (C-6)'); break }
    const fixable = confirmed.filter(f => localLevel(f.verification_level))
    const blocking = fixable.filter(f => f.severity === 'critical' || f.severity === 'high'); openBlocking.push(...blocking.map(f => f.id))
    const fixCards = [...fixable, ...vetoes].map((f, i) => toFixCard(f, round, i))
    if (fixCards.length) {
      const fw = await run('integrator', 'fixcards', 'r' + round, P.fixcards(fixCards, head, round), { phase: 'Review', schema: MERGE, effort: 'low' })   // C-3: first-class cards on plan/fixes, committed by the single writer
      const written = fw.status === 'written' && isSha(fw.head_sha) && fixCards.every(c => (fw.files_written || []).includes(cardPath(c)))
      if (!written) { log('review r' + round + ': fix cards NOT written (' + (fw.status || fw.reason) + ') — ' + fixCards.length + ' fix card(s) not attempted this round'); fixCards.forEach(c => status.set(c.id, { state: 'not_attempted', reason: 'fixcards-unavailable', next: 'relaunch stage=' + A.stage })) }
      else { head = fw.head_sha; head = await buildAndIntegrate(fixCards, head, 'fix-r' + round); fixCards.forEach(c => { if (stateOf(c.id) === 'merged') { const k = openBlocking.indexOf(c.finding_ids[0].id); if (k >= 0) openBlocking.splice(k, 1) } }) }
    }
    vetoes = []
    if (satisfied(head, allCards)) {
      const rows = [...status.entries()].sort().map(([id, s]) => ({ id, state: s.state, reason: s.reason || null }))
      const vj = await run('verifier', 'veto', 'r' + round, P.veto(head, rows, round === MAX_ROUNDS || dry === 1, [...probesUsed].sort()), { phase: 'Review', schema: VERDICT, effort: 'xhigh' })
      if (vj.status === 'null') { stop = 'veto-unavailable'; log('veto r' + round + ': judge dropped → NOT satisfied (fail closed)'); break }   // A1 §13.7 fail-closed judging
      vetoes = (vj.findings || []).filter(f => f.reproduction && f.reproduction.exit_code !== 0 && f.verification_level !== 'unverified'); const notes = (vj.findings || []).length - vetoes.length
      ;(vj.probes_used || []).forEach(p => probesUsed.add(cap(p, 200)))
      log('veto r' + round + ': ' + vetoes.length + ' veto(es) with a non-zero-exit reproduction, ' + notes + ' note(s) without')
    }
    dry = (fresh.length === 0 && vetoes.length === 0) ? dry + 1 : 0
  }
  log('review loop ended: ' + stop + ' after ' + round + ' round(s); seen=' + seen.size + ' openBlocking=' + openBlocking.length)
  return { head, stop, round }
}
const syntheticFindings = []

// ---------------------------------------------------------------------------------------------
// Checkpoint object (computed by the script; the synthesizer only renders it) — §2.2; every row carries reason + next (C-22)
// ---------------------------------------------------------------------------------------------
function checkpoint(stage, head, stop, planDefects) {
  const rows = [...status.entries()].filter(([id]) => !id.startsWith('finding:') && id !== 'evidence').sort().map(([task_id, s]) => ({ task_id, state: s.state === 'merged' ? 'merged+gate-green' : s.state, reason: s.reason || s.state, next: s.next || 'none', head_sha: s.head_sha || 'none', dod_done: (s.dod || []).filter(d => d.exit_code === 0).length, dod_total: (s.dod || []).length, dod_deferred: (s.deferred || []).length }))
  const actions = [], blocked_on_owner = [], deferred = []
  const act = (id, kind, why, steps, blast, rollback, cost) => actions.push({ id, kind, why, exact_steps: steps, blast_radius: blast, rollback, cost_estimate: cost, evidence_paths: [R + '/.gate/last_run.json', STATUS_JSON] })
  for (const [id, s] of status) if (s.state === 'blocked_on_owner') blocked_on_owner.push({ task_id: id, field: s.field, why: s.reason, next: s.next || null, severity: s.severity || null })
  for (const [id, s] of status) if (s.state === 'merged' && (s.deferred || []).length) deferred.push({ task_id: id, dod_ids: s.deferred, why: 'staging/owner-required DoD lines; proven by the CI evidence job in R2' })   // informational, not a blocker of R1's ready
  const api_unresolvable = [...status.entries()].filter(([, s]) => (s.api_unresolvable || []).length).map(([id, s]) => ({ task_id: id, symbols: s.api_unresolvable }))
  const retry_parked_suggested = rows.filter(r => PARKED_RE.test(r.state) && RETRYABLE_RE.test(r.reason)).map(r => r.task_id)
  const complete = stage === 'plan' ? stop === 'plan-verified' : rows.length > 0 && rows.every(r => /^(merged\+gate-green|parked|reverted)$/.test(r.state))   // a card blocked on the owner, not attempted or revert-failed ⇒ the stage is not done
  const ownerCritical = ownerFindings.filter(f => /^(critical|high)$/.test(f.severity))
  let ready = !HALT && !INTEG_DIRTY && (stage === 'plan' ? stop === 'plan-verified' : stop === 'satisfied') && complete && blocked_on_owner.length === 0 && ownerCritical.length === 0   // C-6
  if (stage === 'plan') {
    if (stop === 'plan-verified') act('C0-1', 'approve-plan', 'F-9: the owner approves plan/decisions.json (incl. the five against-recommendation rows and the clarifications) and plan/index.json before any code is written', ['read ' + R + '/plan/decisions.json and plan/index.json at ' + (A.plan_sha || '<plan_sha from the CARD_INDEX>'), 'launch stage=build with plan_sha=<that sha>'], 'none', 'none', '0')
    else act('C0-0', 'repair-plan', 'the plan was rejected by the script/plan verifier (' + (planDefects || []).length + ' defect(s) listed in plan_defects); it must not be approved or built', ['read plan_defects and plan_findings in this checkpoint', 'relaunch stage=plan with args.plan_defects = plan_defects (the planner runs in REPAIR MODE on the same branch)'], 'none', 'none', '0')   // C-19
    act('C0-2', 'record-fixture-1', 'lens-4 biggest risk: ONE metered streamed router call (tool + thinking on) decides where the parser lives; card platform-04-streamparser is blocked_on_owner until owner_approvals.fixture1_path is set (the thin slice 03b must exist first — expect this stop after R1\'s first invocation)', ['after cards 01-03b merge: python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    act('C0-3', 'record-boundary-fixture', 'G-19/F-17: the persona absence test needs owner-generated shingle hashes of the excluded clause (the workflow never sees the clause); card product-13b is blocked until owner_approvals.persona_boundary_fixture_path (+ _sha256) is set', ['after card 01 merges: python tools/make_boundary_fixture.py --clause-file <owner-only path> --out <owner-only path>/persona_boundary.json (off-workflow)', 'pass owner_approvals.persona_boundary_fixture_path and persona_boundary_fixture_sha256 (sha256sum of that file)'], 'none', 'none', '0')
    act('C0-4', 'decide-worker-checkpoint', 'M-2 + inference-perf-2/-5/-7 CORRECTED: the resident checkpoint must carry model.visual.* (VLM class kept for G-16); evidence/catalog records has_visual_tensors per candidate; if neither candidate has them a VLM-class export HF Job precedes staging', ['read ' + GRILL + '/evidence/catalog/*.json has_visual_tensors', 'set owner_approvals.worker_checkpoint_decision = {candidate, needs_export: true|false}'], 'none (decision only)', 'none', '0')
  }
  if (stage === 'build') {
    if (!OA.github_repo_url) act('C1-1', 'create-github-repo', 'G-1a: GitHub is the SSOT, CI the only production writer', ['gh repo create <owner>/<name> --private', 'git -C ' + R + ' remote add origin <url>', 'git -C ' + R + ' push -u origin ' + INTEG + ' ' + PLAN_BRANCH, 'post-check: gh repo list --json name shows exactly one new repo'], 'new private repo', 'delete the repo (irreversible) or leave it', '0')
    if (!(OA.staging_space_ids || []).length) act('C1-2', 'create-staging-spaces', 'G-27/M-2: CPU front + ZeroGPU worker staging Spaces (private)', ['hf repos duplicate <prod> <ns>/<name>-staging --type space --private --exist-ok', 'same for the worker Space (ZeroGPU large)', 'post-check: namespace listing shows exactly two new private Spaces'], 'two private Spaces', 'delete Spaces', 'PRO quota only')
    act('C1-3', 'set-staging-secrets', 'G-15/G-24 clarification (owner must approve): the UI/API Space holds ONE fine-grained token scoped to inference-provider calls + read access to the private worker Space; if HF cannot combine those scopes, a second read-only token for the worker is the only alternative — record owner_approvals.token_topology = one-token|two-tokens', ['create the fine-grained token in the Hub UI (never in chat)', 'set it as the staging secret', 'pass owner_approvals.token_topology'], 'staging only', 'revoke token', '0')
    if (!OA.fixture1_path) act('C1-4', 'record-fixture-1', 'card platform-04-streamparser and every card downstream of it stay blocked until fixture #1 exists', ['python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    if (!OA.persona_boundary_fixture_path || !OA.persona_boundary_fixture_sha256) act('C1-5', 'record-boundary-fixture', 'card product-13b-personas-readme stays blocked until the shingle-hash fixture and its sha256 exist', ['see C0-3'], 'none', 'none', '0')
    if (!OA.worker_checkpoint_decision) act('C1-6', 'decide-worker-checkpoint', 'card platform-08c-worker-checkpoint stays blocked until the resident checkpoint (with visual tensors) is decided', ['see C0-4'], 'none', 'none', '0')
  }
  if (stage === 'stage') {
    if (OA.worker_checkpoint_decision && OA.worker_checkpoint_decision.needs_export) act('C2-1', 'run-hf-job-quantize', 'inference-perf-2 CORRECTED: quantise/export offline with the VLM class (never inside a lease); keep the bf16 mount until one boot on the exported checkpoint is observed', ['hf jobs run … tools/export_checkpoint.py --class AutoModelForImageTextToText --budget <usd>'], 'paid HF Job', 'delete the exported repo', OA.hf_job_budget_usd ? '<= $' + OA.hf_job_budget_usd : 'owner sets hf_job_budget_usd')
    act('C2-2', 'run-harness', 'M-3: admission only after the 12-prompt harness; release 1 needs at least one entry with admission: passed (pending entries are hidden from the selector and /v1/models)', ['python tools/harness.py --backend hosted --i-accept-cost --budget ' + (OA.hosted_call_budget_usd || '<usd>') + ' on staging', 'config PR flips admission for the measured entries'], 'provider spend', 'none', OA.hosted_call_budget_usd ? '<= $' + OA.hosted_call_budget_usd : 'owner sets hosted_call_budget_usd')
    const headOk = OA.production_space_head === A.base_sha || !!OA.adopted_delta_sha
    if (!headOk) { ready = false; blocked_on_owner.push({ task_id: 'promotion', field: 'production_space_head', why: 'F-38: read the production Space HEAD (read-only Hub read) and record it; it must equal base ' + A.base_sha.slice(0, 12) + ' or the delta must be adopted explicitly (adopted_delta_sha)', next: 'record the field; relaunch stage=stage', severity: null }) }
    if (ready && headOk) act('C2-3', 'promote-production', 'G-2/M-5: the single production promotion from staging', ['trigger the production environment job (required reviewer = owner)', 'watch /healthz git_sha == pushed sha; canary ×3; keep the rollback command at hand'], 'production', 'tools/promote.py --to <last_good_sha>', '0')
  }
  if (stage === 'promote' && ownerCritical.length) act('C3-1', 'rollback', 'post-promotion evidence contradicts EXPECTED.json: confirmed critical/high finding(s) ' + ownerCritical.map(f => f.id).join(','), ['tools/promote.py --to <last_good_sha>', 'then fix on staging and relaunch stage=stage'], 'production', 'none', '0')   // C-6: rollback only on confirmed evidence, never on an unavailable gate
  const planRepair = /^FAILED:plan-needs-repair/.test(String(stop))   // v2.1 V-3: a plan defect found in ANY stage relaunches stage=plan in REPAIR MODE — next_args must agree with the stop_reason, never send the owner to stage=build (C-19)
  const nextStage = planRepair ? 'plan' : stage === 'plan' ? (stop === 'plan-verified' ? 'build' : 'plan') : stage === 'build' ? (ready ? 'stage' : 'build') : stage === 'stage' ? (ready ? 'promote' : 'stage') : (ready ? 'done' : 'promote')   // C-9: a promote that is not ready (rollback, contradicting evidence) re-runs promote; never advances after dry/halt/budget/incomplete
  return { stage, nonce: A.run_nonce, status: (HALT || INTEG_DIRTY || /^FAILED:/.test(String(stop))) ? 'failed' : ready ? 'ready' : 'blocked', halt: HALT, head_sha: head, integration_branch: INTEG, actions, blocked_on_owner, deferred, parked: rows.filter(r => PARKED_RE.test(r.state)).map(r => ({ task_id: r.task_id, state: r.state, reason: r.reason, next: r.next })), rows, api_unresolvable, stop_reason: stop, agents: agentCount, replay_risk: REPLAY_RISK, last_clean_gate: { verdict: lastClean.verdict, head_sha: lastClean.head_sha, digest: lastClean.digest, why: lastClean.why || null },
    next_args: { stage: nextStage, plan_sha: A.plan_sha || null, integration_sha_at_launch: head, resume_mode: REPLAY_RISK ? 'git' : A.resume_mode, prior_status_path: STATUS_JSON, last_clean_gate: { head_sha: lastClean.verdict === 'pass' ? lastClean.head_sha : null, digest: lastClean.verdict === 'pass' ? lastClean.digest : null }, retry_parked_suggested, plan_defects: (planDefects || []).length ? planDefects : [] } }   // v2.1 V-3: populated whenever defects exist, in EVERY stage — the owner relaunches stage=plan with args.plan_defects (REPAIR MODE)
}

// ---------------------------------------------------------------------------------------------
// Main: one run per args.stage
// ---------------------------------------------------------------------------------------------
let head = A.integration_sha_at_launch || A.base_sha, stop = 'not-run', allCards = [], planDefects = []
try {
  phase('Setup')
  const setup = await run('integrator', 'setup', A.run_nonce, P.setup(), { phase: 'Setup', schema: SETUP, effort: 'medium' })
  if (setup.status === 'null' || setup.status === 'FAILED' || !setup.base_sha_ok) throw new Error('setup failed: ' + cap(J(setup), 600))
  if (setup.gate_sha256 !== A.gate_sha256 || setup.baseline_sha256 !== A.baseline_sha256) throw new Error('gate/baseline pin mismatch: the tools dir does not hold the bytes args pin (CG1)')
  if (Math.min(16, setup.nproc - 2) !== CAP) throw new Error('cap-mismatch: nproc ' + setup.nproc + ' → cap ' + Math.min(16, setup.nproc - 2) + ' but args.cap=' + CAP + ' (stale args after a resize?)')
  if (!setup.red_proof.broken_red) throw new Error('gate red-proof failed: the gate is not RED on the broken base (D-14)')
  if ((setup.remotes || []).length && !OA.github_repo_url) throw new Error('remote present without approval: ' + setup.remotes.join(' | ') + ' (F-35 post-check)')
  if (setup.toolchain_status_sha256 && setup.toolchain_status_sha256 !== A.toolchain_status_sha256) throw new Error('toolchain-mutated at setup (status excluding docs/grills differs from P0) — F-1')
  if (A.stage !== 'plan') {
    if (!setup.plan_merged) throw new Error('plan/' + A.run_nonce + '@' + A.plan_sha.slice(0, 12) + ' is not merged into ' + INTEG)
    if (!isSha(setup.integration_head_live)) throw new Error('integration head unreadable')
    if (A.integration_sha_at_launch && setup.integration_head_live !== A.integration_sha_at_launch) throw new Error('stale-launch-args: live ' + INTEG + ' is ' + setup.integration_head_live.slice(0, 12) + ' but args say ' + A.integration_sha_at_launch.slice(0, 12) + ' — recompute args and launch fresh (F-43 as a script invariant)')
    head = setup.integration_head_live
    const liveMerged = new Set(setup.merged_on_integration || [])
    liveMerged.forEach(id => status.set(id, { state: 'merged', reason: 'merged (git)', next: 'none', head_sha: 'on-' + INTEG, dod: [], deferred: [] }))   // git is the truth for "merged"
    const retryParked = new Set(A.retry_parked || []); let autoRetry = 0
    for (const row of setup.prior_rows || []) {      // CG7 + C-8: prior rows add detail only where git agrees; parks persist unless retryable or named in retry_parked
      if (row.state === 'merged+gate-green' && liveMerged.has(row.task_id)) status.set(row.task_id, { state: 'merged', reason: 'merged (git + prior)', next: 'none', head_sha: row.head_sha, dod: [], deferred: [] })
      else if (PARKED_RE.test(row.state) && !liveMerged.has(row.task_id)) {
        if (retryParked.has(row.task_id)) log('resume: ' + row.task_id + ' re-driven (args.retry_parked)')
        else if (RETRYABLE_RE.test(row.reason || '')) { autoRetry++; log('resume: ' + row.task_id + ' was ' + row.state + ' for a retryable reason (' + row.reason + ') — re-driven automatically') }
        else status.set(row.task_id, { state: 'parked', reason: 'prior:' + (row.reason || row.state), next: 'retry_parked or a review fix card', head_sha: row.head_sha })
      }   // not_attempted / blocked_on_owner / dropped_null prior rows are never adopted: they are re-evaluated live
    }
    ;(setup.seen_keys || []).forEach(k => seen.add(k))
    if (A.last_clean_gate && A.last_clean_gate.head_sha === head && isHex64(A.last_clean_gate.digest)) lastClean = { verdict: 'pass', head_sha: head, digest: A.last_clean_gate.digest, wave: 'prior' }
    else lastClean = { verdict: 'gate-unavailable', head_sha: null, digest: null, why: 'no prior pass at this head' }
    log('resume state: ' + status.size + ' prior rows adopted (' + liveMerged.size + ' merged per git, ' + autoRetry + ' auto-retried), seen=' + seen.size + ', lastClean=' + lastClean.verdict)
  }
  log('setup ok: venv=' + setup.venv_python + ' nproc=' + setup.nproc + ' baseline_collected=' + setup.baseline_collected + ' red_proof=' + J(setup.red_proof))

  if (A.stage === 'plan') {
    phase('Plan')
    const unverified = [...A.unverified_finding_ids].sort()
    const ground = await parallel([
      () => run('planner', 'apiledger', A.run_nonce, P.apiLedger(), { phase: 'Plan', schema: VERDICT, effort: 'medium' }, 2 + unverified.length),
      () => run('verifier', 'catalog', A.run_nonce, P.catalog(), { phase: 'Plan', schema: VERDICT, effort: 'low' }, 2 + unverified.length),
      () => pipeline(unverified, fid => run('verifier', 'preverify', fid, P.preverify(fid), { phase: 'Plan', schema: VERDICT, effort: 'medium' }, 2 + unverified.length).then(v => ({ fid, v }))),
    ])
    const [apiLedger, catalog, pre] = ground
    if (!apiLedger || apiLedger.status === 'null' || apiLedger.verdict !== 'pass') throw new Error('api-ledger not written (' + (apiLedger && apiLedger.reason) + ')')
    const preverified = (pre || []).filter(Boolean).map(({ fid, v }) => ({ id: fid, verdict: v.status === 'null' ? 'unverified' : (v.verdict === 'holds' ? 'confirmed' : v.verdict === 'refuted' ? 'refuted' : 'unverified'), corrected_claim: cap(((v.findings || [])[0] || {}).corrected_claim || '', 600), level: ((v.findings || [])[0] || {}).verification_level || 'unverified' })).sort(byId)
    log('grounding: api-ledger ' + apiLedger.verdict + '; catalog ' + (catalog ? catalog.verdict : 'null') + ' (' + ((catalog && catalog.findings) || []).filter(f => /unresolved/i.test(f.title)).length + ' unresolved); pre-verified ' + preverified.map(p => p.id + '=' + p.verdict).join(','))
    const idx = await run('planner', 'plan', A.run_nonce + (A.plan_defects && A.plan_defects.length ? ':repair' : ''), P.plan(preverified, A.plan_defects || []), { phase: 'Plan', schema: CARD_INDEX, effort: 'high' })
    if (idx.status !== 'SUCCESS' || !isSha(idx.plan_sha)) throw new Error('planner failed')
    planDefects = checkPlan(idx, preverified)
    const chk = await run('verifier', 'plan', idx.plan_sha, P.planCheck(idx), { phase: 'Plan', schema: VERDICT, effort: 'medium' })
    if (chk.status === 'null') planDefects.push('plan verifier unavailable (' + chk.reason + ') — a plan is never approved unverified')
    else if (chk.verdict !== 'pass') planDefects.push('plan verifier: ' + (chk.findings || []).length + ' finding(s)')
    stop = planDefects.length ? 'plan-needs-repair' : 'plan-verified'
    log('plan: ' + idx.cards.length + ' cards; ' + stop + '; defects: ' + (planDefects.join('; ') || 'none') + '; plan findings: ' + ((chk.findings || []).length))
    A.plan_sha = idx.plan_sha
    const cp = checkpoint('plan', A.base_sha, stop, planDefects); cp.plan_sha = idx.plan_sha; cp.plan_defects = planDefects; cp.plan_findings = chk.findings || []; cp.preverified = preverified
    phase('Synthesize'); await run('synthesizer', 'synth', A.run_nonce, P.synth([], cp, stop, [], []), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
    return cp
  }

  phase('Plan')
  const idx = await run('verifier', 'index', 'index@' + A.plan_sha, P.index(), { phase: 'Plan', schema: CARD_INDEX, effort: 'low' })
  if (idx.status !== 'SUCCESS') throw new Error('plan index unreadable at ' + A.plan_sha)
  planDefects = checkPlan(idx, idx.preverified || [])
  if (planDefects.length) throw new Error('plan-needs-repair: ' + planDefects.join('; ') + ' — relaunch stage=plan with args.plan_defects (C-19)')
  allCards = A.smoke ? topoOrder(idx.cards).slice(0, 1) : idx.cards
  allCards.forEach(c => CARD_BY_ID.set(c.id, c))
  if (A.stage === 'build') {
    phase('Build'); head = await buildAndIntegrate(allCards, head, 'plan')
    const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
  }
  if (A.stage === 'stage' || A.stage === 'promote') {
    const dir = A.stage === 'stage' ? OA.staging_evidence_dir : OA.production_evidence_dir
    if (!dir) { stop = 'blocked:evidence-dir-missing'; status.set('evidence', { state: 'blocked_on_owner', field: A.stage === 'stage' ? 'staging_evidence_dir' : 'production_evidence_dir', reason: 'no evidence directory', next: 'run the CI evidence job; pass the directory; relaunch' }) } else {
      phase('Review')
      const ev = await run('verifier', 'evidence', A.stage + ':' + A.run_nonce, P.evidence(dir, head), { phase: 'Review', schema: VERDICT, effort: 'medium' })
      if (ev.status === 'null') { stop = 'evidence-unavailable' } else {
        raiseLevels(ev.findings, f => f.title + ' ' + (f.reproduction || {}).command)
        syntheticFindings.push(...(ev.findings || []).filter(f => f.reproduction))
        const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
      }
    }
  }
} catch (e) { stop = 'FAILED:' + String(e && e.message); log(stop) }

phase('Synthesize')                                                                 // always runs, also after every HALT (F-45, C-7)
const cp = checkpoint(A.stage, head, stop, planDefects)
try {
  const seenKeys = [...seen].sort(), ledgerSummary = ledger.map(l => ({ role: l.role, mode: l.mode, id: l.id, attempt: l.attempt, status: l.status })).sort((x, y) => (ledgerKey(x) < ledgerKey(y) ? -1 : 1))
  let s = await run('synthesizer', 'synth', A.run_nonce, P.synth(cp.rows, cp, stop, seenKeys, ledgerSummary), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
  const same = r => r && r.status === 'SUCCESS' && J(r.rows.map(x => [x.task_id, x.state, x.reason]).sort()) === J(cp.rows.map(x => [x.task_id, x.state, x.reason]).sort())
  if (s.status === 'SUCCESS' && !same(s)) { log('SYNTH ROWS DIFFER from the ledger — rewriting the on-disk rows (J1 G13)'); s = await run('synthesizer', 'synthfix', A.run_nonce, P.synthFix(s.report_path, cp.rows), { phase: 'Synthesize', schema: REPORT, effort: 'low' }) }
  if (s.status === 'SUCCESS') { cp.report_path = s.report_path; cp.status_json_path = s.status_json_path; cp.owner_actions = s.owner_actions; cp.rows_consistent = same(s) }
  else { cp.rows_consistent = false; cp.synth_status = s.reason || s.status }
} catch (e) { log('synthesizer threw: ' + String(e && e.message)) }
log('RUN END stage=' + A.stage + ' stop=' + stop + ' head=' + String(head).slice(0, 12) + ' agents=' + agentCount + ' ledger=' + ledger.length + ' dropped=' + ledger.filter(l => /null|timeout|threw/.test(l.status)).length + (HALT ? ' HALT=' + HALT : ''))
return cp
```

Notes for the script author (v1's six notes all still hold, plus the v2 set):
- `lastClean`, `status`, `seen`, `openBlocking`, `probesUsed`, `syntheticFindings`, `HALT`, `REPLAY_RISK`, `INTEG_DIRTY` are module-level `let`/`const` declared before the main block; functions are hoisted, the first call happens in the main block.
- `P.revert(id, head, mergedIds)` is a pure builder (no string surgery on `P.merge` — J1 D3/J2/J3); **in v2 it reverts the recorded `merge_sha`, never HEAD (C-12)**.
- `taskBranch()` is the single helper for every branch the integrator merges, including journeys (J2 A3-1).
- The `verifier mode:'index'` call exists so R1/R2/R3 never depend on R0's return being in cache: a run starts from `args.plan_sha` alone.
- `parallel`/`pipeline` thunks that throw resolve to `null` and never reject (tool contract), which is why an outward action is a `HALT` flag and not a `throw`.
- No `model` override anywhere; if one is ever needed, add it to the call AND to the `meta.phases` entry of that phase (J2 gap 10).
- **`budgetOk(label, exemptFromHalt)` carries an exemption flag used by exactly one caller, the synthesizer (C-7/F-45): after the invocation agent-cap check, an exempt call returns true even under `HALT` and an exhausted budget — the reserve exists to pay for the report.**
- **`checkPlan(idx, preverified)` is called in every stage (C-19); a defective plan yields `repair-plan` in R0 (REPAIR MODE re-run with `args.plan_defects`) and `FAILED:plan-needs-repair` before any author/builder in R1 — a defective plan can never be approved or built.**
- **Fix cards are files: `toFixCard()` writes `plan/fixes/<fixid>.json` with the finding embedded, the integrator `mode:'fixcards'` commits them, and every prompt of the fix chain carries the card content verbatim (C-3) — no prompt ever refers to a card file the gate would have to read but nobody wrote.**
- **`checkpoint()` types every row with `reason` and `next` (C-22); `nextStage` implements the C-9 table (`plan → build|plan`, `build → stage|build`, `stage → promote|stage`, `promote → done|promote`) so a stage that did not finish never advances; `RETRYABLE_RE` is the single definition of "a park nobody ever judged", used identically by the resume auto-retry and by `retry_parked_suggested` (C-8).**
- **`MANIFEST_MIN` is derived from the cards' `new_modules ∪ required_files` (validated at plan time), with card 08a's `worker/penalty.py` included only when `args.torch_in_venv` — the manifest, the CI filenames and the plan cannot contradict (C-14).**
- **`drive.mjs` (the fake harness) replaces v1's `fake-run.mjs` and must be re-run after any control-flow change: 41 scenarios, 107 assertions — the critic's 21 adapted scenarios, 16 aimed at the v2 gaps, and 4 v2.1 scenarios (S38-S41) aimed at critic-v2's majors.**

---

## 14. Authoring checklist the script author ticks before launch (v2)

Script (X):
- [ ] `meta` is a pure literal; every `phase()` title (`Setup, Plan, Build, Integrate, Review, Synthesize`) appears in `meta.phases`; `grep -nE 'Date\.now|Math\.random|new Date\(\)|isolation'` is empty; `node --check` passes on the assembled file (ESM-factory form AND async-IIFE wrap); **`node drive.mjs` passes 107/107** (the fake harness lives next to the script and must be updated with any control-flow change).
- [ ] The §9 schemas are pasted verbatim at the marker; the schema walk (`check_schemas.mjs`) passes (v2: 34 object nodes, 7 roots); no `pattern/maxLength/minLength/minimum/maximum` anywhere.
- [ ] Every `agent()` goes through `run()`; every barrier drop is counted in a `log()`; every loop has a counter before any budget check; `RESERVE`, `AGENT_SOFT_CAP`, `MAX_AGENTS_RUN`, `RESERVE_PER_CHAIN` set; the synthesizer is outside the main `try` **and exempt from the HALT/reserve branches of `budgetOk` (C-7)**; `HALT` is consulted by `budgetOk()`.
- [ ] Prompts contain only `args` values and sorted results; the integration head is in every code-reading prompt; `attempt`/`redrive` suffixes on every retry/re-drive; `launched_at` only in the git-mode setup prompt; no scratch/session paths; **`checkPlan` is called in every stage (C-19); `nextStage` implements the C-9 table; every `checkpoint()` row carries `reason` + `next` (C-22)**.
- [ ] `assertCommon` runs on every return (prefix test + common dir + outward → `HALT` + installs); **receipt-shaped fragments are logged, not nulled (C-23)**; `redact()` runs before anything reads a return; **the prompts fix the `TESTTOKEN-` dummy-credential convention (C-32)**.
- [ ] `taskDone()` (twelve conditions; diff_stats fail-closed, C-25), `mergeOk()` (requires `merge_sha`, C-12; `already-merged` evidence-checked, C-20), `satisfied()` (tree-complete + `ownerCritical===0`, C-5/C-6), fingerprints (never empty, C-18), `seen`, `topoOrder`, `rankCards`, `waves` (recomputed from live status, C-5; integration order `(−rank, id)`, C-24), `validateCards` (ownership rule, C-21; `est_lines` size classes, C-13; `expected_green_tests` only for lens-4 §F pins, C-13; bootstrap false everywhere), `raiseLevels`, `checkpoint()` are code; no agent decides "new", "done", "ready" or "satisfied"; `promote-production` only from `ready` with the F-38 field (and `ready` false over a confirmed critical/high staging finding, C-6).

Args (P0):
- [ ] `build_repo=/workspaces/space-build` at `base_sha` (full sha), outside the grill folder and the toolchain repo; `libsrc` durable and read-only; `tools_dir` holds `gate.sh` (the §7.2 bytes) and `baseline.json`; `gate_sha256` and `baseline_sha256` computed with `sha256sum` and passed in args; **the venv is CREATED here, once, and every later stage only ever asserts it exists (C-31)**; the wheel list is the v1 list **plus the CPU torch wheel only if Q2 says so, recorded as `args.torch_in_venv` (C-14)**.
- [ ] `cap = min(16, nproc − 2)`, `wave_size ≤ cap`, `max_agents_this_run` (110 at cap 2), `resume_mode='git'` until the settling experiment passes; **`toolchain_status_sha256` computed with `docs/grills` excluded (C-17)**; `unverified_finding_ids`, `against_recommendation_ids`, `catalog_candidates` filled; `owner_approvals` present with nulls; `run_nonce`, `launched_at` set.
- [ ] The trigger message states the `AUTHORITY` rules and contains no secret; the P0 regex scan over every input file is clean; the journal export path is scanned before any copy into `evidence/`.

Owner (O), recorded as actions, never done by agents:
- [ ] Stop notice sent; both Windows scheduled tasks disabled; the other agent's token rotated; the pasted token revoked; `NF4_EXPORT`/`NF4_UPLOAD_TOKEN` deleted; HF connector write tools disabled; `gh repo list` + namespace listing snapshotted; Codespace idle timeout at the maximum with a client attached; resize done or consciously deferred (Q1).
- [ ] `plan/decisions.json` (incl. the clarification rows) and `plan/index.json` read and approved → `args.plan_sha` (or `plan_defects` returned for a REPAIR MODE re-run, C-19); the answers to Q2/Q4 given before R1's first invocation (they change cards 06/07/08a/08b).
- [ ] Fixture #1 recorded after cards 01-03b merge; **the persona boundary fixture generated off-workflow with card 01's tool and BOTH fields recorded — `persona_boundary_fixture_path` and `persona_boundary_fixture_sha256` (C-21)**; the worker checkpoint decided — each passed as an `owner_approvals` field before the next invocation.

Gate (G):
- [ ] `baseline.json` holds `baseline_collected` (expected 73) and the `skipped_ids` set at `base_sha`; the dry run of §7.2 reproduces the same `LEDGER_DIGEST` twice; **`tools/gate.pin` matches `gate_sha256`**.
- [ ] `tests/protected.txt` (card 01) lists EXACTLY the script's `PROTECTED` constant, one path per line — ONE list, two renderings, and the plan verifier refuses a divergence (v2.1 V-5): `tests/test_personas.py`, `tests/test_constants_pin.py`, `tests/test_import_contract.py`, `tests/test_python_eval_surfaces.py`, `tests/test_catalog_policy.py`, `tests/fixtures/gate/false-claim.patch`, `tests/fixtures/gate/false-claim-target.txt`, `tests/fixtures/persona_boundary.json`, `tests/journeys/conftest.py`, `tests/protected.txt`, `tools/gate.sh`, `tools/gate.pin`, `tools/baseline.json`, `tools/baseline.pin`, `tools/make_boundary_fixture.py`, `ruff.toml`, `pytest.ini`, `.gitattributes`, `.editorconfig`, `.gitignore` (the §4.6 `config.py` skeleton is owned through card 01's manifest, C-13/C-14, and is not itself a protected path).
- [ ] `pytest.ini` excludes `tests/live/` and **registers the `journey` marker under `markers` AND deselects it from every default run (C-4; v2.1 V-2 — an unregistered marker is a PytestUnknownMarkWarning)** and defines the `staging_required` marker; **card 01's DoD runs BOTH collections (`--journeys` over a one-file smoke journey AND the default suite, both green) so an inert or over-scoped marker fails card 01, never the first seam wave**; card `platform-01-gate` is the only card with `protected_touch` true **and `bootstrap` is false on every card (the profile exists only for the P0/setup red-proof)**; `REQUIRED_AFTER` in the script **is the cards' `new_modules ∪ required_files`, validated against `MANIFEST_MIN` (C-14)**; **every merge gate carries `--journeys` and every clean gate carries `--journeys --lint-base <last clean pass> --boundary-sha256 <hex>` (C-4/C-15/C-21)**.

---

## 15. Open questions for the owner (only those whose answer changes the build)

| # | Question | What changes |
|---|---|---|
| Q1 | Resize the Codespace (16-32 cores → cap 14-16) BEFORE R1? | `args.cap`/`wave_size`; ≈ 28-29 h in 5-7 invocations at cap 2 vs ≈ 20-22 h in 2-3 at cap 14 (§11, v2.1 V-10 re-derivation); the script is identical. |
| Q2 | Add a CPU `torch` wheel to the gate venv at P0 (one-time, ≈ 200 MB) so `PresencePenalty` (inference-perf-3 CORRECTED), the stop-event `StoppingCriteria` and the continuation seam get real-tensor CPU tests — or remove the `presence_penalty` placebo (slider, preset key, README sentence; API 400 unless 0)? Default if unanswered: remove. | Card 08a's content **and its manifest entry (`worker/penalty.py` exists in `MANIFEST_MIN` only when `args.torch_in_venv`, C-14)**; cards 06/07's `out_of_scope`; the venv recipe in §14. |
| Q3 | G-18 MCP: keep the narrow `ask/poll/status/preflight` surface (card 11, seam H3) or `mcp_server=False`? | Card 11 and H3 exist or are dropped; `gradio[mcp]` enters the venv or not. |
| Q4 | Token topology (G-24-clar): can one fine-grained HF token carry both the inference-provider scope and read access to the private worker Space? If not, approve a second read-only worker token. | Card 08b's env contract (`HF_TOKEN` vs `WORKER_TOKEN`); the C1 `set-staging-secrets` steps; the decision sheet row. |
| Q5 | G-25 prompt-injection defaults: web tools default OFF and `http_request` GET-only (lens-4 §E), or as-is? | Default flag values card 09c writes and the `out_of_scope` lines of 05a/09c. |
| Q6 | Is the local `/usr/bin/python3.12` (3.12.3) acceptable as the gate interpreter although the Space image is 3.12.12, with the resolution difference caught by the R2 evidence reader? | If not, P0 must fetch a 3.12.12 build (network, ~30 MB), one more UNVERIFIED-until-downloaded dependency. |
| Q7 | Worker checkpoint (C0-4): which candidate is the resident model, and if neither the FP8 copy nor the GPTQ 27B carries `model.visual.*`, approve the VLM-class export HF Job (paid) before staging? | Card 08c's entry, `needs_export`, the C2 cost estimate; without vision tensors the worker cannot serve images (G-16). |
| Q8 | Budgets for R2/R3 as `owner_approvals` fields: `hosted_call_budget_usd` (harness), `hf_job_budget_usd`, `gpu_seconds_budget`. | The harness preflight refuses anything above them; the C2 actions quote them. |
| Q9 | Approve the two clarifications recorded as decision rows: `M-3-clar` (pending catalog entries hidden; ≥ 1 passed entry before promotion) and `Continue-clar` (token-level continuation; `continue_final_message` only for a finished non-thinking user Continue)? | Cards 08a/13a and seams H1/H5; a different answer re-opens gpu-lease-3/critic-4 and the release-1 catalog content. |
| **Q10 (new in v2)** | **Policy for confirmed MEDIUM/LOW staging-evidence findings: block promotion exactly like critical/high, or record-and-defer when the owner explicitly lists the finding id in `owner_approvals.accepted_findings`?** The mechanism ships either way (C-6): critical/high always block; a listed medium/low id is typed `deferred` with the owner's acceptance recorded; an unlisted one becomes `blocked_on_owner`. Default if unanswered: accepted-findings carving works as designed (it cannot touch critical/high). | Only the staging stop rule's threshold in §6.2 and the C2 checkpoint wording; no structural change — flipping to "block on everything" deletes one predicate clause. |

---

## Appendix A: judge work-list resolution

Every item from the three judgements, mapped to the section that resolves it or to a one-line reasoned decline. "§" references are into this document. **A.1-A.5 are carried from v1 verbatim** (the judges' reports remain the standard for anything the critic did not mention); where the critic's §4 audit of this table found a v1 closure deficient, the fix is recorded in A.0 and its gap id points into Appendix B.

### A.0 The v2 audit of this work-list (what the reviser re-verified against the critic's audit)

| Audit finding (critic §4) | v2 closure |
|---|---|
| J1 A3-4 closure "half-real" (the F-11/F-10 rows were prose in v1's stage flow) | `checkPlan()` now executes in every stage (C-19: REFUTED-id and manifest checks throw in R0 **and** R1; drive S17/S17b/S17c), and the idiom clearance stays a `taskDone()` condition fed by the gate's `IDIOM_HITS` |
| J1 G13 "real except after HALT" | C-7: `budgetOk(label, exemptFromHalt)` — the synthesizer runs after every HALT (drive S4/S8c) |
| J1 G2 decline "stands, but resume holes remain" | C-8/C-10/C-22: retryable parks auto-retry on resume, a clean gate is re-run before reviewing when the last one is not a pass at head, and every row carries reason + next (drive N5/S7b/N6) |
| J1 G7 "the prose was real, the mechanism dead" (journeys) | C-4: a separate pytest collection, default-deselected, `--journeys` at every merge + clean gate, `needs=` counted by the gate (drive S16/N1) |
| J1 CG9/CG10 "real but contradictory" (floors vs plan) | C-14: the manifest is derived from the cards (`new_modules ∪ required_files`), `worker/penalty.py` conditional on `args.torch_in_venv`; `validateCards` checks plan-vs-manifest coverage |
| J1 CG6 decline "stands" | unchanged (digest equality is the cross-check); not re-litigated |
| J2 A3-1 (journeys branch mismatch) | C-4 mechanics: `taskBranch()` retained and the journeys merge gate carries `--journeys` (drive S1 asserts every merge gate command has it) |
| J2 A3-2 (clean-gate null → revert) | C-11: three-way typing; a null/malformed/contradicted return is `gate-unavailable`, never a revert (drive S6/S6b/N2) |
| J2 A3-4 (R2/R3 `satisfied()` unreachable / promote from failed) | C-6 + C-10: `lastClean` seeded only at the same head, evidence findings through the loop, `ready` false over confirmed critical/high (drive S15/N8) |
| J2 gap 8 (budget throw) | C-7 again: no fan-out of instant throws, but the synthesizer still runs |
| J2 gap 12 (unchecked revert) | C-12: the revert targets the recorded `merge_sha` and its result is checked (drive N3/N4) |
| J2 graft 3 (rankCards) | C-24: the same `(−rank, id)` key orders integration, not just waves (drive S1 asserts wave 2 = [03a, 02] by rank) |
| J2 graft 15 (validateCards) | extended per C-13/C-14/C-21: size classes, manifest coverage, ownership rule, `expected_green_tests`, bootstrap-false |
| J2 graft 6 decline (timing) | stands: returns stay timestamp-free; the orchestrator computes durations from the run record after the run |
| J1 D5/G-15(5) "the §C DoD regex is weak" | noted; the §C greps stay plan-verifier-checked (C-19 re-checks them), and the idiom lint's v2 scoping (C-15: `--lint-base..HEAD`, comments stripped) stops it firing on legitimate lines such as a quoted `continue_final_message` in prose |
| J3 Continue-clar "the blocking idiom fires on legitimate lines" | C-15: comment stripping + range scoping; the blocking regex still fires on real call sites |
| J3/C-Q "the boundary tool was unowned" | C-21: card 01 delivers `tools/make_boundary_fixture.py`; the owner records `persona_boundary_fixture_path` AND its sha256; the gate pins it |
| J3 CG-31 "the `/healthz` sha source was ambiguous pre-CI" | C-34: card 03b ships a placeholder `build_info.json` (`git_sha: "unknown"` — rejected by the canary), CI writes the real one |
| A.5's v1 rows "real but unproven" | each is now drive-checked; A.5 below gains the three defects the v2 drive caught in my own drafts |
| "the v1 drive's 19 assertions are not auditable" | the v2.1 drive (`drive.mjs`, 41 scenarios, 107 assertions) and its full log live beside the design in the scratch dir and are re-runnable (`node drive.mjs`); Appendix C lists every scenario and every annotation |

### A.1 Judge J1 (red-team)

**Blocking defects in A3 (J1 §2)**

| # | Item | Resolution |
|---|---|---|
| A3-1 | `assertCommon` nulls every worktree agent (`repo_toplevel === R`) | §10.5 / §13 `assertCommon`: prefix test `startsWith(R + '-wt/')` plus `git_common_dir === R/.git` (the store identity, so a worktree of another repo cannot pass); the drive exercises a `-wt/x` toplevel on every return. |
| A3-2 | test-count and skip floors inert or spuriously red (`.gate/base.json` only in the main checkout) | §7.2 `--baseline <path> --baseline-sha256`, mandatory in full mode, fail closed; skip rule became a SET rule vs `baseline.skipped_ids` and `xfail_allowed`; `except: base = {0,0}` deleted. Dry run: tampered baseline → RED. |
| A3-3 | mutants optional | §7.2 `--mutants`: written ≥ 1, all applied, all killed, tree unchanged; §5 condition 6. |
| A3-4 | F-11 and F-10 rows prose | §1.4/§2.1/§13: `pipeline(unverified_finding_ids, verifier mode:'preverify')` before the planner; REFUTED ids refused in JS (v2: `checkPlan()` in every stage, C-19); `IDIOM_HITS` in the ledger + condition 9; `corrected_text` required per cited finding. |
| A3-5 | stale re-drive replays the stale result | §4.4/§13 `redriveLine(k)` on every prompt of a re-driven chain (`buildTask(c, head, merged, 1)`). |
| A3-6 (minor) | external gate copy unpinned; `judged.filter(Boolean)` unlogged; on-disk RUN-REPORT not rewritten; `pgrep -f "python.*$REPO"` inert | CG-1 pin (+ `tools/gate.pin`); §13 `judgeDrops` log line; `synthesizer mode:'fix'` rewrite (F-40); kill scoped to `/proc/<pid>/cwd == $REPO` (CG-2). |

**Adversarial constructions (J1 §3), status now:** (a) ship the f88b120 pattern — the optional-mutant hole is closed (condition 6) and the oracle reset makes the author's suite the one that runs; (b) fix-loop spin — unchanged (cannot spin); the soft spot "a parked fix card keeps `satisfied()` false until max-rounds" is bounded and now also visible in the checkpoint as a parked row with reason + next; (c) leak a secret — closed at the gate and in every structured return (`redact()`, condition 11; v2: the `TESTTOKEN-` dummy convention, C-32); (d) outward action — `HALT` (works inside barriers), `git remote -v` post-checks, owner Hub checks (**O**), and the synthesizer still reports after the HALT (C-7); (e) drop a null — honoured everywhere, including the clean gate (three-way typed, C-11), the veto judge and the evidence reader; (f) stale cache — resume modes + `stale-launch-args` + `redrive:` suffix, and prior rows are detail, never truth (C-8).

**Graft list (J1 §6)**

| # | Graft | Resolution |
|---|---|---|
| G1 | A1 canonical digest + two-execution equality | §7 (digest over the timestamp-free canon; dry-run verified) + §5 condition 3 + confirm-RED equality (C-29). |
| G2 | A1 state probe before consuming any cached sha | **Applied as one live probe per invocation, not two agents per card** (§1.2, §1.4, §2.3, §10.1): a per-card probe replays from the same cache it would check; the setup probe carries `launched_at` in `git` mode, returns live heads/merged ids/remotes, and JS refuses a stale launch sha. |
| G3 | A1 oracle reset diffed against the oracle, not the base; tamper-scan idioms | §7.2 step 4 (`--oracle`) + author-range tamper rules in `--only-tests` + builder-test tamper idioms in step 8. |
| G4 | every acceptance id exit 0 on both sides; mutants exist and all die; negative control red | §5 conditions 6, 7, 8 (`dod_reruns[]`, `--revert-proof`; v2: the test set includes builder-added `tests/unit/*`, C-28). |
| G5 | pre-verifier pipeline over UNVERIFIED findings | §2.1 R0, §13 main (plan stage). |
| G6 | JS keyword raise of `verification_level` | §13 `raiseLevels()` in `validateCards` and on every returned finding/DoD line. |
| G7 | held-out seams H1-H7 as the journeys spec | §4.8; `JOURNEY_NEEDS`; journeys author per seam wave; v2: the separate collection + gate counting (C-4). |
| G8 | A2 `semantic()` extras | §5 conditions 5, 8, 10; receipts logged not nulled (C-23); `veto` needs a reproduction (§6.2; v2: non-zero-exit, C-27). |
| G9 | recorded `--profile bootstrap`, rejected for non-bootstrap cards | §7.2 (`profile` in the ledger and the digest) + condition 4 + `validateCards` (`bootstrap` false on every card). |
| G10 | gate integrity extended with `args.gate_sha256` | CG-1: the gate self-checks; `gate_sha256_observed` compared in `taskDone()`/`mergeOk()`; the integrity step compares the repo copy to the pin and `tools/gate.pin` exists. |
| G11 | `maxAgentsThisRun` slices + chain-level reservation | §2.3, §13 `agentsOk(label, need)` with `RESERVE_PER_CHAIN = 7`; v2: sliced cards are `not_attempted`, auto-retried (C-8). |
| G12 | confirm-RED failure-class recording | §7.2 `--only-tests` records `classes=` in the ledger summary; rc 1/2 only count. |
| G13 | synthesis verifier as a file-rewriting probe | §13 `synthesizer mode:'fix'` when rows differ; `rows_consistent` in the checkpoint; runs after every HALT (C-7). |
| G14 | idiom-warning clearance in JS | condition 9 (`warnings_cleared.length ≥ idiom_hits`), over the v2-scoped lint (C-15). |
| D1 | prefix test / common dir | done (A3-1). |
| D2 | baseline from args, fail closed; distinguish xfails in new files | done (A3-2; `xfail_allowed` per card; set rule). |
| D3 | real `P.revert` | §13 `P.revert(id, head, mergedIds)`; result checked (CG-24); v2: targets the recorded `merge_sha` (C-12). |
| D4 | `attempt` suffix on stale/author re-drives; mutants mandatory | done; v2: the author re-drive carries the red verdict (C-26, drive N11). |
| D5 | log `judged.filter(Boolean)`; clean-gate toolchain check in JS | done (`judgeDrops`; toolchain mismatch → `HALT`, `docs/grills` excluded, C-17). |
| D6 | consider dropping the per-wave journeys author | **Partially taken:** the author runs only for waves in which a seam card merged (≈ 6-8 per R1), not per wave. |

**Common gaps (J1 §7):** CG1 → CG-1; CG2 → CG-2; CG3 → CG-3; CG4 → CG-4; CG5 → CG-5; CG6 → CG-6 (declined as an agent, covered by digest equality); CG7 → CG-7; CG8 → CG-8; CG9 → CG-9; CG10 → CG-10 (v2: the manifest is the plan, C-14); CG11 → CG-11; CG12 → CG-12.

**Per-row ◐ verdicts on A3 (J1 §8) now closed:** F-8 (apicheck also runs on the builder's `apis_used` as the separate `apicheck-extended` entry, every entry needs a `ledger_ref` — condition 12; v2: wheel-SOURCE resolution, C-16); F-13 (condition 10, fail-closed, C-25); F-20 (fixture #1 precondition; mutants mandatory); F-26 (scoped kill); F-37 (`raiseLevels` in JS); F-43 (resume modes; v2: retryable parks auto-retry, C-8); F-47 (journeys branch unified; the 107-assertion drive); D/AP-1 (receipts logged, not nulled, C-23); T/AP-11 (drops counted, `fixcards-unavailable` included).

### A.2 Judge J2 (tool contract)

**Contract-violation table for A3 (J2 §1b), rows that were ◐/✗**

| Row | Resolution |
|---|---|
| schemas: `pattern/maxLength/minLength/minimum/maximum` UNVERIFIED | §9: removed; JS enforcement; CG-17. |
| `log()` silent spots (`dropped_null` chains; journeys merge failure) | §13: both logged with counts/reasons (v2: `fixcards-unavailable` typed and logged, C-3). |
| journeys branch mismatch | §13 `taskBranch()` used by the journeys author and the integrator; v2: `--journeys` on the merge gate (C-4). |
| stale re-drive identical prompts | `redriveLine`. |
| fail-closed on dropped verdict agents (clean-gate null → revert; veto null fail-open; confirm-RED null misattributed to the author) | §4.5/§6.2/§13: `gate-unavailable` without revert (three-way typing, C-11); `veto-unavailable`; a red-verifier null is `agent-null:red`, not an author re-drive — and an author re-drive now carries the red verdict (C-26). |
| R2/R3 `satisfied()` unreachable; `promote-production` emitted with `status:'failed'` | §6.2: `lastClean` seeded from `args.last_clean_gate` only at the same head (C-10); evidence findings routed through the loop with the C-6 stop; §2.2 `promote-production` only from `ready` + F-38 field; drive S15/N8 asserts both. |
| `NEED` incomplete | §13 `NEED_ALL` + `NEED_BY_STAGE`, every interpolated arg listed. |

**Blocking defects (J2 §3, A3 1-5):** 1 journeys → `taskBranch` (+ C-4); 2 clean-gate null → `gate-unavailable` (C-11); 3 veto null → `veto-unavailable`; 4 R2/R3 → §6.2 (+ C-6); 5 stale re-drive + `NEED` → done.

**Graft list (J2 §6)**

| # | Graft | Resolution |
|---|---|---|
| 1 | A2 gate steps 13-15 (`--journeys` with `needs=`, gate integrity, `--self-test` on every clean gate) | §7.2; `P.clean` passes `--clean --self-test --journeys`; v2: `--journeys` also on every merge gate and `needs=` counted by the gate itself (C-4). |
| 2 | `semantic()` + `STAGING_RE` level forcing in JS | conditions 5/8/10; `raiseLevels()`; receipts logged (C-23). |
| 3 | `rankCards` longest-path ordering inside barrier waves | §4.3, §13 `rankCards`/`waves`; v2: the same key orders integration (C-24) and `readyWave()` is recomputed live (C-5). |
| 4 | R0 grounding trio | §2.1 R0, §13 plan stage (`parallel([apiLedger, catalog, pipeline(preverify)])`). |
| 5 | cache-key settling experiment + `maxAgentsThisRun` slicing | §2.0 step 8, §2.3, §10.1. |
| 6 | `t_start`/`t_end` timing + waste ratio | **Declined:** the returns carry no timestamps by design (T-AP-9); the orchestrator computes per-role durations from the run record's `queuedAt/startedAt` after the run (research-2 §1.4) and writes `timing-<nonce>.json` outside the script — same data, no volatile prompt content. |
| 7 | incremental bundles `<prev>..HEAD` | §4.4/§13 `P.merge` (v2: outside the grill tree, C-17). |
| 8 | `fingerprint()` sha normalisation | §13 `fingerprint` (`[0-9a-f]{7,40}` → `SHA`) — v2: never empty (C-18). |
| 9 | A1 digest + condition 4 | done (G1). |
| 10 | locked-oracle reset + tamper idioms | done (G3). |
| 11 | `revert_proof` + `negative_control` | done (G4; every mutant is a negative control; test set includes `tests/unit/*`, C-28). |
| 12 | `probesUsed` to the inversion mandate | §6.2/§13 (`probes_used[]` on review/veto returns; `P.veto(..., probes)`). |
| 13 | fail-closed judging | `veto-unavailable`. |
| 14 | H1-H7 as the journeys spec | §4.8 (v2 mechanics, C-4). |
| 15 | `validateCards` throwing at script start | §13 `validateCards` (ids, steps, DoD shape and flags, size classes C-13, manifest-vs-plan coverage C-14, ownership rule C-21, `bootstrap` false, `corrected_text`, security DoD line, level raise, topo). |

**Drop-or-fix list (J2 §6):** journeys branch name ✓; clean-gate null ✓ (C-11); veto null ✓; R2/R3 `satisfied()` ✓ (C-6/C-10); `attempt` suffix / `dropped_null` log / `NEED` ✓; `P.revert` ✓ (C-12); `withTimeout` kept with timeouts sized from queue depth (`tmo()`) and a replay-divergence marker (`REPLAY_RISK`) ✓.

**Common gaps (J2 §7):** 1 → CG-13; 2 → CG-14; 3 → CG-15; 4 → CG-16; 5 → CG-17; 6 → CG-18; 7 → CG-19; 8 → CG-20; 9 → CG-21; 10 → CG-22; 11 → CG-23; 12 → CG-24 (v2: merge_sha, C-12).

### A.3 Judge J3 (program fit)

**Blocking defects (J3 §3, A3 1-5)**

| # | Item | Resolution |
|---|---|---|
| 1 | F-11 guard only in the matrix | pre-verifier pipeline (G5); v2: re-checked every stage (C-19). |
| 2 | G-15 point (5) missing | §4.0 row G-15+G-24 (verbatim), card 05a DoD line + `tests/test_python_eval_surfaces.py` (protected, in the manifest), seam H4, `validateCards` requires a surface/operator-flag DoD line on every `risk:'security'` card. |
| 3 | Continue via chat template contradicts gpu-lease-3/critic-4 | §4.0 `Continue-clar`; card 08a token-level control record + `prefix_ids` + CPU test; seam H1; `continue_final_message=…(think|reasoning)` is a blocking idiom — v2: scoped so it no longer fires on legitimate prose (C-15); critic-4 is pre-verified in R0. |
| 4 | VLM class never stated | §4.0 `G-16-clar`; cards 08b/08c; R0 `has_visual_tensors`; gate catalog step; `prefill_chunk_size` blocking; C0-4/C1-6 decision; §15 Q7. |
| 5 | G-3 never named; Q4 defers the API lane | §1.3 C-N: Q4 deleted; G-3 in the sheet with `against_recommendation: true`; cards 07/11/12/13a/14 stay in R1. |

**Graft list (J3 §7)**

| # | Graft | Resolution |
|---|---|---|
| 1 | A2 §4a decision sheet in the design with A1's `against_recommendation`/`dq_line` | §4.0; JS asserts the five marks — v2 in every stage (C-19); `verifier mode:'plan'` refutes rows vs the DQ lines. |
| 2 | card table with CORRECTED ids + ship-but-flag list with pin rows | §4.2, §4.6 (v2: the pins are green inside card 01 via the `config.py` skeleton, C-13). |
| 3 | gate steps 14-15 + scan of the gate's own logs | §7.2 (integrity + self-test; v2: `tools/gate.pin`; v2.1: the card-01-delivered fixture with the gate-crafted commit message, C-2/V-4). |
| 4 | apicheck known-bad list + `STAGING_RE` at return time | §7.2 step 3 reads `plan/api-ledger.json.known_bad[]`; `raiseLevels()`; v2: wheel-SOURCE resolution + `unresolvable-needs-torch` (C-16). |
| 5 | R0 catalog-provenance agent saving raw Hub reads | `verifier mode:'catalog'` (§13), `evidence/catalog/*.json` — v2 also copied into the repo by card 13a (C-34), `unresolved` after 3 tries. |
| 6 | `maxAgentsThisRun` + timing instrumentation | slicing ✓ (v2: sliced cards retryable, C-8); timing computed by the orchestrator from the run record (see J2 graft 6). |
| 7 | timestamp-free digest | done. |
| 8 | H1-H7 as journeys | done (v2: the separate collection, C-4). |
| 9 | pre-verifier | done (C-19). |
| 10 | VLM-class statement + Q6 as a worker-card precondition | done (blocking 4; §15 Q7). |
| 11 | locked-oracle reset + assertion-loss detection | done (G3; builder-added tests with skip/xfail/`except: pass` → RED; revert-proof includes them, C-28). |
| 12 | canary contract with the visibility tripwire | §2.1 (R2/R3 paragraph), §8 `EXPECTED.json` (v2: from `tools/expected.py`, written by CI, C-35), card 14, S-AP-12. |

**Drop-or-repair list (J3 §7):** `P.revert` ✓ (C-12); Q4 deleted (C-N) ✓; G-15 (5) verbatim in card 05a ✓; F-11 code ✓ (C-19); chat-template resume replaced by the token-level control record ✓.

**Common gaps (J3 §8):** 1 → CG-25 (C-O; §15 Q4); 2 → CG-26; 3 → CG-27 (C-S; §15 Q2; v2: wired into MANIFEST_MIN, C-14); 4 → CG-28 (§4.7; v2 re-checked every stage, C-19); 5 → CG-29 (C-Q; v2: C-21); 6 → CG-30 (C-M; v2: field/why/next on the row, C-22); 7 → CG-31 (v2: placeholder build_info.json, C-34); 8 → CG-32 (C-P; §15 Q9); 9 → CG-33; 10 → CG-34 (§15 Q6). J3 §2's shared soft spot (the local row for `backends/worker` is thin): the fake-worker conformance row and seam H1 on the fake worker are the local proof; the queue/`x-ip-token` identity trap under M-2 is a `staging-required` row of card 08b (H2 covers the `/v1` side locally).

### A.4 Declined items (all of them, with the reason)

| Item | Reason |
|---|---|
| J1 G2 / work-list "state probe before/after each card" as agents | A per-card probe is issued with the same prompt on every resume and therefore replays from the cache it is supposed to check; under a positional cache a live probe early in the sequence would also invalidate everything after it. Folded into one live setup probe per invocation + JS checks + `missing-ref` re-drives (§10.1); the resume holes the critic flagged are closed by C-8/C-10/C-22 instead. |
| J1 CG6 "bash ledger reader" probe | It would re-read a file written by the agent under test; the two-execution digest equality (§5 condition 3) is the independent signal. |
| J2/J3 `t_start`/`t_end` in every return + waste ratio inside the script | Timestamps in returns are volatile prompt content (T-AP-9); the same numbers come from the run record after the run, computed by the orchestrator. |
| J1 D6 drop the journeys author entirely | Kept, but only on seam waves (≈ 6-8 per R1); S-AP-4 needs the seams written after the wave. |
| Separate refuter panel, auditor, critic, judge panel, per-wave LLM review, transcript monitor, `mutmut`, hidden branch ACL, `isolation:'worktree'`, plan-critic role, inversion scout, cross-vendor judge (A3 §1.4 cuts) | Unchanged; no judge asked for them back; §1.4 names the covering mechanism for each — and the v2 additions (fixcards, `checkPlan`, the drive) are mechanisms inside the existing six roles and one gate, not new scaffolding. |

### A.5 Defects found by the synthesizer's own checks (not in any judge list)

| Found by | Defect | Fix |
|---|---|---|
| fake drive | `checkpoint.status === 'ready'` while cards were `blocked_on_owner` | `complete` predicate (§2.2). |
| reading the tool contract | an outward-action `throw` inside a `parallel`/`pipeline` thunk resolves to `null` and never aborts | `HALT` flag consulted by `budgetOk()` (§10.5). |
| reading the prompts | cards lived on `plan/<nonce>`, but gates read `plan/cards/<id>.json` from worktrees that did not contain it | setup merges the plan branch into `integration/<nonce>`; `plan/` immutable during a run (gate step 8). |
| fake drive (stage) | the merged set on a fresh invocation came only from a status file | `merged_on_integration` from `git ls-tree` seeds `status`; the file adds detail. |
| gate dry-run design | the self-test's inner run went RED for a missing baseline, making `false_claim_red` vacuous | pins passed to the inner run; the RED must come from the `claim-lint` step (verified from the inner ledger). |
| v2 drive | the gate's protected-ownership rule and `validateCards` disagreed on who may write a protected path (a card with the file in its manifest failed validation) | one ownership rule in both: a protected hit is legal iff the path is in the card's own manifest (`MANIFEST_MIN[id]`) or the card carries `protected_touch` (C-21). |
| v2 drive | the synthesizer was skipped whenever `HALT` was set or the budget was exhausted — the reserve existed but could not be spent on it (C-7/F-45) | `budgetOk(label, exemptFromHalt)`: the exempt caller returns true after the agent-cap check, so the report is always written (drive S4/S8c). |
| v2 drive | a not-ready `promote` run advanced `next_args.stage` to `done` — the C-9 violation in my own first draft | `nextStage`: `(ready ? 'done' : 'promote')` — a stage that did not finish never advances (drive N8/S15). |

---

## Appendix B: Changes in v2 — every critic gap mapped to its resolution (C-1..C-38; 0 declines)

| id | Sev | Gap (critic) | Resolved in |
|---|---|---|---|
| C-1 | blocking | `import-app` RED by construction (card 03b owns `api/app.py`; every earlier card's gate red) | §7.1/§7.3: the step is conditional on `[ -f api/app.py ]`; §4.2 card 03b ships the placeholder `build_info.json` and its own gate command runs both collections; dry-run + drive S1/N2 |
| C-2 | blocking | the self-test's false-claim fixture produced zero claims (vacuous red) | §7.3: the fixture pair is delivered by card 01 (v2.1 V-4 correction — the gate creates only the temp worktree), the gate crafts a commit message matching the claim-lint regexes over a patch that does not change the symbol; `false_claim_red === 'true'` asserted from the inner ledger; dry-run |
| C-3 | blocking | review fix cards were in-memory; `cardRef` named a file nobody wrote; prompts lacked the finding and DoD | §3 (`fixcards` mode), §4.1 (`path`), §4.4, §5/§6 (`toFixCard` → `plan/fixes/`, prompts carry content verbatim); drive S12/N1 |
| C-4 | blocking | journeys collected by the default suite; `needs=` skips RED vs baseline; merge gates lacked `--journeys` | §4.8 (marker conftest + deselect), §7.1/§7.3 (`--journeys` everywhere, `skipped_other`); drive S16/N1 |
| C-5 | blocking | the DAG was asserted only at plan time; dependents of parked roots got built; lenses spent on incomplete trees | §4.3 (`readyWave()` from live status), §6.2 (`tree-incomplete` pre-check); drive S13/N5/N12 |
| C-6 | blocking | R2/R3 emitted `ready`/`promote-production` over confirmed critical/high staging findings | §2.1/§6.2 (`ownerCritical === 0`, `blocked-on-owner:staging-evidence`, rollback on confirmed evidence only); §15 Q10; drive S15/N8 |
| C-7 | major | the synthesizer never ran after HALT | §10.2/§13: `budgetOk(label, exemptFromHalt)`; drive S4/S8c |
| C-8 | major | starvation became permanent parks; rows carried no reasons | §2.3/§10.1 (`starved` → `not_attempted`, `RETRYABLE_RE` auto-retry, `retry_parked_suggested`); §2.2; drive N5/N6 |
| C-9 | major | `next_args.stage` advanced after dry/budget/halt stops | §2.2/§13 nextStage table; drive S7/N7/N8/S8 |
| C-10 | major | no clean-gate re-run when the last was not a pass at head | §6.2 pre-check; §2.1 seeding only at the same head; drive S7b/N3 |
| C-11 | major | malformed clean-gate returns reverted good merges | §4.5/§10.2 three-way typing (incl. exit 0 contradicted by the self-test); drive S6/S6b/N2 |
| C-12 | major | reverts targeted HEAD (wrong after a journeys merge) | §4.4/§4.5: `merge_sha` recorded and targeted, result checked; drive N3/N4 |
| C-13 | major | card 01 could not satisfy its own gate | §4.1/§4.2/§4.6: `expected_green_tests` both ways, `config.py` skeleton, size M, `LEDGER_DIFF_STATS` exclusions; dry-run |
| C-14 | major | `REQUIRED_AFTER` contradicted the plan | §4.1/§13: `MANIFEST_MIN` derived from the cards, conditional on `args.torch_in_venv`; §2.0/§14 |
| C-15 | major | the idiom lint re-scanned all history | §7.1/§7.3: two tiers over `--lint-base..HEAD`, `tests/` excluded, comments stripped |
| C-16 | major | apicheck went RED on symbols it could not resolve without torch | §7.1/§7.3/§8: import-first, else ast of the wheel SOURCE; `unresolvable-needs-torch` never RED; `api_unresolvable[]` |
| C-17 | major | the toolchain-status HALT fired on the owner's grill syncs | §2.0/§2.4/§10.5: exclude `docs/grills`; bundles outside the grill tree |
| C-18 | major | digest equality fragile; fingerprints could be empty | §5/§7.1: gate LAST on the committed tree, `apicheck-extended` separate, `digest_mismatch` with both ledgers, never-empty fingerprint; drive S2/S3 |
| C-19 | major | plan checks ran only in R0 | §2.1/§13: `checkPlan()` every stage, `repair-plan`, REPAIR MODE; drive S17/S17b/S17c |
| C-20 | major | `already-merged` bypassed every check | §4.5: evidence else `already-merged-unproven`; merged + red → revert-now; drive S14/N9 |
| C-21 | major | the persona pipeline was incomplete | §4.2 card 01 (generator), §3/§4.4 (FIXTURE COPY STEP), §7.1 (`--boundary-sha256`), §4.0 (owner sha field), the ownership rule; §14 |
| C-22 | major | checkpoint rows carried no reason or suggested next action | §2.2/§13 `checkpoint()`; drive S1/N6 |
| C-23 | minor | `RECEIPT_RE` dropped a central design phrase | §9 semantic rules: dropped; fragments logged only |
| C-24 | minor | integration order was raw id order | §4.3/§4.5: `(−rank, id)`; drive S1 |
| C-25 | minor | missing `diff_stats` failed open | §5 condition 10 fail-closed; §7.3; the verify schema requires it |
| C-26 | minor | the second author attempt was uninformed | §5: it carries the red verdict (digest_equal false + failures); drive N11 |
| C-27 | minor | reproductions could exit 0 and still confirm | §6.2/§9: non-zero-exit required, else ignored + logged; drive N10 |
| C-28 | minor | `--revert-proof` missed builder-added tests | §7.1/§4.4: `--tests` includes `tests/unit/*` |
| C-29 | minor | the red verifier's digest was only shape-checked | §5/§12 F-12: equality with the author's digest required; drive N11 |
| C-30 | minor | `git worktree add` refuses a checked-out branch for conflict worktrees | §4.4: `worktree add --detach` |
| C-31 | minor | P0 circularity (the setup agent told to create what it must assume) | §2.0 step 2: the venv is CREATED at P0; every prompt asserts existence, never creates |
| C-32 | minor | `SECRET_RE` matched the prompts' own dummy credentials | §10.6/§7.3: the `TESTTOKEN-` convention |
| C-33 | minor | the smoke run executed the full review loop | §2.0 step 8/§6.2: `smoke-skip-review` |
| C-34 | minor | CI/repo path ambiguities (`build_info.json`, evidence/catalog, workflow filenames) | §4.2: placeholder `build_info.json`, `evidence/catalog/README.md` in-repo, the four `.github/workflows` names in card 14's manifest |
| C-35 | minor | `EXPECTED.json` attributed to the wrong writer | §2.1/§8: `tools/expected.py` (card 14) defines the contract; CI writes the file |
| C-36 | minor | `core/engine.py` was delivered by no card | §4.2: in card 03a's manifest |
| C-37 | minor | receipt/label drift (timeout vs `timeout-or-dialog`, revert reasons, self-test exit) | §10.2/§13: `run()` maps receipts; typed revert reasons; the gate computes the self-test exit |
| C-38 | minor | a clean gate ran even when nothing had merged | §4.5/§6.1: skipped when nothing merged and the last clean gate passed at this head; drive S1 |

---

## Appendix C: Drive results v2

(v2.1: extended by scenarios S38-S41; Appendix D maps critic-v2's V-ids to what changed.)

**Method.** `drive.mjs` imports `makeScript` from the assembled §13 (`assembled.mjs`, rebuilt from the §9 schemas + the §13 text by `gen.sh`) and drives the WHOLE script from its stage entry to the checkpoint against a fake harness implementing exactly the workflow tool contract: `agent(prompt, {label, phase, schema, effort})`, `parallel` (barrier, throwing thunk → null), `pipeline` (no barrier, stage throw → null), `budget{total, spent, remaining}`, `log`, `phase`. Deterministic shas (`SHA(n)`/`HEX(n)`) make every digest comparison meaningful; the happy path (`happy()`) answers per role+mode with internally consistent digests (`st.seq`/`seqPeek` so a verifier can only reproduce the builder's digest by construction); each scenario overrides one behaviour. Assertions run against the calls (labels, prompts, launch order), the log lines and the checkpoint object — never against an agent's self-report.

**Provenance and result.** The critic's 21 scenarios are all carried (adapted to the v2 mechanisms, with the inversions the critic itself flagged flipped and marked below); 16 new scenarios/sub-variants (N1-N12 + S6b/S7b/S8b/S8c/S17b/S17c/N5b/N8b) aim at the blocking gaps. **41 scenarios, 107 assertions: 107 passed, 0 failed** (98/98 over the original 37 scenarios at v2; v2.1 adds S38-S41 with 9 assertions aimed at critic-v2's majors — Appendix D). Artifacts: `scratch/revise-v2/drive.mjs` + `drive-run.log`; re-run with `node drive.mjs`.

| Scenario | Drives | Asn | The load-bearing assertion |
|---|---|---|---|
| S1 | happy build, 12 cards, wave rule | 12 | wave 1 = [01] alone, wave 2 = [03a, 02] by rank desc; every merge gate carries `--journeys`; no extra review-pre clean gate |
| S2 | schema-valid-but-empty verifier | 3 | 2 builds, parked `no-progress` (never-empty fingerprint, C-18) |
| S3 | verifier pass, different digest | 3 | typed `digest-mismatch` with both ledgers to the fixer; two-strikes at 2 builds |
| S4 | hidden remote at merge | 4 | `HALT remote-added`; nothing after HALT except the synthesizer — which DID run (C-7) |
| S5 | overlapping write sets | 3 | overlapping cards never share a pipeline batch; all still merge |
| S6 / S6b | malformed clean gate; self-test contradicts exit 0 | 3 | no revert; `gate-unavailable`; no lenses on a never-clean tree (C-11/C-10) |
| S7 / S7b | null clean gate every wave, then resume | 6 | no revert, no lenses, stage stays build; resume re-runs a clean gate at head first (C-10), then satisfied |
| S8 / S8b | budget crosses RESERVE mid-wave; resume | 4 | starved cards `not_attempted` (retryable), stage repeats build, synthesizer ran; resume completes without `retry_parked` (C-8) |
| S8c | `agent()` throws budget ceiling | 4 | `HALT budget-exhausted`, synthesizer still ran, no retry fan-out (C-7/CG-20) |
| S9 | stale launch sha | 3 | throws `stale-launch-args`; no card agent launched |
| S10 | secret in builder `output_tail` | 3 | secret reaches no prompt/log/checkpoint; card parked `secret-shaped-output`; no fixer |
| S11 | veto judge null | 3 | stop `veto-unavailable`; not ready; retried once then parked |
| S12 | review finding → fix card | 4 | fixcards wrote `plan/fixes/<id>.json` BEFORE the author ran; the prompt carries the finding text AND the DoD command; `--card plan/fixes/…` (C-3) |
| S13 | root card parked (verify ×3) | 4 | `tree-incomplete`, zero lenses, dependents `not_attempted:dependency-blocked` (C-5) |
| S14 | bogus `already-merged` | 2 | unevidenced claim → `already-merged-unproven`; head unchanged; no revert (C-20) |
| S15 | stage with a failed canary | 3 | NO `promote-production`; stop `blocked-on-owner:staging-evidence`; stage stays stage (C-6/C-9) |
| S16 | seam card merges → journeys | 3 | journeys author launched; the journeys merge gate carries `--journeys`; the author is told the marker + `needs=` rule (C-4) |
| S17 / S17b / S17c | REFUTED citation + missing manifest cards; R1 refusal; repair relaunch | 5 | `repair-plan` (never approve-plan) + `plan_defects` carried; R1 refuses before any author/builder; REPAIR MODE relaunch approves (C-19/C-22) |
| N1 | journey skipped after its card merged | 2 | synthetic finding → refuter → fix card in `plan/fixes/` → built + merged (C-4 + C-3) |
| N2 | one malformed clean gate, healthy later | 2 | no revert; run still ends satisfied + ready (C-11) |
| N3 | clean gate red right after a journeys merge | 3 | exactly one revert, of the JOURNEYS merge, by its merge sha; a passing clean gate at head precedes any lens (C-12/C-10) |
| N4 | merged + gate red | 2 | checked revert of that merge sha; card `reverted`; dependents `dependency-blocked` (C-12) |
| N5 / N5b | resume with prior parked rows | 4 | `agent-null` park auto-retried + merged; `fix-exhausted` stays parked with reason; `retry_parked` re-drives it on demand (C-8/C-22) |
| N6 | verifier drops twice on card 01 | 2 | parked `agent-null:verifier` with `next: retry_parked`; `retry_parked_suggested` exactly [card 01] (C-22) |
| N7 | review loop to max-rounds | 2 | stop `max-rounds(3)`; status blocked; stage stays build (C-9) |
| N8 / N8b | promote with a confirmed critical finding; clean evidence | 2 | `rollback` emitted with the finding id; stage pinned at `promote` (C-6/C-9); clean evidence → satisfied + ready + no rollback |
| N9 | proven `already-merged` | 1 | evidence-checked claim counts as merged; run completes (C-20) |
| N10 | exit-0 reproduction; digest wording in notes | 2 | no fix card for a "holds" whose reproduction exits 0 (C-27); receipt-shaped notes NOT nulled (C-23) |
| N11 | confirm-RED digest differs once | 2 | author attempt 2 carries the verdict (`digest_equal: false`, failures); card then builds + merges (C-26/C-29) |
| N12 | fixture #1 not recorded | 2 | 04 `blocked_on_owner` with next; 05a `dependency-blocked`; independent 08a merged; `record-fixture-1` action; no lenses |
| S38 (v2.1 V-1) | verifier notes carry a REMAINING receipt phrase ("will report back when…") | 3 | the fragment is logged (`matched "will report back when"`), nothing is blocked receipt-shaped, the card merges — log-only, never null (C-23) |
| S39 (v2.1 V-2) | the stage=plan planner prompt | 2 | the prompt pins the exact path-scoped `pytest_collection_modifyitems` hook byte-for-byte, demands the `pytest.ini` marker registration and a BOTH-collections DoD line on card 01 |
| S40 (v2.1 V-3) | R1 throws `plan-needs-repair` on a REFUTED citation | 2 | refusal before any author/builder AND `next_args.stage === 'plan'` with `plan_defects` populated (was: `build` with an empty list) |
| S41 (v2.1 V-11) | journeys author SUCCESS over a red gate | 2 | the branch is refused (no merge/ff), the refusal is logged with the required-evidence note, the run still ends satisfied |

**Annotation taxonomy.** `[flipped: …]` = the critic's assertion encoded a v1 defect (an inverted expectation) and v2 asserts the intended behaviour. `[corrected, not a flip: …]` = my own draft's expectation was wrong and the assertion was rewritten to the correct invariant. `[corrected fixture, assertion unchanged]`, `[strengthened: …]`, `[not carried: …]` as below. Assertions are never edited to make a failing script pass; the three real failures were fixed in `script.js`.

| Assertion | Annotation |
|---|---|
| S1 "checkpoint status ready" | `[flipped: the critic marked its own "blocked" expectation as a mistake]` — with every card merged and the veto clean, `ready` is the correct state |
| S1 wave-2 order | `[corrected, not a flip: my first draft wrote the critic's id order; the rank order is platform-03a (deeper dependents) before platform-02]` |
| S1 rows carry reason + next | `[flipped: v1 rows had neither — C-22]` |
| S2 two-strikes at 2 builds | `[corrected, not a flip: v1 burned all 3 builds only because its fingerprint could be empty, disabling two-strikes; with the never-empty fingerprint the correct expectation is 2 builds + no-progress]` |
| S3 typed digest-mismatch + 2 builds | `[flipped: v1 passed failures: [] and burned 3 builds — C-18/C-26]` |
| S5 trailing refute batch | `[not carried: the critic's S5 asserted a trailing refute batch that only exists in the v1 loop shape; v2 runs refutes inside the review round, and the equivalent behaviour is asserted by S12/N1/N10]` |
| S7 lenses not spent; stage stays build | `[flipped: v1 spent 6 review agents on a never-clean tree — C-5/C-10/C-9]` |
| S8c the synthesizer still ran | `[flipped from FAIL: C-7]` |
| S12 fixcards before author; finding + DoD in the prompt | `[flipped: v1 named a card file nobody wrote — C-3]` |
| S13 tree-incomplete, no lenses | `[flipped from FAIL: C-5]` |
| S15 promote-production not emitted | `[flipped from FAIL: C-6]` |
| S16 merge gate `--journeys` | `[flipped from FAIL: C-4]` |
| S17 repair-plan + plan_defects; R1 refusal; REPAIR MODE | `[flipped from FAIL: C-19/C-22]` |
| N3 re-gate before lens | `[corrected, not a flip: the re-gate is wave 4's clean gate, which is why the literal review-pre label never appears — the invariant is a passing clean gate at head before the first lens (C-10)]` (the hook freezes `st.lastJourneyMerge` at the first journeys merge so the assertion tests the right sha) |
| N7 max-rounds | `[corrected fixture, assertion unchanged: the drive originally fed low-severity findings, which satisfied() correctly tolerates — critical/high are what keep it false]` |
| N8 stage pinned at promote | `[strengthened: C-9 pins the stage at promote, not merely not-done]` |

**The three real defects the drive caught in my own drafts** (fixed in `script.js`, never in the assertions): (1) the gate's protected-ownership rule and `validateCards` disagreed on who may write a protected path — resolved as one ownership rule (`MANIFEST_MIN[id] ∪ protected_touch`) in both (C-21); (2) the synthesizer was blocked by the budget guard after a HALT, violating C-7/F-45 — `budgetOk(label, exemptFromHalt)` now exempts it, because that reserve is what it is FOR; (3) a not-ready promote run advanced `next_args.stage` to `done`, violating C-9 — now `(ready ? 'done' : 'promote')`.

---

## Appendix D: v2.1 changes (the critic-v2 audit, applied in place)

Critic-v2 audited this document on 2026-09-19 (`design-v2-critique.md`): verdict `revise` — 0 blocking, 3 major, all 38 C-closures confirmed (4 with an attached V-gap), the artifacts byte-identical to the document, its own 28-scenario drive 50/51 with the single failure a real defect. The ids **V-1..V-11 below are critic-v2's gap ids, not §12.7's V-rows** (those map the v1 critic's gaps). One naming deviation, declared: the coordinator asked for an "Appendix C: v2.1 changes", but this document's Appendix C already holds the drive results, so the map is Appendix D.

| id | sev | What the audit found | What changed in v2.1 | Where |
|---|---|---|---|---|
| V-1 | **major** | §9, §12.2 AP-1 and §12.7 V-22 said receipt-shaped fragments are only logged, but `assertCommon` still NULLed returns matching the four remaining `RECEIPT_RE` alternatives (its drive M2 parked a card on "will report back when the run ends"; my drive N10 had tested only the removed alternative — vacuously green). | Decision (coordinator): **log-only, never null the card**. The null is gone; the matched fragment is still logged (`NOTE …: receipt-shaped fragment (matched "…") — logged only`). Drive S38 asserts a REMAINING phrase is logged and its card still merges. | §13 `assertCommon`; drive S38 |
| V-2 | **major** | The journeys marker was a name-only spec, and both naive implementations are dead ends: `pytestmark = pytest.mark.journey` in a conftest is inert (pytest reads `pytestmark` only from test modules → `--journeys` collects 0), and an unscoped `pytest_collection_modifyitems` marks every item in the session (→ `-m "not journey"` deselects the whole default suite). | Card 01's spec pins the conftest BYTE-FOR-BYTE to the critic's validated path-scoped hook (`it.path.is_relative_to(pathlib.Path(__file__).parent)`), demands `journey:` registered under `pytest.ini` `markers`, and adds a both-collections DoD line (gate `--journeys` over a one-file smoke journey AND the default suite, both green) so an inert or over-scoped marker fails card 01, never the first seam wave. The dry run now writes exactly the pinned bytes and its journeys checks stay green. The pin is SELF-CONTAINED — `import pytest` included, signature `(config, items)`: the audit's fix line omitted the import ("(or equivalent)"), and the v2.1 dry run proved the omission real — without it the gate's ruff step is `F821 Undefined name 'pytest'` RED and the hook NameErrors at collection (pytest 9.1.1) — so every suite-collecting gate went red until the pin was corrected; caught before rebuild, no card ever burned. Drive S39 asserts the planner prompt carries the pin. | §4.2 card 01, §4.8, §7.3, §13 `P.plan`; dry run; drive S39 |
| V-3 | **major** | An R1 `plan-needs-repair` told the owner to "relaunch stage=plan with args.plan_defects" while `next_args.stage` was `build` and `next_args.plan_defects` was `[]` — the machine-readable contract contradicted the stop message (the audit's own drive failure, M16b). | `nextStage` returns `'plan'` whenever `stop` starts with `FAILED:plan-needs-repair` (any stage), and `next_args.plan_defects` is populated whenever `planDefects.length > 0`, in every stage. Drive S40 asserts both. | §13 `checkpoint()`; drive S40 |
| V-4 | minor | The fixture delivery was misdescribed ("ships inside `gate.sh` itself"; "the gate writes the fixture itself"): the code reads the pair from the repo, only the temp worktree and the commit message are gate-created, and P0 works only because the bootstrap profile tolerates `fixture-not-yet-delivered`. | The five prose sites (§2.0 step 3, §7.3, §12.7 V-2, Appendix B C-2, A.3) rewritten: the pair is delivered by card 01 at `tests/fixtures/gate/`; the gate crafts the message and the worktree; P0's bootstrap run proves `broken_red` live and tolerates the missing fixture. No code change (the code was already right). | §2.0, §7.3, §12.7 V-2, App. B C-2, A.3 |
| V-5 | minor | The JS `PROTECTED` array and the §14 `tests/protected.txt` checklist diverged in both directions, so "checked identically in `validateCards` and in the gate" was false at the list level. | ONE list: the JS `PROTECTED` constant is the law and gains `tests/fixtures/persona_boundary.json` (ownership through card 13b's manifest; still sha-pinned at the boundary-fixture step); the §14 checklist now lists EXACTLY that array verbatim and states the plan verifier refuses a divergence; the author prompt's protected-path sentence now states the ownership rule instead of a 01-only ban. | §13 `PROTECTED` + `P.author`, §14 |
| V-6 | minor | `TIMEOUT` had no `tests` key, so `run('author','tests',…)` fell back to 30 min while §10.4/§11 say the author gets 25. | `TIMEOUT.tests = 1500000` added (25 min). | §13 `TIMEOUT` |
| V-7 | minor | §2.3 promised "a wave is admitted only if every chain in it can finish inside this invocation" over a 7-agent reservation, while a worst-case chain is ≈ 20 `agent()` calls. | The sentence now states the honest contract: admitted when 7 agents/chain remain; a mid-chain overrun degrades to typed, retryable starvation (C-8). `RESERVE_PER_CHAIN` stays 7 — raising it to the worst case would starve whole waves at cap 2 for a rare tail; the degradation is the designed answer. | §2.3 |
| V-8 | minor | `not_attempted:integration-dirty` matched `RETRYABLE_RE` (auto-retried on resume) while its `next` said "owner inspects". | The dirty case now carries `blocked:integration-dirty` — outside `RETRYABLE_RE`, agreeing with its `next`. | §13 wave loop |
| V-9 | minor | The budget-throw HALT still keys on the guessed regex `/budget\|ceiling\|spend/i` over the harness's throw text, and v2's UNVERIFIED list had dropped the item. | Re-added to the header UNVERIFIED list with the fallback note: if the real message differs the HALT never fires and the miss degrades to typed, retryable starvation, bounded by the per-call `budget.remaining()` guard. | header UNVERIFIED |
| V-10 | minor | Cost arithmetic was ~10-15 % optimistic: the design's own fix mix gives ≈ 6.65 agents/card, not 5.7. | §11 and the thesis re-derived WITH the mix stated: per card ≈ 6.65 (5 + 0.4×2 + 0.15×4 + 0.1×2 + 0.05×1), R1 ≈ 296 (280-315), total ≈ 335-350; wave ≈ 95-100 min; cap 2 ≈ 28-29 h in 5-7 invocations; cap 14 ≈ 20-22 h. §15 Q1 updated to match. | thesis, §11, §15 Q1 |
| V-11 | minor | The journeys author's gate result was never JS-verified — acceptance was `status==='SUCCESS' && isSha(tests_head)`, so a SUCCESS over a red `journeys-only-tests` step was caught only at the merge gate. | Acceptance now requires `gate_exit_code === 0` and a 64-hex `gate_digest`; the `TESTS` schema gains a required `gate_exit_code`; the journeys prompt demands both; a red journeys-only run is refused before any merge. Drive S41 asserts the refusal and that the run still completes. | §13 journeys branch + `P.journeys`, §9 TESTS; drive S41 |

**Tally note.** The critique's §0 header says "3 major, 9 minor"; its gaps table lists 8 minors (V-4..V-11). All 11 ids are addressed above — 11 fixed, 0 declined. Three of them (V-4, V-9, and V-7's sentence) are prose-side fixes because the audited code was already right; that is the fix the audit asked for.

**After the patch:** the drive is 41 scenarios / 107 assertions (from 37/98), all passing; the 22-check control-path dry run stays green with its journeys conftest now byte-identical to the pinned §4.8 text; the schema walk, `node --check` (both assembly forms) and `bash -n` re-run green; `gate.sh` is unchanged by v2.1.

---

*End of design v2.1. Every section required by the brief is present in the brief's order; all 136 coverage rows are kept and §12.7 adds the v2 mechanism rows; every judge item is mapped in Appendix A (with the v2 audit in A.0); every v1 critic gap C-1..C-38 is resolved with 0 declines and mapped in Appendix B; critic-v2's V-gaps are mapped in Appendix D; the gate, the schemas and the script are the exact texts that passed `bash -n` (+ 13 heredocs and 3 one-liners compiled), the schema walk (34 object nodes, 7 roots), `node --check` (both assembly forms), the 22/22 control-path dry run and the 107-assertion fake-harness drive (41 scenarios).*
