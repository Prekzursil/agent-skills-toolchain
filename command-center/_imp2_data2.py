# -*- coding: utf-8 -*-
"""IMP-2 slice, data part 2: units IMP-0195..IMP-0229.

E (14) IMP-0195..0208  static validation, simulation, benchmarking, certification lifecycle
F ( 7) IMP-0209..0215  workflow-scout / workflow-forge / recommendation
G (14) IMP-0216..0229  the execution engine (extends agentrail; no rival runtime)
"""

AGENTSPEC = "tools/agentspec/agentspec"
RAIL = "tools/agentrail/agentrail"
FOUNDRY = "tools/foundry"

UNITS_2 = [
    # ---------------------------------------------------------------- GROUP E (14)
    dict(
        t="Implement static validation: reachability, orphan nodes, unreachable barriers",
        q="Target: a static pass over a validated Workflow that reports unreachable nodes, orphan barriers (awaiting "
        "something no path produces) and units no node ever schedules. Acceptance: a workflow whose barrier awaits "
        "a unit outside every path is REJECTED before dispatch - today validate.py catches barrier-awaits-unknown "
        "but not barrier-awaits-unreachable, which is a different defect.",
        i=[
            f"{AGENTSPEC}/validate.py (barrier-awaits-unknown)",
            "IMP-0129..IMP-0132 node types",
        ],
        d=["IMP-0129", "IMP-0130", "IMP-0132"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) an unreachable-barrier fixture is rejected while the reachable twin passes; (2) the "
        "reachability set is computed by graph traversal and cross-checked against an independent topological "
        "sort (two derivations of the same set).",
        ts=[
            "unreachable barrier rejected; reachable twin accepted (both-states)",
            "traversal-derived and topological-sort-derived reachable sets are equal",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement deadlock and livelock analysis over Loop and Barrier combinations",
        q="Question: can this workflow reach a state where no node can progress, or loop without information gain? "
        "Target: a static analysis that answers it for the Loop x Barrier x Subworkflow combinations. Acceptance: "
        "a mutual-wait fixture is detected statically, and 'one hung unit blocks a large batch' (11318) is "
        "unrepresentable when per-unit pipelines are declared.",
        i=["_USER-PROMPTS.md:11318", "IMP-0130 output", "IMP-0195 output"],
        d=["IMP-0195"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) mutual-wait fixture detected; (2) a deliberately safe fixture is NOT flagged (false-"
        "positive control), with the flagged/unflagged counts reported as numbers.",
        ts=[
            "mutual-wait deadlock detected; safe fixture not flagged (both-states)",
            "a bounded livelock (loop with no state change) is detected as a distinct verdict from deadlock",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Build the paired A/B benchmark runner with matched cases and paired statistics",
        q="Target: run two workflows over the SAME case set with paired analysis (per-case delta, not group means). "
        "Acceptance: the runner reports effect size and the number of cases, and REFUSES to emit a verdict below a "
        "declared minimum case count instead of reporting a percentage over three cases.",
        i=[f"{AGENTSPEC}/evals/registry.py", "IMP-0198 output"],
        d=["IMP-0198"],
        role="benchmark-engineer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) paired deltas computed per case and archived; (2) an under-powered run returns "
        "INSUFFICIENT-EVIDENCE rather than a verdict (both-states with a powered run).",
        ts=[
            "under-powered run returns INSUFFICIENT-EVIDENCE, never a verdict",
            "identical workflows compared to themselves produce a zero effect (sanity/control run)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Construct the matched benchmark case corpus with difficulty stratification",
        q="Target: build the case corpus workflows are benchmarked on - stratified by difficulty, with a held-out "
        "slice never shown during workflow development. Acceptance: the held-out slice is enforced mechanically "
        "(a hash-partition, not a convention) so a workflow cannot be tuned on it.",
        i=[
            f"{AGENTSPEC}/evals/rows.py",
            "_USER-PROMPTS.md:10741 (matched benchmark cases)",
        ],
        d=["B08"],
        role="benchmark-engineer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) partition membership is a pure function of the case hash (recomputed independently); "
        "(2) a development run that touches a held-out case is detected by an access log assertion.",
        ts=[
            "held-out partition is hash-determined and reproducible",
            "touching a held-out case during development is detected (detector fires)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Build the hermetic workflow simulator on the fake rail",
        q="Target: execute any workflow against agentspec.evals.fake_rail so structure, gates and stopping rules can "
        "be exercised with zero live calls and zero cost. Acceptance: a simulated run makes zero network calls and "
        "zero real spawns, and the simulator refuses to run a workflow that requires a capability the fake rail "
        "cannot honestly emulate - a silently faked capability is worse than a refusal.",
        i=[f"{AGENTSPEC}/evals/fake_rail.py", f"{AGENTSPEC}/evals/pytest_live.py"],
        d=["IMP-0195"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) zero egress and zero real spawns measured by instrumented ports; (2) an unemulatable "
        "capability produces an explicit refusal naming the capability.",
        ts=[
            "zero egress / zero real spawn during simulation (measured, not asserted)",
            "unemulatable capability refused by name (both-states with an emulatable twin)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Build the tournament bracket runner for N competing workflows",
        q="Target: run a round-robin or bracket tournament over N candidate workflows on the matched corpus, "
        "preserving every pairwise result. Acceptance: the ranking is computed from pairwise results with ties "
        "reported as ties - a forced total order over statistically indistinguishable candidates is a fabricated "
        "verdict.",
        i=["IMP-0197 output", "IMP-0198 output"],
        d=["IMP-0197"],
        role="benchmark-engineer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) pairwise matrix archived in full; (2) an injected exact-tie pair is reported as a tie, "
        "not ordered.",
        ts=[
            "injected tie is reported as a tie (both-states with a clear winner)",
            "ranking is reconstructible from the archived pairwise matrix alone",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim"],
        oa=False,
    ),
    dict(
        t="Capture a per-workflow regression baseline that later runs are compared against",
        q="Target: freeze each certified workflow's benchmark result as a named baseline with its corpus version and "
        "spec_version. Acceptance: comparing against a baseline captured under a DIFFERENT corpus version is "
        "refused - comparing across corpora is the quiet way a regression gate stops measuring anything.",
        i=["IMP-0197", "IMP-0198 outputs", "command-center/TEST-REGISTRY.json"],
        d=["IMP-0197", "IMP-0198"],
        role="benchmark-engineer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a cross-corpus comparison is refused with a named reason; (2) a same-corpus comparison "
        "produces a delta computed from stored per-case rows, not from a stored summary.",
        ts=[
            "cross-corpus comparison refused (both-states: same-corpus permitted)",
            "delta recomputed from per-case rows, proving the summary is not the only artifact",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Wire the independent-confirmation hook into the certification path",
        q="Target: before certification, a fresh reviewer that did NOT author the workflow reproduces the benchmark "
        "claim from raw sources. Acceptance: the confirmation record must cite the raw artifacts it read; a "
        "confirmation that only cites the author's summary is rejected by the gate - a digest is a claim, not a "
        "receipt (10646).",
        i=[
            "_USER-PROMPTS.md:11028-11041 (independent confirmation)",
            "_USER-PROMPTS.md:10646",
        ],
        d=["IMP-0197"],
        role="integrator",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a summary-only confirmation is rejected; (2) an artifact-citing confirmation passes and "
        "its cited paths are proven to exist by Test-Path before the digest is read.",
        ts=[
            "summary-only confirmation rejected (both-states)",
            "every cited artifact path is existence-checked before the digest is accepted",
        ],
        rev="cross-vendor reviewer (Codex) - independence is the point of the unit",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Define the certification record and its admission criteria",
        q="Target: a typed certification record (workflow id, version, corpus version, evidence, confirmer, tier, "
        "expiry). Acceptance: certification EXPIRES - a certificate older than its corpus or spec_version is "
        "reported as STALE rather than valid, because a stored green decays.",
        i=[
            "IMP-0201",
            "IMP-0202 outputs",
            "_USER-PROMPTS.md:10741 (certify only workflows that outperform)",
        ],
        d=["IMP-0201", "IMP-0202"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a certificate whose corpus version is superseded reports STALE (injected clock, "
        "deterministic); (2) a current certificate reports VALID.",
        ts=[
            "stale certificate detected; current certificate valid (both-states)",
            "certificate schema rejects a record with no evidence anchor",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement deprecation and supersession records for retired workflows",
        q="Target: retire a workflow by SUPERSESSION (naming the replacement and the migration) or DEPRECATION "
        "(naming the reason and the removal date), never by deletion. Acceptance: a retired workflow remains "
        "resolvable and its consumers get a typed warning with the successor id - silent removal breaks the "
        "'rollback removes existing commands or user data' failure class (11347).",
        i=["_USER-PROMPTS.md:11347", "IMP-0203 output"],
        d=["IMP-0203"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a retired id still resolves and returns the successor; (2) a consumer pinned to the "
        "retired id still executes (no hard break) while emitting the warning.",
        ts=[
            "retired id resolves to successor; pinned consumer still runs (both-states)",
            "deletion attempt on a referenced workflow is refused",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["dependency-blocked", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement rollback of a fusion to its source components",
        q="Target: given a fused workflow in service, roll back to the source components it was built from, "
        "preserving in-flight state where possible. Acceptance: rollback is REHEARSED in a test, not merely "
        "documented, and the post-rollback capability vector equals the union of the sources'.",
        i=["IMP-0179 lineage", "IMP-0180 decomposition", "_USER-PROMPTS.md:10742"],
        d=["IMP-0179", "IMP-0180"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) rehearsed rollback restores the source components (fingerprint equality); (2) "
        "post-rollback capability vector equals the sources' union (computed).",
        ts=[
            "rehearsed rollback restores sources by fingerprint",
            "no capability is lost across the rollback (computed set equality)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement the benchmark-gaming and overfit detector",
        q="Question: did this workflow win because it is better, or because it was tuned to the visible cases? "
        "Target: compare visible-slice and held-out-slice performance and flag a gap beyond a declared threshold. "
        "Acceptance: an intentionally overfit workflow is flagged - 'benchmark gaming' is a named refuter lane "
        "(11059) and must have a mechanical detector, not only a reviewer.",
        i=["IMP-0198 held-out partition", "_USER-PROMPTS.md:11059"],
        d=["IMP-0198", "IMP-0197"],
        role="test-author",
        tools="CODE",
        sub="cloud-batch",
        to=3600,
        ev="Two signals: (1) a deliberately overfit workflow is flagged; (2) an honest workflow is not (false-positive "
        "control), with both gaps reported as numbers.",
        ts=[
            "overfit workflow flagged; honest workflow not flagged (both-states)",
            "the threshold is declared and versioned, not tuned per run",
        ],
        rev="cross-vendor reviewer (Codex) - the detector must not share the builder blind spot",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement workflow packs, presets and semantic versioning",
        q="Target: group workflows into installable packs with editable presets and semver. Acceptance: a preset "
        "cannot silently widen a workflow's tool permissions or source policy - a preset that requests more "
        "privilege than the workflow declares is rejected at load.",
        i=["IMP-0133 params", "IMP-0136 tool permissions"],
        d=["IMP-0133", "IMP-0136"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a privilege-widening preset is rejected; (2) a narrowing preset is accepted and the "
        "effective permission set is the intersection (computed).",
        ts=[
            "privilege-widening preset rejected; narrowing preset accepted (both-states)",
            "effective permissions are the computed intersection, asserted directly",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Emit the marketplace publication payload for a certified workflow",
        q="Target: turn a certified workflow into a publishable package payload (identity, version, permissions, "
        "provenance, SBOM entry, licence, benchmark evidence, lineage) for the Phase-6 registry. Acceptance: the "
        "payload NEVER includes .git, caches, transcripts or credentials (10842), proven by an inventory diff of "
        "the packed bytes, and publication itself remains owner-gated.",
        i=[
            "_USER-PROMPTS.md:10842",
            "B07 phase-6 registry contract",
            "IMP-0203 certification",
        ],
        d=["IMP-0203", "B07"],
        role="integrator",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) packed-byte inventory contains zero excluded paths (computed set intersection == empty); "
        "(2) a credential-shaped scan of the packed bytes returns zero hits.",
        ts=[
            "packed inventory excludes .git/caches/transcripts (computed)",
            "planted junk file must be caught by the inventory gate (detector fires)",
        ],
        rev="cross-vendor reviewer (Codex) plus owner gate before any publish",
        retry="two-strikes",
        fc=["owner-blocked", "overclaim"],
        oa=True,
    ),
    # ---------------------------------------------------------------- GROUP F (7)
    dict(
        t="Ship workflow-scout as an executable meta-workflow",
        q="Target: given a goal and constraints, scout searches local, marketplace, repo, docs and paper sources, "
        "verifies provenance and licence, and returns ranked existing candidates with an adopt/adapt verdict. "
        "Acceptance: scout is itself a typed Workflow executed by the same runtime (dogfooding), not a script - if "
        "it cannot be expressed in the spec, the spec is the thing that is wrong.",
        i=[
            "_USER-PROMPTS.md:10913 (ship workflow-scout and workflow-forge)",
            "IMP-0150..IMP-0153 adapters",
        ],
        d=["IMP-0150", "IMP-0151", "IMP-0152", "IMP-0153", "IMP-0156"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=5400,
        ev="Two signals: (1) scout runs through the standard runtime and its receipt passes the shared oracle; "
        "(2) on a goal with a known incumbent workflow, scout returns that incumbent (planted-known-answer control).",
        ts=[
            "planted known incumbent is found by scout (detector control)",
            "scout executes as a typed Workflow through the shared runtime, not as a bespoke script",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "rate-limited"],
        oa=False,
    ),
    dict(
        t="Implement the scout prior-art stage with mandatory licence verification",
        q="Target: a scout stage that searches prior art and refuses to recommend anything whose licence is UNKNOWN "
        "or incompatible with the target use. Acceptance: a permissively-described but unlicensed candidate is "
        "downgraded to CLEAN-ROOM-REIMPLEMENT rather than ADOPT.",
        i=[
            "IMP-0156",
            "IMP-0157 outputs",
            "_USER-PROMPTS.md:10723 (disposition vocabulary)",
        ],
        d=["IMP-0156", "IMP-0157", "IMP-0209"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) unlicensed candidate is dispositioned CLEAN-ROOM-REIMPLEMENT; (2) an MIT candidate is "
        "dispositioned ADOPT-AS-IS - two different inputs, two different verdicts, both asserted.",
        ts=[
            "unlicensed candidate never returns ADOPT (both-states with a licensed twin)",
            "disposition values are drawn from the spec's closed 15-value vocabulary",
        ],
        rev="cross-vendor reviewer (Codex) - legal surface",
        retry="two-strikes",
        fc=["owner-blocked", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the anti-rebuild guard: never build what already exists and is better",
        q="Question: does an existing workflow already cover this goal at or above the quality bar? Target: a guard "
        "the generator MUST consult, returning BUILD only when coverage is genuinely absent or measurably inferior. "
        "Acceptance: the guard fires on a planted incumbent, and its verdict cites the incumbent's benchmark "
        "evidence - 'discovery ignores an existing superior workflow and rebuilds it' (11331) is the exact failure "
        "this unit exists to make impossible.",
        i=[
            "_USER-PROMPTS.md:11331",
            "IMP-0177 capability vectors",
            "IMP-0201 baselines",
        ],
        d=["IMP-0209", "IMP-0177"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) planted incumbent blocks BUILD; (2) a genuinely uncovered goal returns BUILD, so the "
        "guard is not simply always-blocking (both-states).",
        ts=[
            "planted incumbent blocks BUILD; uncovered goal permits BUILD",
            "the BUILD verdict cites either absent coverage or an inferior baseline, asserted structurally",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Ship workflow-forge as an executable meta-workflow",
        q="Target: forge takes a goal plus scout output and produces an executable workflow by adopting, adapting, "
        "merging, composing or building - returning the workflow AND an evidence-backed design rationale. "
        "Acceptance: the forged artifact passes schema validation, static validation and simulation before it is "
        "returned; a forged workflow that only 'looks right' must never reach the caller.",
        i=["IMP-0209 scout", "IMP-0182..IMP-0192 fusion", "IMP-0199 simulator"],
        d=["IMP-0209", "IMP-0182", "IMP-0199"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=5400,
        ev="Two signals: (1) every forged artifact carries a passing simulation receipt; (2) a deliberately broken "
        "forge input yields a typed failure, not a plausible-looking workflow.",
        ts=[
            "forged workflow passes schema + static + simulation before return",
            "broken input yields a typed failure (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the find-vs-repair-vs-merge-vs-build recommender with an explicit cost model",
        q="Question: for this goal, is it cheaper and safer to adopt, repair, merge, compose or build? Target: a "
        "recommender that scores each path on expected cost, licence risk, capability fit and maintenance burden, "
        "and shows its arithmetic. Acceptance: the recommendation changes when an input changes - a recommender "
        "that returns BUILD for every input is a constant function wearing a model's clothes, and the test suite "
        "must prove it is not.",
        i=[
            "IMP-0209",
            "IMP-0211 outputs",
            "_USER-PROMPTS.md:11168 (recommendation logic)",
        ],
        d=["IMP-0209", "IMP-0211"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a sensitivity table shows at least three distinct recommendations across the input grid; "
        "(2) the scoring arithmetic is reproducible from the recorded inputs alone.",
        ts=[
            "input grid yields >=3 distinct recommendations (constant-function control)",
            "score recomputed independently from the recorded inputs matches the stored score",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement the forge design-rationale emitter with inline evidence anchors",
        q="Target: every forged workflow ships a rationale that anchors each design decision to a file:line, a "
        "benchmark run id or an explicit 'inferred from X'. Acceptance: a rationale containing an unanchored "
        "load-bearing claim is REJECTED by a lint - and the lint must fire on a planted unanchored claim, or it is "
        "measuring nothing.",
        i=["IMP-0212 forge", "rules/common/fan-out-contract.md (A3)"],
        d=["IMP-0212"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) planted unanchored claim is rejected; (2) a fully anchored rationale passes, so the lint "
        "is not simply always-failing.",
        ts=[
            "planted unanchored claim rejected; anchored rationale passes (both-states)",
            "anchor resolution is checked (the cited file:line must exist), not just pattern-matched",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Make scout and forge resumable with partial-result preservation",
        q="Target: a scout or forge run that is interrupted preserves everything it had proven and resumes from "
        "there. Acceptance: killing forge mid-run leaves a truthful partial artifact on disk (every unproven claim "
        "marked UNKNOWN - not yet measured), because a unit that holds results in memory for 70 minutes and then "
        "freezes is a measured total loss on this estate.",
        i=["rules/common/fan-out-contract.md (C1)", "IMP-0145 resume state"],
        d=["IMP-0145", "IMP-0212"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a kill at 30% leaves a parseable artifact whose unproven sections are marked UNKNOWN; "
        "(2) the resumed run does not re-do proven work (dispatch count strictly lower).",
        ts=[
            "kill-at-30% leaves a truthful partial artifact (schema-valid, UNKNOWNs explicit)",
            "resume does not repeat proven work (counted from the ledger)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["uncontrolled-silence", "green-not-live"],
        oa=False,
    ),
    # ---------------------------------------------------------------- GROUP G (14)
    dict(
        t="Implement the Loop node executor with per-iteration convergence evaluation",
        q="Target: execute a Loop, evaluating the convergence predicate against real state each iteration and "
        "stopping at the bound. Acceptance: the iteration record shows the predicate INPUTS per iteration, so a "
        "loop that 'converged' can be audited - a convergence claim with no per-iteration state is unfalsifiable.",
        i=["IMP-0130 Loop type", f"{RAIL}/runner.py"],
        d=["IMP-0130"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) per-iteration predicate inputs are recorded and re-evaluable offline to the same verdict; "
        "(2) the bound is enforced under a never-converging predicate.",
        ts=[
            "never-converging predicate stops at the bound (both-states with a converging twin)",
            "offline re-evaluation of recorded inputs reproduces every iteration verdict",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["uncontrolled-silence", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement the Subworkflow executor with id namespacing and budget roll-up",
        q="Target: execute an embedded workflow with namespaced ids, an isolated artifact space and a budget that "
        "rolls up to the parent. Acceptance: two sibling subworkflows that use the SAME internal unit id do not "
        "collide, proven by running exactly that fixture.",
        i=["IMP-0129 Subworkflow type", f"{AGENTSPEC}/budget.py"],
        d=["IMP-0129", "IMP-0189"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) colliding-internal-id fixture completes with two distinct receipts; (2) parent budget "
        "equals the sum of child budgets with no double count (ledger assertion).",
        ts=[
            "sibling subworkflows with identical internal ids do not collide",
            "budget roll-up exact, no double count",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Implement the HumanCheckpoint executor as an owner gate that never busy-waits",
        q="Target: on reaching a checkpoint, persist state, emit a terminal envelope with the exact question, and "
        "exit - then resume on answer. Acceptance: no process remains resident waiting, measured by process count "
        "before and after; and the question presented is ONE foundation-level question with a recommendation and a "
        "stated default (the owner-interaction contract at 11364-11370).",
        i=["IMP-0131 checkpoint type", "_USER-PROMPTS.md:11364-11370"],
        d=["IMP-0131"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) process count returns to baseline after a checkpoint (measured, not assumed); (2) the "
        "emitted question carries recommendation + default + durable record, asserted field-by-field.",
        ts=[
            "no resident process after checkpoint (process-table measurement)",
            "question payload carries recommendation, tradeoff, default, durable record",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["owner-blocked", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Implement the DynamicFanOut executor with an oracle-gated producer receipt",
        q="Target: expand a dynamic fan-out only after the producer receipt passes the shared completion oracle. "
        "Acceptance: a producer that exits 0 with a missing or progress-stream receipt expands to ZERO units and "
        "reports severed-stream - exit code zero alone is never success (10646).",
        i=["IMP-0132 type", f"{AGENTSPEC}/oracle.py", f"{AGENTSPEC}/progress.py"],
        d=["IMP-0132"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) exit-0-with-missing-receipt expands to zero and reports severed-stream; (2) the healthy "
        "twin expands to the expected cardinality.",
        ts=[
            "exit-0 + missing receipt => zero expansion + severed-stream (both-states)",
            "progress-stream body is never parsed as a result (assert the taxonomy reason)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["severed-stream", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement rate-limit-aware admission with staggered arrivals",
        q="Target: admit units on a schedule that staggers arrivals per rail so a fan-out does not become a "
        "thundering herd. Acceptance: measured inter-arrival times respect the configured stagger under a "
        "200-unit synthetic fan-out, and the scheduler is driven by an INJECTED clock so the test is deterministic.",
        i=["_USER-PROMPTS.md:10577 (stagger arrivals)", f"{AGENTSPEC}/clock.py"],
        d=["IMP-0135"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) inter-arrival histogram from a 200-unit synthetic run matches the configuration; "
        "(2) removing the stagger reproduces a burst (control proving the measurement can see the difference).",
        ts=[
            "200-unit synthetic fan-out respects the configured stagger (histogram assertion)",
            "stagger disabled => burst observed (both-states control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["rate-limited", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Make quota and observed arrival rate first-class scheduler inputs",
        q="Question: how should the scheduler behave when a rail starts returning 429? Target: feed measured quota "
        "and arrival rate back into admission with bounded backoff. Acceptance: a synthetic 429 storm degrades "
        "throughput but produces ZERO lost work units - every unit either completes or carries a typed "
        "rate-limited terminal record.",
        i=[
            f"{AGENTSPEC}/retry.py (rate-limited backoff)",
            "_USER-PROMPTS.md:11318 (429 arrival-rate storm)",
        ],
        d=["IMP-0220"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) unit accounting after a synthetic storm sums to 100% (completed + typed failures); "
        "(2) backoff is bounded - the run terminates rather than retrying indefinitely.",
        ts=[
            "synthetic 429 storm: zero lost units (accounting sums to 100%)",
            "backoff bounded; the run reaches a terminal state",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="bounded backoff on rate-limited; two strikes otherwise",
        fc=["rate-limited", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Implement per-unit pipeline isolation so one hung unit cannot deadlock the cohort",
        q="Target: give every work unit its own end-to-end pipeline with its own timeout, so a barrier never waits on "
        "a hung sibling beyond that sibling's declared timeout. Acceptance: a deliberately hung unit in a 50-unit "
        "cohort delays only itself - the other 49 complete, counted from the ledger. This is a measured "
        "orchestration failure on this estate (one hung agent deadlocked a whole phase).",
        i=[
            "rules/common/fan-out-contract.md",
            "_USER-PROMPTS.md:11318",
            f"{RAIL}/runner.py",
        ],
        d=["IMP-0220"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) 49/50 complete with one planted hang (counted); (2) the hung unit's terminal record is "
        "timeout-typed, not absent.",
        ts=[
            "planted hang: 49/50 complete, 1 typed timeout (both-states with a clean cohort)",
            "no barrier waits past a declared timeout (asserted from timestamps in the ledger)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["uncontrolled-silence", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Implement worktree provisioning and teardown per implementation shard",
        q="Target: provision a disposable git worktree per file-mutating unit and tear it down after harvest. "
        "Acceptance: two concurrent mutating units never share a git index - the measured contamination mode where "
        "a broad add sweeps a sibling's work - and teardown NEVER deletes a worktree whose content is not proven "
        "preserved elsewhere (content comparison, not commit ancestry, because squash-merge makes a merged branch "
        "report as ahead).",
        i=[
            "rules/common/single-signal-verification.md",
            "tools/gitcrypt-worktree",
            "tools/lib/git-diff.mjs",
        ],
        d=["IMP-0222"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) two concurrent mutating units produce disjoint staged sets (computed); (2) a teardown "
        "attempt on an unpreserved worktree is refused (detector fires on the dangerous state).",
        ts=[
            "concurrent mutators have disjoint indexes (computed set intersection == empty)",
            "teardown refused when content is not proven preserved (both-states)",
        ],
        rev="cross-vendor reviewer (Codex) - data-loss adjacent",
        retry="two-strikes",
        fc=["dependency-blocked", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the append-only resumable ledger writer with crash-safe atomic appends",
        q="Target: a single append-only run ledger that survives a hard kill mid-write. Acceptance: killing the "
        "process during a write leaves the ledger parseable with the partial record ABSENT rather than truncated - "
        "verified by a kill-loop test, not by reasoning about atomicity.",
        i=[
            "command-center/events/EVENTS.jsonl",
            "tools/event-ledger",
            "tools/lib/handled-ledger.mjs",
        ],
        d=["IMP-0144"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) 50 kill-loop iterations leave 50 parseable ledgers (computed pass count); (2) no "
        "iteration produces a half-written record (schema check over every line).",
        ts=[
            "50/50 kill-loop iterations leave a parseable ledger",
            "zero half-written records across the loop (per-line schema check)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["uncontrolled-silence", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement crash recovery that rebuilds run state from the ledger alone",
        q="Question: after a monitor or orchestrator dies while remote work continues, can state be rebuilt from the "
        "ledger with no in-memory context? Target: implement that rebuild. Acceptance: state reconstructed from "
        "the ledger equals the live state at kill time (field-by-field), and units that completed remotely DURING "
        "the outage are harvested rather than re-dispatched - 'monitor dies while remote work continues' is a "
        "named failure class (11315).",
        i=["_USER-PROMPTS.md:11315-11316", "IMP-0224 ledger"],
        d=["IMP-0224"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) reconstructed state equals a snapshot taken at kill time; (2) work completed during the "
        "outage appears as harvested, with dispatch count unchanged (no duplicate dispatch).",
        ts=[
            "reconstructed state == pre-kill snapshot (field equality)",
            "no duplicate dispatch after recovery (counted)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Wire the ONE shared completion reducer into every fan-in point",
        q="Target: local runner, cloud dispatcher, monitor, harvester, workflow fan-in, cross-vendor adapter and "
        "final synthesis all call agentspec.oracle.judge - no second predicate anywhere. Acceptance: an AST sweep "
        "finds zero local completion checks, and a planted second predicate FAILS the sweep. 'Two completion "
        "predicates disagree' (11314) becomes structurally impossible rather than tested for.",
        i=[
            f"{AGENTSPEC}/oracle.py",
            "_USER-PROMPTS.md:10648,11314",
            "tools/agentrail/tests/test_no_rival_core.py",
        ],
        d=["IMP-0216", "IMP-0217", "IMP-0219"],
        role="integrator",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) AST sweep over every runner/monitor/harvester module finds zero rival predicates; "
        "(2) a planted rival predicate makes the sweep fail (detector control).",
        ts=[
            "zero rival completion predicates across all fan-in modules (AST-computed)",
            "planted rival predicate detected",
        ],
        rev="cross-vendor reviewer (Codex) - the single most load-bearing invariant in the program",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the dry-run executor",
        q="Target: execute a workflow in dry-run, emitting the resolved plan, the cost estimate and the declared "
        "write set without side effects. Acceptance: the dry-run write set is a SUPERSET of the real run's actual "
        "writes on the same inputs - an under-declared blast radius is worse than no estimate.",
        i=["IMP-0142 dry-run semantics", "IMP-0143 estimator"],
        d=["IMP-0142", "IMP-0143"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) declared write set is a superset of observed writes across all fixtures (computed); "
        "(2) zero spawns and zero egress during the dry run (instrumented ports).",
        ts=[
            "declared writes superset of observed writes (computed, all fixtures)",
            "zero side effects during dry run (measured)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement the deterministic replay executor",
        q="Target: replay a recorded run, reproducing plan and verdicts with zero dispatch. Acceptance: replay of a "
        "run recorded on a DIFFERENT machine still reproduces the plan, proving no hidden host state leaked into "
        "the record; if it cannot, the missing input is named rather than the difference being explained away.",
        i=["IMP-0144 replay format", f"{AGENTSPEC}/determinism.py"],
        d=["IMP-0144"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) cross-machine replay reproduces the plan byte-for-byte (or names the missing input); "
        "(2) zero dispatches during replay, counted.",
        ts=[
            "cross-machine replay reproduces the plan or names the missing input",
            "zero dispatch during replay (counted, not assumed)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement the content-addressed artifact cache backend",
        q="Target: a content-addressed store behind the cache key, with integrity verification on read and an "
        "explicit corrupted-entry path. Acceptance: a corrupted entry is detected on read and refetched, never "
        "served - 'corrupted-cache tests' and 'stale cache masks a fixed package' are both named failure classes.",
        i=["IMP-0141 cache key", "_USER-PROMPTS.md:11013,11305"],
        d=["IMP-0141"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) a bit-flipped entry is detected on read (hash mismatch) and refetched; (2) a clean entry "
        "is served from cache with a measured hit (counter, not inference).",
        ts=[
            "bit-flipped entry detected and refetched (both-states with a clean entry)",
            "cache hit and miss counters are measured, and a stale entry never masks a fixed artifact",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
]
