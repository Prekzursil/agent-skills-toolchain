# Extensive Grill — decision queue: deep-research / e2e-testing / workflow-authoring / ultracode

**Modes:** expansion + red-team (scoping a next tranche on four named surfaces).
**Method:** grill-me-extensive (scout -> diverge -> structure -> foundation-first -> one-at-a-time -> capture -> converge).
**Status:** OPEN — questions unanswered. This doc is the decision queue and audit trail; answers land in
"Resolved Decisions" at the bottom as the walk proceeds. A grill is not a build.

---

## 1. Scout ground truth (verified 2026-08-20, this checkout)

1. The four surfaces map to open register items in `command-center/sources/REGISTER.md`
   (59 OUTSTANDING as of 2026-08-11):
   - `/deep-research` -> R-A13 (Mission 4, "configurable production workflow", IN-FLIGHT).
   - `/workflow-authoring` -> R-A07 (workflow foundry, OPEN XL) + R-A08 (>=96 executable
     blueprints, >=40 flagship with e2e tests, OPEN XL).
   - `/e2e-testing` -> the "with e2e tests" clause of R-A08 + R-A11 (conformance suite, OPEN XL).
   - ultracode (= a Claude Code Workflow fan-out run) -> R-M06 (program parked 2026-07-27 after
     7 adversarial-gate blocking verdicts; 6 still live, incl. `lane3-ultracode`).
2. `workflows/` on main holds exactly one executable Workflow (`rtv-pdr.js`). The blueprint corpus
   (~97-115 WfDSL JSON docs under `platform/workflows/`) is definitions only; status files say
   "no runner exists yet".
3. `research_harness` (deep-research substrate) is a tested pure-logic library exposing ONE
   config knob (`top_n` in `harness.py:42-48`); the spec (`:11248-11278`, paraphrased in
   `command-center/CLOSE-PROPOSALS-A2.md:25`) demands ~23 config dimensions. Modules
   `academic.py`/`claims.py`/`calibration.py` exist and are tested but are not exported.
4. `.agents/skills/e2e-testing/` is a single vendored ECC Playwright prose SKILL.md — generic
   web-app content, unadapted to this harness; no scripts, no tests.
5. Foundry: `platform/lib/foundry/` ships scout/forge CLIs (147 tests; fuse gate 52 CERTIFIED /
   224 REJECTED) but the 9-verb pipeline is incomplete (discover~0, translate/distill/generate~1,
   publish~3). The `.agents/skills/workflow-foundry/` NAME is taken by a 22 KB fan-out operating
   contract, not the forge — a standing grade-from-code trap.
6. Spec artifacts `08-WORKFLOW-CANDIDATE-REGISTRY.json`, `09-WORKFLOW-BLUEPRINT-LIBRARY.json`,
   `10-WORKFLOW-FORGE-SPEC.md` and the `gate-findings/` bodies live only on host trees
   (`~/.claude/...`), NOT in this repo (dual-tree blindness, R-A26).
7. Owner decisions are recorded canonically: `WORK-UNIT-CATALOG.json.owner_questions[]`
   (OPEN|ANSWERED + provenance) rendered to `OWNER-DECISIONS.md`; closures via
   `CLOSE-VERIFY.json` (close-verify/v2). The consistency contract: nothing dropped without a
   recorded owner decision.
8. Live blockers: OQ-5 (SPEC-38 vs 1.9R adjudication fork, R-A05) is OPEN and register section 5
   forbids starting A07/A08/A09 before the scope ruling; D-03 keeps the 108 blueprints as a
   design queue until an explicit apply-mode switch; R-M18 (receipt `unit_id` matches 0/103
   register rows) blocks any monitor-lane receipt.

## 2. Cross-lens convergence (4 independent scouts)

- **C1 (4/4 lenses): the missing layer is a RUNNER.** Deep-research has a library but no
  executable workflow; blueprints have definitions but no runner; e2e has definition-level
  conformance but nothing executes a Workflow with runtime assertions; foundry has CLIs but no
  end-to-end pipeline. One execution/verification spine would advance all four register items.
- **C2 (3/4): "what counts as done" is undefined and owner-only.** R-A08 "executable" (DSL doc vs
  `.js` runtime?), R-A11/e2e "e2e" (definition conformance vs runtime run?), R-A13
  "configurable" (schema+knobs vs contradiction/quota gates passing?).
- **C3 (3/4): small tractable slices exist on every surface** (S/M efforts) as alternatives to
  the XL items as written.
- **C4 (2/4): vendor the host-only specs into the repo** to end dual-tree blindness (S effort,
  prerequisite for grading any of this from code).
- **C5 (2/4): building now without the authority packet re-enacts the recorded ~50x de-scope**
  (R-A04); every build slice must land with a register receipt.

## 3. Direction catalog (from the diverge wave; dedup'd)

### deep-research (R-A13)
| id | direction | effort |
|---|---|---|
| DR-1 | `workflows/deep-research.js` Claude Code shell (clarify -> preflight -> fan-out -> synthesize; args for topic/top_n) | M |
| DR-2 | `ResearchConfig` + JSON schema for a subset of the ~23 spec knobs, threaded into `plan_research` | L |
| DR-3 | Contradiction + favourable/unfavourable quota gate in grading/report (spec `:11260-11278`, TST-0319) | M |
| DR-4 | Adopt/fuse the WfDSL `bp-res-01..06` cascade as the Mission-4 product; skill harness as library | M-L |
| DR-5 | Export + wire the orphan `academic`/`claims`/`calibration` modules into plan->grade->render | S-M |
| DR-6 | Live MCP adapter implementing `fetch_with_cache` end-to-end (injectable probe/fetch) | L |

### workflow-authoring / foundry / ultracode (R-A07, R-A08, R-M06)
| id | direction | effort |
|---|---|---|
| WF-1 | Promote 1-3 flagship DSL blueprints to `.js` under `workflows/` + lint/e2e (rtv-pdr as pattern) | M |
| WF-2 | Ship the thin missing foundry verbs: discover + translate | M |
| WF-3 | Vendor 08/09/10 spec artifacts into `command-center/` (ends R-A26 dual-tree blindness) | S |
| WF-4 | Wire WfmonSource into the unified cockpit (fixes R-M05 count skew; first live R-M06 gate) | S |
| WF-5 | Rename/dual-track the `workflow-foundry` skill vs `platform/lib/foundry` (kill the name trap) | S |
| WF-6 | Full 9-verb foundry + >=40 executable e2e flagships as written | XL |

### e2e / verification (R-A08 e2e clause, R-A11)
| id | direction | effort |
|---|---|---|
| EE-1 | Blueprint definition gate in CI: wire wfdsl catalog/schema tests into `quality.yml` as the floor | S |
| EE-2 | Skill smoke matrix: parametrize `test-live-skill-helpers.py` over every skill with `scripts/` | S-M |
| EE-3 | MCP server contract matrix: spawn stdio MCP -> list_tools -> known-positive call, both-states | M |
| EE-4 | Fixture-backed agent-run replay (hermetic transcript replay + completion predicates, no live LLM) | L |
| EE-5 | Workflow-DSL conformance RUNNER over a flagship subset (closes R-A08/R-A11 as written) | XL |
| EE-6 | Retire/relabel the vendored `e2e-testing` skill; author a harness-native `workflow-e2e` skill | S |

### authority / sequencing (red-team lane)
| id | direction | effort |
|---|---|---|
| SQ-1 | Answer-or-supersede OQ-5 (SPEC-38 vs 1.9R); relabel the R-A04 misnamed "Prompt Two" artifacts | S (owner) |
| SQ-2 | Fix R-M18 receipt `unit_id` schema so lanes can emit valid receipts | S |
| SQ-3 | OQ-6 / R-B08 security quarantine (owner-only rotation) before anything else ships | S (owner) |
| SQ-4 | Register receipt discipline: every slice above lands with a register disposition | process |

## 4. Decision queue (foundation-first; one per turn; each with recommendation)

### Foundation
- **G-1. What is this tranche FOR?** (a) pragmatic thin-slice build on the four surfaces;
  (b) formal Program-A resumption (authority packet first, then Phase 0); (c) BOTH — a minimal
  authority mini-packet (SQ-1..3 answers) gating a thin-slice build wave.
  **Recommend (c)** — building without the packet re-enacts the recorded de-scope failure (C5);
  a pure authority pass ships no software. Trade-off: (c) needs 2-3 owner answers before code.
- **G-2. What counts as "executable" and "e2e" for R-A08/R-A11?** (a) WfDSL definition +
  conformance = done; (b) Claude `.js` runtime under `workflows/` + a runtime-asserted run = done;
  (c) two-tier: definition-conformance floor now (EE-1), runtime bar for "flagship" only.
  **Recommend (c)** — matches C2 and keeps the XL runner honest without blocking the floor.
  Trade-off: two definitions of done need clean labeling in the register.

### Scope-inclusion
- **G-3.** deep-research product surface: `.js` workflow (DR-1), WfDSL cascade (DR-4), or both
  with one SSOT? **Recommend DR-1 first** (invokable value now; rtv-pdr pattern exists),
  DR-4 deferred until the runner question (G-2) settles.
- **G-4.** Include DR-5 (wire orphan modules)? **Recommend YES** — cheapest real product step;
  dead-but-tested code is pure downside.
- **G-5.** Include DR-3 (contradiction/quota gate)? **Recommend YES after DR-5** — it is the
  spec's most distinctive demand and the acceptance-bar candidate for R-A13.
- **G-6.** e2e skill hygiene (EE-6): retire, relabel, or leave the vendored Playwright skill?
  **Recommend relabel + author `workflow-e2e`** — keep Playwright prose for actual web UIs
  (mcp-manager, taskwatch), stop it masquerading as the harness answer.
- **G-7.** Which e2e floor ships first: EE-1 (CI definition gate), EE-2 (skill smoke matrix),
  EE-3 (MCP contract matrix)? **Recommend EE-1 then EE-2** — S efforts, both-states-friendly,
  and EE-1 is a hard prerequisite for grading blueprint work.
- **G-8.** Does the 6-gate CI charter GROW (EE-1/EE-3 as gate 7+) or stay closed with opt-in
  extras like TG-2? **Recommend opt-in first, promote after 2 weeks green** — charter is
  deliberately closed; silent-pass risk is the thing this repo red-teams hardest.
- **G-9.** Blueprint promotion (WF-1): how many flagships and which? **Recommend 2** —
  one research-family (pairs with DR-1) + one council/gate-family; enough to prove the pattern,
  small enough to gate properly.
- **G-10.** Foundry: thin verbs now (WF-2) or defer all foundry until OQ-5? **Recommend defer
  WF-2**; do WF-3 (vendor specs, S) and WF-5 (name-trap fix, S) immediately — they are
  bookkeeping, not scope-ruled build.
- **G-11.** Monitor lane: include WF-4 (wfmon cockpit wiring) in this tranche? **Recommend YES**
  — S effort, it is the named first step on R-M06's live gates, and ultracode observability
  multiplies every other fan-out.

### Sequencing / process
- **G-12.** Order of the build wave once gated? **Recommend:** SQ-2 -> WF-3/WF-5/EE-6 (bookkeeping)
  -> EE-1/EE-2 (floor) -> DR-5 -> DR-1 -> WF-1 -> WF-4 -> DR-3 -> (defer DR-2/DR-6/EE-4/EE-5/WF-2/WF-6).
- **G-13.** Where do these answers get recorded? (a) this doc only; (b) also as
  `owner_questions[]` entries in `WORK-UNIT-CATALOG.json` per the canonical shape.
  **Recommend (b)** — the consistency contract demands it; this doc alone is not the register.
- **G-14.** Execution vehicle for the build wave: ad-hoc PRs, or a governed ultracode run using
  `workflow-authoring/templates/governed-run-orchestrator.md` with DOD rows per slice?
  **Recommend governed run** — it dogfoods the very surface being built; trade-off: setup cost.
- **G-15.** Effort ceiling for this tranche: S/M only, or admit the L items (DR-2, EE-4)?
  **Recommend S/M + at most one L** (DR-2 as the single L, since R-A13 is the only IN-FLIGHT item).
- **G-16.** OQ-6 security quarantine (SQ-3): precondition for the whole tranche or parallel
  track? **Recommend precondition** — it is owner-cheap and the register names it first.

## 5. Resolved Decisions

*(filled during the one-at-a-time walk; empty = still open)*

| id | decision | answered on | provenance |
|---|---|---|---|
| — | — | — | — |
