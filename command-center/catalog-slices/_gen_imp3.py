"""Generator for catalog slice IMP-3 (implementation bucket B07, part 3 of 4).

Authored per-unit content; structural fields varied per family. Emits a JSON array of
128 work units IMP-0257..IMP-0384 to IMP-3.json.

Field names follow the unit brief's enumerated list (19 names, which is also exactly what
_USER-PROMPTS.md:10605-10625 enumerates). No extra keys: "strict plugin parser rejects
unknown fields" is a seeded failure class in this very spec (line 11302).
"""
import io
import json
import os

CORP = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SPEC = CORP + "/_USER-PROMPTS.md"

# --- spec anchors (verified by reading the range this session) -----------------
A_PRED = SPEC + ":10627-10648"          # one completion predicate everywhere
A_SCALE = SPEC + ":10570-10584"         # substrate doctrine
A_P7 = SPEC + ":10873-10913"            # Phase 7 workflow foundry
A_P7PROD = SPEC + ":11152-11170"        # foundry required production behavior
A_P7A = SPEC + ":10915-10946"           # Phase 7A council runtime
A_P2C = SPEC + ":10746-10767"           # CouncilSpec configuration surface
A_CPROD = SPEC + ":11172-11244"         # council required production behavior
A_P8 = SPEC + ":10948-10963"            # Phase 8 routing
A_P9 = SPEC + ":10965-10983"            # Phase 9 cross-vendor
A_P16 = SPEC + ":11135-11150"           # Phase 16 self-improvement loop
A_FAIL = SPEC + ":11298-11347"          # seeded regression failure classes
A_STOP = SPEC + ":11372-11399"          # program stopping conditions

# --- corpus inputs (existence verified by ls this session) ---------------------
C_SPEC = CORP + "/11-COUNCIL-SPECIFICATION.md"
C_SCHEMA = CORP + "/11-COUNCIL-SPECIFICATION.schema.json"
C_PROTO = CORP + "/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
C_CARDS = CORP + "/11-COUNCIL-OPTION-CARDS.md"
W_BP = CORP + "/09-WORKFLOW-BLUEPRINT-LIBRARY.json"
W_REG = CORP + "/08-WORKFLOW-CANDIDATE-REGISTRY.json"
W_PROV = CORP + "/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
W_MERGE = CORP + "/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
W_FUSE = CORP + "/10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md"
D_ARCH = CORP + "/13-ARCHITECTURE-CANDIDATES.md"
D_NOREG = CORP + "/14-NO-REGRESSION-CONTRACT.md"
D_PRECON = CORP + "/15-IMPLEMENTATION-PRECONDITIONS.md"
D_UNK = CORP + "/18-OPEN-UNKNOWNS-AND-PROBES.md"
D_PARITY = CORP + "/20-SKILL-PARITY.md"
R_PHASE = "command-center/PHASE-GRAPH.json"
R_GATES = "command-center/COMPLETION-GATES.json"

# --- retry policies ------------------------------------------------------------
R_PIVOT = ("two strikes then pivot (AGENTS.md 4b): after two failures sharing an error "
           "fingerprint, enumerate >=2 alternative designs before a third attempt")
R_NORETRY = ("no automatic retry on schema-invalid or contract-violation - the contract is "
             "frozen by B06; fix the spec via versioned migration or escalate to the owner")
R_TRANSIENT = ("retry up to 3x with staggered arrival (spec 10577) on transient 429/5xx only; "
               "never retry a deterministic assertion failure")
R_ONCE = ("single attempt; on failure preserve partial artifacts and emit FAILED:<id> with a "
          "two-signal blocker proof (spec 11400)")
R_CLEAN = ("retry once in a fresh worktree to rule out shared-index contamination from a "
           "sibling agent, then pivot")

REV_SOLO = ("one independent adversarial reviewer in a fresh context who did not author the "
            "module and starts from the tests, not the author's summary")
REV_CROSS = ("one cross-vendor reviewer (Codex via mcp__codex__codex, prompt-by-file) plus one "
             "Claude reviewer; a split verdict is resolved from the raw probe, not by vote")
REV_SEC = ("two reviewers: correctness plus a security refuter who defaults to REFUTED when "
           "evidence is insufficient (spec 11062)")
REV_OWNER = ("one independent adversarial reviewer plus an explicit owner sign-off block in the "
             "receipt; the reviewer may not grant the owner half")

T_R = ["Read", "Grep", "Glob"]
T_W = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
T_WP = ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "PowerShell"]
T_WX = ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "mcp__codex__codex"]

M_OPUS = {"vendor": "anthropic", "model": "opus", "role": "implementer"}
M_OPUS_ARCH = {"vendor": "anthropic", "model": "opus", "role": "runtime-architect"}
M_CODEX = {"vendor": "openai", "model": "codex-cli default via mcp__codex__codex (slug resolved "
                                    "at dispatch; do not pin - slugs churn)",
           "role": "implementer"}
M_DUAL = {"vendor": "anthropic+openai", "model": "opus authors the contract, codex-cli authors "
                                                 "the second independent implementation",
          "role": "differential-implementer"}

UNITS = []


def add(phase, title, q, inputs, deps, ev, tests, **kw):
    UNITS.append(dict(phase=phase, title=title, q=q, inputs=inputs, deps=deps, ev=ev,
                      tests=tests, kw=kw))


FAM = {
    "7":  dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="workflow-foundry-module",
               fc=["schema-invalid", "overclaim", "green-not-live", "dependency-blocked"]),
    "7A": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="council-runtime-module",
               fc=["schema-invalid", "overclaim", "detector-failure", "dependency-blocked"]),
    "8":  dict(sub="worktree-isolated", to=2700, tools=T_W, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="router-module",
               fc=["overclaim", "detector-failure", "green-not-live", "dependency-blocked"]),
    "9":  dict(sub="local-serialized", to=3600, tools=T_WP, rev=REV_CROSS, model=M_OPUS,
               retry=R_TRANSIENT, prof="crossvendor-module",
               fc=["severed-stream", "win-arg-limit", "green-not-live", "timeout",
                   "dependency-blocked"]),
    "16": dict(sub="local-serialized", to=3600, tools=T_WP, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="selfimprove-module",
               fc=["overclaim", "green-not-live", "detector-failure", "owner-blocked"]),
}

# ============================================================================
# PHASE 7 - workflow foundry runtime (27 units, IMP-0257..IMP-0283)
# ============================================================================
P7 = [A_P7, A_P7PROD, A_PRED]

add("7", "Workflow DSL schema and static validator",
    "Implement tools/foundry/schema/workflow.schema.json plus tools/foundry/validate.py so every "
    "built-in blueprint in 09-WORKFLOW-BLUEPRINT-LIBRARY.json validates and every stage names a "
    "typed input, output, and stop rule. Falsifiable question: does the validator REJECT a "
    "blueprint whose stage declares an output type no downstream stage consumes, and ACCEPT all "
    "108 library entries unchanged?",
    P7 + [W_BP, D_PRECON],
    ["B06"],
    "1) validate.py exit code over all 108 library entries; 2) an independent jsonschema CLI run "
    "(different implementation) over the same files agreeing entry-for-entry.",
    ["unit: 108/108 library entries validate",
     "negative control: an orphan-output stage mutation must FAIL validation",
     "negative control: an unknown top-level key must FAIL (spec 11302 strict-parser class)"],
    retry=R_NORETRY, prof="workflow-schema-artifact")

add("7", "Workflow SDK typed authoring API",
    "Implement tools/foundry/sdk.py exposing Workflow/Stage/Gate/Tool/StopRule builders that can "
    "only emit schema-valid documents. Falsifiable question: is it possible to construct any "
    "document through the SDK that IMP-0257's validator rejects?",
    P7 + [W_BP],
    ["IMP-0257"],
    "1) a Hypothesis property test generating random SDK call sequences, asserting validator-clean "
    "output; 2) round-trip: SDK -> JSON -> parse -> SDK, structural equality by canonical hash.",
    ["property: 500 generated SDK programs all validate",
     "negative control: bypassing the builder and hand-patching the dict must produce a document "
     "the validator rejects, proving the property test can fail"],
    prof="workflow-sdk-module")

add("7", "Structured workflow builder surface",
    "Implement tools/foundry/builder/ as a structured (non-graphical) builder: a guided CLI that "
    "composes a workflow from typed prompts and writes it through the SDK. Falsifiable question: "
    "can a user who has never read the schema produce a passing workflow in <=12 prompts, and does "
    "every builder field map 1:1 onto a schema property with no builder-only fields?",
    P7 + [D_ARCH],
    ["IMP-0258"],
    "1) a scripted non-interactive transcript driving the builder end to end and validating the "
    "output; 2) a set-difference check builder_fields vs schema_properties printing both "
    "directions, required empty.",
    ["integration: scripted 12-answer transcript yields a valid workflow",
     "negative control: remove one schema property and assert the field-parity check FAILS"],
    prof="workflow-builder-surface")

add("7", "Runtime parameter validation and typed coercion",
    "Implement tools/foundry/params.py so invocation-time arguments are validated and coerced "
    "against the stage's declared types before any tool call. Falsifiable question: does a string "
    "'12' supplied for an int parameter coerce, while '12abc' aborts BEFORE the first side effect "
    "rather than mid-stage?",
    P7,
    ["IMP-0257"],
    "1) a side-effect spy asserting zero tool calls occurred on the aborting case; 2) the process "
    "exit code plus an empty artifact directory listing.",
    ["unit: coercion matrix across str/int/float/bool/path/enum",
     "negative control: a mutation that moves validation AFTER the first tool call must make the "
     "side-effect spy assertion fail"],
    to=1800, prof="workflow-runtime-module")

add("7", "Subworkflow invocation with scope and namespace isolation",
    "Implement tools/foundry/subworkflow.py so a workflow can invoke another by id with an "
    "explicit input mapping and no ambient variable leakage. Falsifiable question: can a "
    "subworkflow read or write any parent variable that was not explicitly mapped?",
    P7 + [W_BP],
    ["IMP-0257", "IMP-0260"],
    "1) an isolation test asserting KeyError on an unmapped parent variable; 2) a memory-scope dump "
    "diff between parent and child frames showing disjoint key sets.",
    ["unit: 3-level nesting preserves mapping fidelity",
     "negative control: delete the scope guard and assert the leakage test goes red"],
    prof="workflow-runtime-module")

add("7", "Dynamic fan-out operator with runtime-determined width",
    "Implement tools/foundry/fanout.py so a stage can expand into N children where N is computed at "
    "runtime, with staggered arrival and a per-child artifact path. Falsifiable question: at N=200 "
    "does the operator stagger arrivals so no more than the configured concurrency is in flight, and "
    "does one child's crash leave the other 199 artifacts intact?",
    P7 + [A_SCALE],
    ["IMP-0257", "IMP-0263"],
    "1) an arrival-timestamp histogram from the child receipts proving the stagger; 2) a "
    "filesystem census after an injected child crash showing 199 artifacts present.",
    ["load: N=200 simulated children under a concurrency cap of 8",
     "chaos: kill one child mid-write; siblings must still be complete",
     "negative control: remove the stagger and assert the histogram test FAILS"],
    to=5400, sub="cloud-batch", prof="workflow-runtime-module")

add("7", "Barrier and fan-in bound to the shared completion predicate",
    "Implement tools/foundry/barrier.py so every fan-in calls the ONE shared completion reducer "
    "(IMP-0376) and never a local re-implementation. Falsifiable question: does a child that exits "
    "0 with a missing or unparseable artifact count as INCOMPLETE at the barrier, and is there any "
    "code path in the foundry that decides completeness without calling the shared reducer?",
    P7 + [A_PRED, R_GATES],
    ["IMP-0257", "IMP-0376"],
    "1) a call-graph grep proving exactly one completeness implementation is reachable from the "
    "barrier; 2) an exit-0-with-missing-artifact fixture returning INCOMPLETE.",
    ["unit: all 12 predicate conditions exercised individually",
     "negative control: exit-code-only shortcut mutation must be caught by the fixture",
     "duplicate-predicate test: a second reducer added to the tree must fail the call-graph check"],
    prof="workflow-runtime-module",
    fc=["overclaim", "green-not-live", "detector-failure", "duplicate-control-plane"])

add("7", "Loop construct with explicit convergence rules",
    "Implement tools/foundry/loop.py supporting until/while loops whose termination is a typed "
    "convergence expression plus a hard iteration ceiling. Falsifiable question: does a loop whose "
    "convergence metric is monotonically NOT improving terminate by the no-information-gain rule "
    "rather than only by the ceiling?",
    P7,
    ["IMP-0257", "IMP-0272"],
    "1) an iteration trace showing the no-gain exit fired before the ceiling; 2) a separate run with "
    "the gain rule disabled hitting the ceiling, proving the two exits are distinguishable.",
    ["unit: converging, oscillating and flat metric series",
     "negative control: a flat series must NOT be reported as converged-successfully"],
    to=1800, prof="workflow-runtime-module")

add("7", "Human checkpoint primitive with durable pause and resume",
    "Implement tools/foundry/checkpoint.py so a workflow can suspend at an owner gate, persist full "
    "state, and resume in a different process. Falsifiable question: after a machine restart, does "
    "resume reproduce the identical downstream artifact set as an uninterrupted run?",
    P7 + [A_PRED],
    ["IMP-0257", "IMP-0268"],
    "1) byte-comparison of artifacts from an interrupted-then-resumed run vs a straight-through run; "
    "2) a fresh PowerShell process performing the resume, proving no in-memory dependency.",
    ["integration: pause, kill the process, resume in a new shell",
     "negative control: corrupt the checkpoint file and assert resume REFUSES rather than "
     "silently starting over"],
    sub="local-serialized", prof="workflow-runtime-module")

add("7", "Retry engine with backoff, jitter and fingerprint-aware pivot",
    "Implement tools/foundry/retry.py so retries are bounded per error fingerprint and a repeated "
    "identical failure escalates instead of grinding. Falsifiable question: does a deterministic "
    "assertion failure retry ZERO times while a 429 retries with increasing jitter?",
    P7 + [A_SCALE],
    ["IMP-0257", "IMP-0275"],
    "1) the retry ledger showing attempt counts keyed by fingerprint; 2) wall-clock deltas between "
    "attempts proving backoff, measured independently of the ledger.",
    ["unit: transient vs deterministic classification matrix",
     "negative control: mislabel a deterministic error as transient and assert the grind-guard "
     "test FAILS"],
    to=1800, retry=R_ONCE, prof="workflow-runtime-module")

add("7", "Repair loop with attempt limit and proof-of-impossibility exit",
    "Implement tools/foundry/repair.py implementing fix-review: weak output is returned to the "
    "producing stage until it passes, the attempt limit is hit, or a proof-of-impossibility record "
    "is written. Falsifiable question: when evidence genuinely cannot be obtained, does the loop "
    "emit a structured impossibility record naming the missing prerequisite rather than a "
    "low-quality pass?",
    P7 + [SPEC + ":11272-11278"],
    ["IMP-0266", "IMP-0275"],
    "1) the impossibility record's schema validation plus its named missing prerequisite; 2) an "
    "independent replay of the same input confirming the loop does not eventually pass it.",
    ["integration: unfixable input yields PROOF_OF_IMPOSSIBILITY, not PASS",
     "integration: fixable-on-attempt-2 input yields PASS with attempts=2",
     "negative control: remove the quality gate and assert the unfixable input wrongly passes"],
    prof="workflow-runtime-module")

add("7", "Resume from partial state over a resumable ledger",
    "Implement tools/foundry/resume.py so an interrupted run restarts from the last completed "
    "stage using the append-only event ledger, never re-running a completed side effect. "
    "Falsifiable question: does a resume after stage 7 of 12 re-execute any stage 1-7 tool call?",
    P7 + [A_PRED, "command-center/events/EVENTS.jsonl"],
    ["IMP-0263", "IMP-0270"],
    "1) a tool-call audit log comparing pre-kill and post-resume call sets; 2) artifact mtimes "
    "proving stages 1-7 files were not rewritten.",
    ["integration: kill at each of 12 stages, resume, compare final state",
     "negative control: truncate the ledger and assert resume refuses instead of guessing"],
    sub="local-serialized", prof="workflow-runtime-module")

add("7", "Deterministic replay of a recorded run",
    "Implement tools/foundry/replay.py so a recorded run can be re-executed against recorded tool "
    "responses producing byte-identical artifacts. Falsifiable question: does replay detect and "
    "REFUSE when the workflow definition changed since recording, rather than silently replaying "
    "against a different graph?",
    P7,
    ["IMP-0268", "IMP-0279"],
    "1) sha256 equality of every artifact between original and replay; 2) a definition-hash "
    "mismatch case exiting non-zero with the two hashes printed.",
    ["unit: 5 recorded runs replay byte-identically",
     "negative control: mutate one recorded tool response and assert replay diverges loudly",
     "negative control: nondeterministic clock/random use must break replay, proving the "
     "determinism harness works"],
    prof="workflow-runtime-module")

add("7", "Artifact cache with content-addressed keys and explicit invalidation",
    "Implement tools/foundry/cache.py keyed on (stage definition hash, resolved inputs hash, tool "
    "policy hash). Falsifiable question: does editing ONLY the stage prompt invalidate the entry, "
    "and does a corrupted cache entry fail closed rather than serving garbage?",
    P7 + [A_FAIL],
    ["IMP-0257"],
    "1) hit/miss counters across a matrix of single-field edits; 2) a deliberately corrupted entry "
    "producing a miss plus a quarantine record, verified by directory listing.",
    ["unit: each key component independently invalidates",
     "negative control (spec 11305 stale-cache class): a fixed package behind a stale entry must "
     "NOT be served"],
    to=1800, prof="workflow-runtime-module")

add("7", "Dry-run planner and static execution preview",
    "Implement tools/foundry/dryrun.py so a workflow can be planned without side effects, printing "
    "the stage order, fan-out widths, tool calls and gates it WOULD perform. Falsifiable question: "
    "does the dry-run plan match the real execution trace stage-for-stage on all flagship "
    "workflows, and does dry-run perform exactly zero writes?",
    P7,
    ["IMP-0257", "IMP-0262"],
    "1) a filesystem snapshot hash before and after dry-run showing zero change; 2) a diff of the "
    "predicted plan against the real trace of the same workflow.",
    ["integration: plan-vs-trace equality on 10 workflows",
     "negative control: insert a hidden write into a stage and assert the zero-write check FAILS"],
    to=1800, prof="workflow-runtime-module")

add("7", "Cost, time and impact estimator",
    "Implement tools/foundry/estimate.py producing a pre-run estimate of token cost, wall-clock and "
    "blast radius (files touched, external calls). Falsifiable question: on 20 historical runs, is "
    "the estimator's interval calibrated - do 80 percent of actuals fall inside the 80 percent "
    "band, and does it ever under-report the file blast radius?",
    P7 + [R_PHASE],
    ["IMP-0271"],
    "1) a calibration table over 20 recorded runs with coverage counted mechanically; 2) a "
    "set-inclusion check that the predicted file set is a superset of the actual touched set.",
    ["calibration: 80 percent band coverage measured, not asserted",
     "negative control: a run touching an unpredicted file must FAIL the superset check"],
    to=2700, sub="local-parallel", tools=T_R + ["Bash", "Write"],
    prof="workflow-analysis-artifact")

add("7", "Per-stage source and tool policy enforcement",
    "Implement tools/foundry/policy.py so each stage runs under a declared allowlist of tools and "
    "source classes, enforced at call time. Falsifiable question: does a stage that requests a tool "
    "outside its allowlist get DENIED at the boundary, and is the denial recorded as an event rather "
    "than swallowed?",
    P7 + [A_P7PROD],
    ["IMP-0260", "IMP-0275"],
    "1) a denial event in the append-only log with the requested tool name; 2) the tool's own "
    "invocation counter showing zero calls.",
    ["unit: allow, deny and escalate paths per tool class",
     "negative control: widen the allowlist and assert the denial test goes green, proving the "
     "test is sensitive to the policy and not to unrelated failure"],
    to=1800, prof="workflow-policy-module",
    fc=["overclaim", "injection", "detector-failure", "dependency-blocked"])

add("7", "Model routing policy with vendor-diversity constraints",
    "Implement tools/foundry/routing.py mapping a stage's declared role and risk class onto a "
    "model/vendor, honouring a diversity constraint for independent-verification stages. "
    "Falsifiable question: can a verification stage ever be routed to the SAME model instance that "
    "produced the artifact it verifies?",
    P7 + [A_P7PROD, D_ARCH],
    ["IMP-0257"],
    "1) a constraint-solver unit test enumerating all role pairs; 2) a run-log audit over a full "
    "workflow proving no producer/verifier vendor collision occurred.",
    ["unit: diversity constraint satisfied or explicitly waived with a reason",
     "negative control: remove the constraint and assert the audit detects the collision"],
    to=1800, prof="workflow-policy-module")

add("7", "Failure policy engine mapping classification to action",
    "Implement tools/foundry/failure.py so each failure classification (severed-stream, "
    "win-arg-limit, timeout, schema-invalid, dependency-blocked, owner-blocked) maps to a declared "
    "action: retry, pivot, escalate, quarantine or abort. Falsifiable question: is there any "
    "failure that reaches the runtime with NO classification and therefore no declared action?",
    P7 + [A_FAIL],
    ["IMP-0266", "IMP-0263"],
    "1) an exhaustiveness test over the classification enum with a compile-time-style total match; "
    "2) a chaos run injecting 12 distinct failures and confirming each produced a classified event.",
    ["unit: enum exhaustiveness (an added member must break the build)",
     "chaos: 12 injected failure shapes all classified",
     "negative control: an unclassified exception must surface as FAILED, never as success"],
    prof="workflow-policy-module")

add("7", "Portable workflow package export and import",
    "Implement tools/foundry/package.py producing a self-contained, versioned workflow pack "
    "(definition, presets, fixtures, lineage, license) and importing it into a clean install. "
    "Falsifiable question: does the exported pack ever contain .git, caches, transcripts or "
    "credentials, and does it import into a machine that has never seen the source repo?",
    P7 + [A_FAIL, SPEC + ":10842"],
    ["IMP-0257", "IMP-0279"],
    "1) a pack manifest census asserting the excluded-path set is empty; 2) an import into a fresh "
    "temp profile with no repo present, then a smoke run of the imported workflow.",
    ["packaging: excluded-path census (spec 11307 .git/huge-file class)",
     "clean-install: import and execute on a profile with no source tree",
     "negative control: plant a fake credential file and assert the census FAILS"],
    sub="local-serialized", tools=T_WP, prof="workflow-package-artifact",
    fc=["schema-invalid", "green-not-live", "overclaim", "dependency-blocked"])

add("7", "Semantic diff and duplicate-collapse over the blueprint library",
    "Implement tools/foundry/semdiff.py which compares two workflows on extracted stage/role/gate/"
    "stop-rule structure (not prose) and collapses duplicates, producing the machine-readable "
    "distinctness catalog the spec demands for the 96-entry floor. Falsifiable question: with "
    "planted mutants (exact rename, one-parameter fork, full paraphrase), which of the three does "
    "structural diff catch that token-similarity misses?",
    P7 + [W_BP, SPEC + ":10909"],
    ["IMP-0257"],
    "1) planted-mutant recall measured against a hand-labelled key; 2) a second, mechanically "
    "different similarity metric (structure hash vs token Jaccard) reported side by side with "
    "disagreements listed rather than averaged.",
    ["control: 3 planted mutant classes, recall reported per class not pooled",
     "negative control: two genuinely distinct blueprints must NOT collapse (false-positive rate "
     "reported)"],
    to=5400, sub="cloud-batch", prof="workflow-analysis-artifact",
    fc=["overclaim", "detector-failure", "count-gaming", "dependency-blocked"])

add("7", "Fusion algebra engine for all seven composition modes",
    "Implement tools/foundry/fusion.py supporting stage-splice, common-core, union, best-of-breed, "
    "conditional-hybrid, ensemble and progressive fusion as typed operations over the component "
    "graph. Falsifiable question: does any fusion produce a second control plane or silently drop a "
    "source capability, and is a fused workflow accepted purely for having more stages?",
    P7 + [W_MERGE, W_FUSE, A_P7PROD],
    ["IMP-0277", "IMP-0279"],
    "1) a capability set-difference check source_union minus fused, required empty; 2) an "
    "acceptance gate reading the benchmark result, proving stage count alone cannot certify.",
    ["unit: each of the 7 modes on a fixture pair",
     "invariant: no fusion introduces a second control plane (spec 10727)",
     "negative control: drop one source capability and assert the set-difference check FAILS"],
    to=5400, prof="workflow-fusion-module",
    fc=["lineage-loss", "duplicate-control-plane", "overclaim", "dependency-blocked"])

add("7", "Lineage recorder and decomposition back to source components",
    "Implement tools/foundry/lineage.py so every fused workflow records source ids, licenses and "
    "credit, and can be mechanically decomposed back into its sources. Falsifiable question: for "
    "every fused artifact, does decompose(fuse(A,B)) return components equivalent to A and B, and "
    "is any license or provenance field lost in the round trip?",
    P7 + [W_PROV, A_P7PROD],
    ["IMP-0278"],
    "1) a round-trip equivalence test over 20 fusions; 2) a license-field census before and after, "
    "compared as sets.",
    ["property: fuse-then-decompose round trip on 20 pairs",
     "negative control (spec 11334 provenance-loss class): strip one license field and assert the "
     "census FAILS"],
    prof="workflow-fusion-module",
    fc=["lineage-loss", "overclaim", "schema-invalid", "dependency-blocked"])

add("7", "Workflow tournament and A/B benchmark harness",
    "Implement tools/foundry/tournament.py running source and fused workflows on matched benchmark "
    "cases with paired statistics. Falsifiable question: can a fused workflow that performs worse "
    "than every one of its sources still be reported as a winner, and does the harness resist "
    "benchmark gaming by a workflow that detects the fixture?",
    P7 + [A_P7PROD, SPEC + ":11170"],
    ["IMP-0278", "IMP-0272"],
    "1) paired per-case scores with the win/loss table printed per source, not pooled; 2) a "
    "held-out fixture set never seen by any candidate, run second.",
    ["benchmark: matched-case A/B with per-source comparison",
     "anti-gaming: a candidate that special-cases the fixture must score at chance on held-out",
     "negative control: a deliberately worse fusion must be reported as WORSE"],
    to=5400, sub="cloud-batch", prof="workflow-benchmark-artifact",
    fc=["overclaim", "benchmark-gaming", "detector-failure", "dependency-blocked"])

add("7", "Certification, deprecation and supersession state machine",
    "Implement tools/foundry/certify.py with states DRAFT, CANDIDATE, CERTIFIED, DEPRECATED, "
    "SUPERSEDED and legal transitions gated on benchmark evidence. Falsifiable question: is there "
    "any transition into CERTIFIED that does not require a tournament receipt and an independent "
    "reviewer PASS?",
    P7 + [W_FUSE, A_PRED],
    ["IMP-0280"],
    "1) a transition-table test enumerating every (state, event) pair; 2) an attempt to certify "
    "without a receipt, expected to be refused with the missing prerequisite named.",
    ["unit: full transition table including illegal transitions",
     "negative control: remove the receipt requirement and assert the refusal test goes green, "
     "proving the test targets the gate"],
    to=1800, prof="workflow-lifecycle-module")

add("7", "workflow-scout executable meta-workflow",
    "Implement tools/foundry/meta/scout.workflow.json plus its runner so that, given a goal and "
    "constraints, it searches local, marketplace, repository, paper and transcript sources, verifies "
    "provenance and license, and returns a ranked adopt/adapt/merge/compose/build recommendation. "
    "Falsifiable question: when a superior existing workflow already exists in the library, does "
    "scout find it rather than recommending BUILD?",
    P7 + [W_REG, W_PROV, A_FAIL],
    ["IMP-0257", "IMP-0277"],
    "1) a plant-and-find control: a known-superior workflow is placed in the library and scout must "
    "return it; 2) a provenance check on every returned candidate resolving to a real source record.",
    ["control (spec 11331 rebuild-instead-of-discover class): planted superior workflow must be "
     "found, and the same query with it removed must recommend BUILD",
     "negative control: a candidate with no license record must be flagged, not silently ranked"],
    to=5400, prof="workflow-meta-artifact",
    fc=["overclaim", "detector-failure", "lineage-loss", "dependency-blocked"])

add("7", "workflow-forge executable meta-workflow",
    "Implement tools/foundry/meta/forge.workflow.json plus its runner so that, given scout output, "
    "it decomposes mechanisms, synthesises a candidate, benchmarks it against its sources and "
    "returns both the executable workflow and an evidence-backed rationale. Falsifiable question: "
    "does forge ever emit a workflow it did not benchmark, and is the returned rationale traceable "
    "to specific tournament receipts?",
    P7 + [A_P7PROD],
    ["IMP-0282", "IMP-0280", "IMP-0279"],
    "1) every emitted workflow carries a tournament receipt id that resolves on disk; 2) a "
    "rationale-to-receipt link check with unresolved links listed.",
    ["integration: forge on 3 goals, each output benchmarked and traceable",
     "negative control: delete a receipt and assert the link check FAILS rather than degrading to "
     "an unsupported rationale"],
    to=5400, prof="workflow-meta-artifact")

# ============================================================================
# PHASE 7A - universal council runtime (69 units, IMP-0284..IMP-0352)
# ============================================================================
P7A = [A_P7A, A_P2C, A_CPROD, C_SPEC, C_SCHEMA]

# -- core (4)
add("7A", "CouncilSpec JSON Schema and versioned validator",
    "Implement tools/council/schema/councilspec.schema.json covering all 13 sections measured in "
    "11-COUNCIL-SPECIFICATION.schema.json (charter, participants, roles, engagement, budgets, "
    "evidence, voting, stopping, outcomes, integrity, artifacts, execution, meta) plus "
    "tools/council/validate.py. Falsifiable question: do all 72 presets in "
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json validate unchanged, and does an unknown section key "
    "fail closed?",
    P7A + [C_PROTO],
    ["B05", "B06"],
    "1) validator exit status over all 72 presets and 58 protocols; 2) an independent jsonschema "
    "CLI over the same inputs agreeing item-for-item.",
    ["unit: 72/72 presets and 58/58 protocols validate",
     "negative control: unknown section key must FAIL (strict-parser class, spec 11302)",
     "negative control: a preset missing a stopping rule must FAIL"],
    retry=R_NORETRY, prof="council-schema-artifact")

add("7A", "CouncilSpec compiler lowering a spec to a typed execution plan",
    "Implement tools/council/compile.py turning a validated CouncilSpec into an explicit round/turn/"
    "gate plan before any model call. Falsifiable question: is the compiled plan a pure function of "
    "the spec - do two compiles of the same spec produce byte-identical plans - and does the plan "
    "name every participant, round and gate it will execute?",
    P7A,
    ["IMP-0284"],
    "1) sha256 equality across repeated compiles of 20 specs; 2) a plan-vs-trace diff after "
    "executing one compiled plan.",
    ["property: compile determinism over 20 specs",
     "negative control: introduce a dict-ordering dependency and assert the determinism test FAILS"],
    prof="council-compiler-module")

add("7A", "CouncilSpec versioning and migration",
    "Implement tools/council/migrate.py so a v1 spec is migrated to v2 with an explicit, tested "
    "transform, honouring the frozen-schema rule (spec 10660). Falsifiable question: does an "
    "un-migrated v1 spec run silently under v2 semantics, or is it refused with the required "
    "migration named?",
    P7A + [SPEC + ":10660"],
    ["IMP-0284"],
    "1) a refusal path printing the source and target versions; 2) a migrated-then-executed spec "
    "producing the same decision as the v1 runtime on a recorded fixture.",
    ["unit: v1->v2 field mapping table",
     "negative control: remove the version check and assert the silent-run case is detected"],
    to=1800, retry=R_NORETRY, prof="council-compiler-module")

add("7A", "Council runtime kernel: round scheduler and turn state machine",
    "Implement tools/council/kernel.py owning rounds, turn order, turn length, response obligations "
    "and the single event loop every topology and protocol plugs into. Falsifiable question: can any "
    "topology advance a round without the kernel recording a turn event, i.e. is there a bypass path?",
    P7A,
    ["IMP-0285"],
    "1) an event-count invariant: turns_recorded == turns_executed across a full council; 2) a "
    "call-graph check that no topology module writes participant output directly.",
    ["unit: turn ordering, turn timeout, obligation enforcement",
     "invariant: event count equals executed turns",
     "negative control: add a direct-write bypass in a test topology and assert the call-graph "
     "check FIRES"],
    model=M_OPUS_ARCH, prof="council-kernel-module")

# -- participants (11)
add("7A", "Participant registry and identity model",
    "Implement tools/council/participants/registry.py holding participant identity, vendor, model, "
    "declared expertise, calibration history pointer and tool grants. Falsifiable question: are two "
    "participants with identical vendor+model+prompt+tools distinguishable as independent voices, "
    "or should the registry mark them as one effective voice?",
    P7A + [C_CARDS],
    ["IMP-0284"],
    "1) a fingerprint collision report over a 12-seat roster; 2) an independence audit comparing "
    "first-round outputs of flagged pairs.",
    ["unit: fingerprint computation stability",
     "negative control: seat the same configuration twice and assert the collision report FIRES"],
    to=1800, prof="council-participants-module")

add("7A", "Explicit roster resolver",
    "Implement the exact-participant path in tools/council/participants/select_explicit.py so a "
    "named roster is resolved, validated against role requirements and failed loudly when a named "
    "participant is unavailable. Falsifiable question: does an unavailable named participant get "
    "silently substituted?",
    P7A,
    ["IMP-0288"],
    "1) an unavailability fixture producing a refusal event naming the participant; 2) the seated "
    "roster compared as a set against the requested roster.",
    ["unit: exact roster round trip",
     "negative control: enable auto-substitution and assert the set comparison FAILS"],
    to=1800, prof="council-participants-module")

add("7A", "Auto-composed participant selector with per-choice explanation",
    "Implement tools/council/participants/select_auto.py which derives roles and seat count from the "
    "task and emits a human-readable reason per seat plus an owner-override hook. Falsifiable "
    "question: for a task with an obvious missing expertise (e.g. legal), does auto-composition seat "
    "it, and is every seat's reason grounded in a task feature rather than boilerplate?",
    P7A + [SPEC + ":10765"],
    ["IMP-0288", "IMP-0292"],
    "1) a missing-expertise control task where the expected role must appear; 2) a reason-diversity "
    "check rejecting identical reason strings across seats.",
    ["control: 6 task archetypes, expected role present in each",
     "negative control: a task with no legal dimension must NOT seat a legal role (false-positive "
     "rate reported)"],
    prof="council-participants-module")

add("7A", "Calibration-ranked selector over a persistent calibration store",
    "Implement tools/council/participants/select_calibrated.py ranking candidates by historical "
    "calibration (Brier or log score) from the store written by IMP-0352. Falsifiable question: with "
    "an empty store, does the selector degrade loudly to another strategy rather than ranking on "
    "zeros?",
    P7A,
    ["IMP-0288", "IMP-0352"],
    "1) a cold-store run emitting an explicit degradation event; 2) a warm-store run whose ranking "
    "matches an independently computed score table.",
    ["unit: score computation against a hand-computed fixture",
     "negative control: empty store must not silently produce a confident ranking"],
    to=1800, prof="council-participants-module",
    fc=["overclaim", "detector-failure", "dependency-blocked", "uncontrolled-silence"])

add("7A", "Expertise-ranked selector with claimed-vs-demonstrated verification",
    "Implement tools/council/participants/select_expertise.py matching task tags to declared "
    "expertise AND verifying the claim against a demonstrated-competence probe before seating. "
    "Falsifiable question: can a participant that merely asserts expertise be seated as the domain "
    "authority without passing the probe (the hallucinated-expertise class, spec 11241)?",
    P7A + [A_CPROD],
    ["IMP-0288"],
    "1) a probe result attached to each seated expert; 2) an unseated-claimant list proving the "
    "probe can reject.",
    ["unit: tag matching precision/recall on a labelled fixture",
     "negative control: a bogus expertise claim must be rejected by the probe"],
    prof="council-participants-module")

add("7A", "Random and stratified samplers with a recorded deterministic seed",
    "Implement tools/council/participants/select_random.py providing uniform and stratified sampling "
    "whose seed is recorded in the run artifact. Falsifiable question: can a run be reproduced "
    "seat-for-seat from the recorded seed alone?",
    P7A,
    ["IMP-0288"],
    "1) two runs with the same recorded seed producing identical rosters; 2) a chi-square check that "
    "stratum proportions match the requested strata.",
    ["unit: reproducibility from seed",
     "statistical: stratum proportion check over 1000 draws",
     "negative control: unseeded RNG must break the reproducibility test"],
    to=1800, sub="local-parallel", prof="council-participants-module")

add("7A", "Stakeholder-balanced selector",
    "Implement tools/council/participants/select_stakeholder.py which seats declared stakeholder "
    "classes to a target balance and reports any class it could not fill. Falsifiable question: when "
    "a stakeholder class cannot be filled, does the council proceed silently under-represented?",
    P7A,
    ["IMP-0288"],
    "1) an unfilled-class report present in the run artifact; 2) a per-class seat census compared "
    "against the requested balance.",
    ["unit: balance arithmetic across 5 class mixes",
     "negative control: suppress the unfilled report and assert the census check FAILS"],
    to=1800, prof="council-participants-module")

add("7A", "Model and vendor diversity constraint solver",
    "Implement tools/council/participants/diversity.py enforcing minimum vendor/model diversity as a "
    "hard constraint with an explicit waiver record when it cannot be met. Falsifiable question: "
    "when only one vendor is reachable, does the council run anyway while REPORTING that its "
    "independence assumption is void?",
    P7A + [A_CPROD],
    ["IMP-0288"],
    "1) a solver unit test over infeasible and feasible constraint sets; 2) a waiver record present "
    "in the artifact whenever diversity < requested, checked mechanically.",
    ["unit: feasible/infeasible constraint matrix",
     "negative control: remove the waiver emission and assert the artifact check FAILS"],
    to=1800, prof="council-participants-module")

add("7A", "Adversarial-pairing selector",
    "Implement tools/council/participants/select_adversarial.py which deliberately seats opposed "
    "positions or a dedicated refuter against each proposer. Falsifiable question: does the pairing "
    "measurably increase first-round position spread compared with an unpaired council on the same "
    "question?",
    P7A,
    ["IMP-0288", "IMP-0317"],
    "1) first-round position-spread metric, paired vs unpaired, on the same 10 questions; 2) a "
    "manual read of 3 transcripts confirming the refuter actually opposed rather than agreed.",
    ["experiment: spread comparison across 10 matched questions",
     "negative control: a refuter that agrees with everything must be flagged by the spread metric"],
    prof="council-participants-module")

add("7A", "Elastic scaling and dynamic mid-run recruitment",
    "Implement tools/council/participants/elastic.py so seat count grows within min/max when "
    "coverage or expertise gaps are detected mid-run. Falsifiable question: does a recruited "
    "participant receive the same information partition as an original seat, or does it inherit the "
    "existing consensus and therefore add no independence?",
    P7A,
    ["IMP-0288", "IMP-0297"],
    "1) a context diff between a recruited seat and an original seat; 2) an independence check "
    "comparing the recruit's first output against the running consensus.",
    ["unit: scale-up trigger conditions",
     "negative control: feed the recruit the consensus transcript and assert the independence check "
     "FIRES"],
    prof="council-participants-module")

add("7A", "Participant replacement and eviction on inactivity or failure",
    "Implement tools/council/participants/replace.py evicting a participant that breaches max "
    "inactivity or fails repeatedly, preserving its prior contributions in the record. Falsifiable "
    "question: does eviction ever delete or orphan an evicted participant's earlier votes and ideas?",
    P7A,
    ["IMP-0288", "IMP-0311"],
    "1) an artifact census before and after eviction showing prior contributions retained; 2) the "
    "vote tally recomputed with the documented eviction rule and compared to the recorded tally.",
    ["unit: eviction triggers and quorum recomputation",
     "negative control: drop the evicted member's ideas and assert the census FAILS"],
    to=1800, prof="council-participants-module")

# -- integrity (4)
add("7A", "Anonymity layer with per-round unlinkable pseudonyms",
    "Implement tools/council/integrity/anonymity.py mapping real participants to per-round "
    "pseudonyms so a reader cannot link positions across rounds when anonymity is configured. "
    "Falsifiable question: can identity be recovered from residual metadata - ordering, timing, token "
    "counts or style - even when names are masked?",
    P7A + [A_P2C],
    ["IMP-0287"],
    "1) a linkage attack script attempting re-identification from the artifact alone, reporting "
    "accuracy vs chance; 2) a field census proving no real id appears in the anonymised artifact.",
    ["security: linkage attack must be at chance level, accuracy reported",
     "negative control: leave ordering unshuffled and assert the attack accuracy rises above chance"],
    rev=REV_SEC, prof="council-integrity-module",
    fc=["overclaim", "detector-failure", "injection", "dependency-blocked"])

add("7A", "Conflict-of-interest declaration and incompatible-role checker",
    "Implement tools/council/integrity/coi.py requiring a declared interest per seat and refusing "
    "role combinations the spec calls incompatible (e.g. proposer also judging its own proposal). "
    "Falsifiable question: is there any path by which a participant reviews or votes on an artifact "
    "it authored?",
    P7A + [A_P7A],
    ["IMP-0300", "IMP-0288"],
    "1) an authorship-vs-vote cross-reference over a full run, required empty; 2) a refusal event "
    "for a deliberately constructed self-review roster.",
    ["unit: incompatible-role matrix",
     "negative control (spec 11242 hidden-COI class): allow self-review and assert the "
     "cross-reference FIRES"],
    prof="council-integrity-module")

add("7A", "Information-partition engine",
    "Implement tools/council/integrity/partition.py delivering per-participant redacted context so "
    "configured partitions genuinely differ. Falsifiable question: does any participant receive a "
    "token it was partitioned away from, measured by scanning delivered prompts rather than by "
    "reading the config?",
    P7A + [A_P2C],
    ["IMP-0287"],
    "1) a delivered-prompt scan for partitioned tokens, required zero hits; 2) a positive control "
    "confirming the scanner finds a token that WAS delivered.",
    ["unit: partition definition to delivered-context mapping",
     "detector control: scanner proven to find a known-present token before its silence is trusted",
     "negative control: disable redaction and assert the scan FIRES"],
    prof="council-integrity-module")

add("7A", "Duplicate-participant detector",
    "Implement tools/council/integrity/dupes.py flagging seats whose effective configuration "
    "(vendor, model, system prompt, tools, context) makes them one voice. Falsifiable question: does "
    "a council of 8 seats that are 8 copies of one configuration report an effective independence "
    "count of 1?",
    P7A,
    ["IMP-0288"],
    "1) effective-voice count on an all-identical roster; 2) inter-participant output similarity on "
    "the same roster corroborating the config-level verdict.",
    ["unit: effective-voice counting",
     "negative control: a genuinely diverse roster must report >1, so the detector is not "
     "constant-firing"],
    to=1800, prof="council-integrity-module")

# -- roles (2)
add("7A", "Role mandate model: permissions, speaking, vote and veto rights",
    "Implement tools/council/roles/mandate.py as typed role objects carrying tool access, source "
    "access, speaking rights, vote rights and veto rights. Falsifiable question: is every right "
    "checked at the point of use rather than merely declared at seat time?",
    P7A + [A_P7A],
    ["IMP-0287"],
    "1) a point-of-use audit listing each right and the call site that enforces it; 2) an attempt "
    "to exercise each right without it, expecting refusal events.",
    ["unit: rights matrix, each right exercised with and without the grant",
     "negative control: remove one enforcement call and assert the audit reports it unenforced"],
    to=1800, prof="council-roles-module")

add("7A", "Runtime role-enforcement guard",
    "Implement tools/council/roles/guard.py rejecting any turn whose content exceeds the "
    "participant's mandate (a critic proposing, a non-voter voting) and recording the rejection. "
    "Falsifiable question: does the guard distinguish a genuine mandate breach from a participant "
    "merely MENTIONING another role's action (the use-vs-mention defect class)?",
    P7A,
    ["IMP-0300"],
    "1) a labelled corpus of 40 turns (breach vs mention) with precision and recall reported "
    "separately; 2) a second pass classifying by structured action field rather than prose.",
    ["unit: breach detection on the labelled corpus",
     "use-vs-mention control: quoted text describing a vote must NOT be classified as a vote",
     "negative control: an actual breach must FIRE"],
    prof="council-roles-module",
    fc=["detector-failure", "overclaim", "schema-invalid", "dependency-blocked"])

# -- topologies (8)
add("7A", "Chair-led topology with rotation and moderator-capture guard",
    "Implement tools/council/topology/chair.py giving the chair agenda and recognition powers, with "
    "rotation and a guard against moderator capture. Falsifiable question: can a chair suppress a "
    "dissenting participant entirely, and does the guard detect a chair whose recognitions are "
    "systematically skewed?",
    P7A + [A_CPROD],
    ["IMP-0287", "IMP-0300"],
    "1) a recognition-distribution statistic per participant across rounds; 2) an independent check "
    "that every participant's submissions appear in the artifact even when not recognised.",
    ["unit: rotation order and chair powers",
     "control (spec 11240 moderator-capture class): a skewed chair must be flagged",
     "negative control: an even chair must NOT be flagged"],
    prof="council-topology-module")

add("7A", "Proposer-critic-judge pipeline topology",
    "Implement tools/council/topology/pcj.py with three staged roles and typed handoff artifacts "
    "(proposal, critique, ruling). Falsifiable question: does the judge ever see the proposer's "
    "identity or reasoning that the critique did not surface, and can a judge rule without citing "
    "at least one critique point?",
    P7A,
    ["IMP-0287", "IMP-0300"],
    "1) a context census of what the judge received; 2) a citation check on the ruling requiring "
    "resolvable critique-point ids.",
    ["unit: staged artifact typing and handoff",
     "negative control: a ruling with fabricated critique ids must FAIL the citation check"],
    to=1800, prof="council-topology-module")

add("7A", "Red team / blue team topology",
    "Implement tools/council/topology/redblue.py with two opposed teams, private intra-team channels "
    "and a scored exchange. Falsifiable question: does the private channel actually stay private - "
    "does any blue-team token appear in a red-team prompt?",
    P7A,
    ["IMP-0287", "IMP-0297"],
    "1) a cross-team token scan over delivered prompts, required zero; 2) the same scanner proven to "
    "find an intentionally shared token.",
    ["unit: team assignment and scoring",
     "detector control: scanner validated on a known-shared token",
     "negative control: leak one token deliberately and assert the scan FIRES"],
    to=1800, prof="council-topology-module")

add("7A", "Jury topology with jurors, judge and a typed verdict form",
    "Implement tools/council/topology/jury.py where jurors deliberate under an evidence standard and "
    "return a structured verdict. Falsifiable question: can a jury return a verdict that no juror's "
    "recorded reasoning supports, and is a hung jury representable rather than forced to a decision?",
    P7A + [C_PROTO],
    ["IMP-0287", "IMP-0328"],
    "1) a verdict-to-reasoning support check listing unsupported verdicts; 2) a hung-jury fixture "
    "producing the NO-DECISION outcome kind.",
    ["unit: verdict form validation",
     "integration: hung jury yields NO-DECISION, not a coerced majority",
     "negative control: an unsupported verdict must FAIL the support check"],
    to=1800, prof="council-topology-module")

add("7A", "Delphi topology with anonymous iterative rounds and statistical feedback",
    "Implement tools/council/topology/delphi.py feeding back anonymised distributional summaries "
    "between rounds. Falsifiable question: does the feedback cause genuine belief revision or only "
    "anchoring - do round-2 estimates converge toward the round-1 median regardless of evidence?",
    P7A,
    ["IMP-0287", "IMP-0296"],
    "1) round-over-round dispersion measured on a question with a KNOWN answer, checking convergence "
    "toward truth not merely toward the median; 2) a planted-wrong-median control run.",
    ["experiment: convergence measured against ground truth on 10 known-answer questions",
     "negative control: planted wrong median must NOT drag the panel if evidence gating works, and "
     "if it does, report it as an anchoring finding rather than suppressing it"],
    prof="council-topology-module")

add("7A", "Pairwise tournament topology",
    "Implement tools/council/topology/tournament.py scheduling pairwise comparisons (Swiss or "
    "round-robin) and aggregating into a ranking. Falsifiable question: is the resulting ranking "
    "order-independent - does shuffling the pairing schedule change the winner?",
    P7A,
    ["IMP-0287", "IMP-0326"],
    "1) 20 shuffled schedules over the same judgements with the winner recorded each time; 2) a "
    "Condorcet-cycle detector reporting when no stable winner exists.",
    ["property: order independence across 20 shuffles",
     "negative control: a constructed Condorcet cycle must be REPORTED, not silently broken"],
    prof="council-topology-module")

add("7A", "Nested subcouncil spawn and fan-in",
    "Implement tools/council/topology/nested.py so a council can spawn a subcouncil for a bounded "
    "question and fold its result back. Falsifiable question: when parent and child disagree on "
    "completion, which one wins, and is that resolution explicit rather than incidental?",
    P7A + [A_FAIL],
    ["IMP-0287", "IMP-0263"],
    "1) a disagreement fixture whose resolution is recorded with the deciding rule id; 2) the shared "
    "completion reducer invoked at the child boundary, verified by call graph.",
    ["integration: 2-level nesting with a deliberate completion disagreement",
     "negative control (spec 11343 nested-disagreement class): remove the resolution rule and "
     "assert the fixture becomes nondeterministic"],
    prof="council-topology-module")

add("7A", "Council-of-councils meta aggregation",
    "Implement tools/council/topology/meta.py aggregating several independent councils' outputs, "
    "preserving each council's dissent rather than averaging it away. Falsifiable question: after "
    "meta-aggregation, is every constituent council's minority report still reachable from the final "
    "artifact by id?",
    P7A + [A_CPROD],
    ["IMP-0311", "IMP-0328"],
    "1) a reachability check from the meta artifact to every constituent minority report id; 2) a "
    "count comparison of dissents in versus dissents out.",
    ["integration: 3 councils aggregated, all dissents reachable",
     "negative control (spec 11342 dissent-loss class): drop one minority report and assert the "
     "reachability check FAILS"],
    prof="council-topology-module",
    fc=["dissent-loss", "overclaim", "detector-failure", "dependency-blocked"])

# -- protocols needing real runtime machinery (8)
add("7A", "Blind independent first pass with a submission barrier",
    "Implement tools/council/protocol/blind_first.py so no participant sees another's position until "
    "all have submitted. Falsifiable question: is there any ordering, retry or streaming path by "
    "which an early submitter's text reaches a later participant before the barrier opens?",
    P7A + [A_P7A],
    ["IMP-0287", "IMP-0297"],
    "1) a delivered-prompt scan for peer content before the barrier timestamp, required zero; 2) an "
    "event-order audit comparing submission and delivery timestamps.",
    ["unit: barrier semantics under a slow participant and a timeout",
     "negative control: open the barrier early and assert the prompt scan FIRES"],
    prof="council-protocol-module")

add("7A", "Brainstorming engine with a structured idea ledger",
    "Implement tools/council/protocol/brainstorm.py maintaining an append-only idea ledger with "
    "author, round, and canonical-mechanism fields, supporting the 100-unique-idea target. "
    "Falsifiable question: does the ledger's unique count reflect distinct MECHANISMS or merely "
    "distinct strings?",
    P7A + [SPEC + ":10937", A_CPROD],
    ["IMP-0287", "IMP-0319"],
    "1) the unique count computed two ways (string-distinct and mechanism-distinct) reported side by "
    "side; 2) a hand-labelled sample of 40 ideas scoring the mechanism grouping.",
    ["unit: ledger append and canonicalisation",
     "control (spec 11339 count-gaming class): 100 trivial wording variants must NOT satisfy a "
     "100-unique target"],
    prof="council-protocol-module",
    fc=["count-gaming", "overclaim", "detector-failure", "dependency-blocked"])

add("7A", "Socratic cross-examination with enforced response obligations",
    "Implement tools/council/protocol/socratic.py so a directed question creates a tracked obligation "
    "the addressee must discharge within N turns. Falsifiable question: can a participant discharge "
    "an obligation with a non-answer, and does the tracker detect evasion rather than counting any "
    "reply as a response?",
    P7A + [A_P2C],
    ["IMP-0287", "IMP-0300"],
    "1) an obligation ledger with open/discharged states and per-turn ages; 2) a labelled evasion "
    "corpus with the discrimination rate reported.",
    ["unit: obligation lifecycle including expiry and escalation",
     "negative control: a non-answer must remain OPEN, proving the tracker is not counting bytes"],
    prof="council-protocol-module")

add("7A", "Steelman-before-rebuttal gate",
    "Implement tools/council/protocol/steelman.py rejecting a rebuttal that is not preceded by an "
    "accepted steelman of the opposing position, where acceptance is judged by the ORIGINAL author. "
    "Falsifiable question: does author-acceptance prevent strawmanning, and what happens when the "
    "author refuses to accept any steelman (a denial-of-service on the gate)?",
    P7A + [A_P7A],
    ["IMP-0287", "IMP-0300"],
    "1) a gate-rejection log with the steelman text and the author's verdict; 2) a DoS fixture where "
    "an author refuses 3 times, checking the documented escalation fires.",
    ["unit: gate accept/reject paths",
     "adversarial: perpetual-refusal DoS must escalate, not deadlock",
     "negative control: remove the gate and assert a strawman rebuttal passes, proving sensitivity"],
    prof="council-protocol-module")

add("7A", "Scenario and war-game protocol with branch forking",
    "Implement tools/council/protocol/scenario.py forking council state into parallel scenario "
    "branches and rejoining with per-branch conclusions. Falsifiable question: is each branch "
    "genuinely independent, or does shared mutable state let branch A's conclusion contaminate "
    "branch B?",
    P7A,
    ["IMP-0287", "IMP-0334"],
    "1) a state-isolation test mutating branch A and asserting branch B's snapshot hash is "
    "unchanged; 2) a cross-branch token scan of delivered prompts.",
    ["unit: fork, mutate, rejoin over 4 branches",
     "negative control: share one mutable object and assert the isolation test FAILS"],
    prof="council-protocol-module")

add("7A", "Prediction and confidence-betting ledger",
    "Implement tools/council/protocol/betting.py letting participants stake confidence on resolvable "
    "propositions, with payoff resolution feeding the calibration store. Falsifiable question: does a "
    "participant that always states 0.5 profit relative to one that commits and is right?",
    P7A + [A_P2C],
    ["IMP-0287", "IMP-0352"],
    "1) a scoring-rule unit test proving the rule is strictly proper (hedging loses); 2) a simulated "
    "tournament of hedger vs committer vs random with final scores reported.",
    ["unit: strictly-proper scoring rule verification",
     "simulation: hedger must not win against a well-calibrated committer",
     "negative control: substitute a non-proper rule and assert the hedger wins, proving the test "
     "discriminates"],
    to=1800, prof="council-protocol-module")

add("7A", "Negotiation and mediation protocol",
    "Implement tools/council/protocol/negotiate.py supporting proposal, counter-proposal, concession "
    "tracking and an optional neutral mediator with no vote. Falsifiable question: does the mediator "
    "role remain neutral - can it be shown to shift outcomes toward its own prior across matched "
    "runs?",
    P7A + [A_CPROD],
    ["IMP-0287", "IMP-0300"],
    "1) a concession ledger per party; 2) a matched-pair experiment with and without the mediator "
    "measuring outcome shift relative to the mediator's declared prior.",
    ["unit: proposal/counter/concession state machine",
     "experiment: mediator-neutrality shift measured over 10 matched runs",
     "negative control: a deliberately biased mediator must show a detectable shift"],
    prof="council-protocol-module")

add("7A", "Protocol-as-data plugin interface",
    "Implement tools/council/protocol/plugin.py so a new deliberation protocol can be added as a "
    "declarative record (phases, obligations, gates) without touching kernel code. Falsifiable "
    "question: can all 58 protocols in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json be expressed through "
    "this interface, and exactly which ones cannot - naming them rather than claiming full coverage?",
    P7A + [C_PROTO],
    ["IMP-0287", "IMP-0284"],
    "1) an expressibility census over all 58 protocols with the inexpressible ones listed by id and "
    "reason; 2) execution of at least 12 expressed protocols end to end.",
    ["census: 58 protocols classified expressible / needs-kernel-change, list published",
     "integration: 12 data-only protocols execute",
     "negative control: a protocol requiring a new kernel primitive must be classified as such, not "
     "silently degraded"],
    to=5400, prof="council-protocol-module")

# -- budgets and quotas (4)
add("7A", "Budget governor for effort, tokens, tool calls, turns, time and experiments",
    "Implement tools/council/budget/governor.py enforcing every budget dimension in the CouncilSpec "
    "budgets section with a declared behaviour on exhaustion. Falsifiable question: when a budget is "
    "exhausted mid-turn, does the council produce a truncated-but-labelled result or an unlabelled "
    "partial that reads as complete?",
    P7A + [A_P2C],
    ["IMP-0287", "IMP-0284"],
    "1) an exhaustion fixture per dimension with the resulting artifact carrying a BUDGET_EXHAUSTED "
    "marker; 2) an independent token count from the transport layer compared to the governor's.",
    ["unit: each budget dimension exhausted individually",
     "negative control: remove the marker and assert a partial result is indistinguishable from a "
     "complete one, proving the marker is load-bearing"],
    prof="council-budget-module")

add("7A", "Speaking quota, minimum engagement and maximum inactivity enforcement",
    "Implement tools/council/budget/engagement.py enforcing per-participant floors and ceilings on "
    "participation. Falsifiable question: does a participant that posts three empty acknowledgements "
    "satisfy a minimum-engagement floor?",
    P7A + [A_P7A],
    ["IMP-0287", "IMP-0322"],
    "1) an engagement metric computed on substantive content units, not message count; 2) a "
    "hand-labelled sample confirming the metric separates substantive from filler turns.",
    ["unit: floor/ceiling enforcement and eviction handoff",
     "negative control: filler-only participation must FAIL the floor"],
    to=1800, prof="council-budget-module")

add("7A", "Unique-idea counter with semantic deduplication",
    "Implement tools/council/quota/unique_ideas.py counting ideas by canonical mechanism using two "
    "mechanically different similarity signals. Falsifiable question: on a planted set containing "
    "exact duplicates, paraphrases and one-parameter forks, what is the per-class recall, and does "
    "the counter ever merge two genuinely distinct ideas?",
    P7A + [SPEC + ":11236"],
    ["IMP-0313"],
    "1) per-class recall against a hand-labelled key, reported per class not pooled; 2) a "
    "false-merge rate on a distinct-pairs control set.",
    ["control: 3 planted duplicate classes, recall per class",
     "control: distinct-pairs set, false-merge rate reported",
     "negative control: a pure string-equality counter must score worse, proving the semantic layer "
     "contributes"],
    to=2700, sub="cloud-batch", prof="council-quota-module",
    fc=["count-gaming", "detector-failure", "overclaim", "dependency-blocked"])

add("7A", "Target evaluator for novelty, diversity, category, coverage, objection and evidence quotas",
    "Implement tools/council/quota/targets.py evaluating every non-count target the CouncilSpec can "
    "declare and reporting per-target attainment. Falsifiable question: can a council satisfy a "
    "coverage target while leaving an entire declared category empty - i.e. is coverage measured per "
    "category or in aggregate?",
    P7A + [A_P7A],
    ["IMP-0319"],
    "1) a per-category attainment table with empties listed explicitly; 2) an aggregate-vs-per-"
    "category comparison demonstrating the two can disagree.",
    ["unit: each target type on a fixture with a known answer",
     "negative control: an empty category must prevent a coverage PASS"],
    to=1800, prof="council-quota-module")

# -- decision and aggregation (6)
add("7A", "Majority, supermajority, unanimity, quorum and abstention tally engine",
    "Implement tools/council/vote/tally.py with explicit quorum and abstention semantics. "
    "Falsifiable question: does an abstention count toward the denominator, and is that choice "
    "configurable and recorded rather than implicit in the arithmetic?",
    P7A + [A_P7A],
    ["IMP-0287"],
    "1) a tally matrix over abstention policies with hand-computed expected values; 2) the recorded "
    "policy id present in every decision artifact.",
    ["unit: 24-case tally matrix (threshold x abstention policy x quorum)",
     "negative control: change the abstention policy and assert at least one recorded outcome flips"],
    to=1800, prof="council-vote-module")

add("7A", "Ordinal and cardinal ballot engine: ranked-choice, Condorcet, score and approval",
    "Implement tools/council/vote/ballots.py covering ranked-choice, pairwise/Condorcet, score and "
    "approval with a shared ballot type. Falsifiable question: on the same ballots, do the four "
    "methods ever elect different winners, and is that divergence surfaced to the owner instead of "
    "hidden behind a default method?",
    P7A,
    ["IMP-0324"],
    "1) a divergence report across all four methods on every recorded ballot set; 2) textbook "
    "fixtures with known winners verifying each method independently.",
    ["unit: each method against a published worked example",
     "invariant: method divergence is reported, never silently resolved",
     "negative control: a constructed Condorcet cycle must be reported as such"],
    prof="council-vote-module")

add("7A", "Weighted voting and vote delegation",
    "Implement tools/council/vote/weights.py supporting authority-based weights and liquid "
    "delegation with cycle detection. Falsifiable question: can a delegation cycle silently "
    "disenfranchise a bloc, and does total voting power stay conserved after delegation?",
    P7A,
    ["IMP-0324"],
    "1) a conservation check total_power_before == total_power_after on 100 random delegation "
    "graphs; 2) an explicit cycle report on constructed cyclic graphs.",
    ["property: power conservation over 100 random graphs",
     "unit: cycle detection and resolution policy",
     "negative control: break conservation deliberately and assert the property test FAILS"],
    to=1800, prof="council-vote-module")

add("7A", "Bayesian belief aggregation and confidence pooling",
    "Implement tools/council/vote/bayes.py pooling participant credences with declared "
    "independence assumptions. Falsifiable question: when participants are correlated (same vendor, "
    "same context), does naive pooling manufacture overconfidence, and does the implementation "
    "discount for the measured correlation?",
    P7A + [A_CPROD],
    ["IMP-0295", "IMP-0324"],
    "1) pooled credence computed with and without the correlation discount on the same inputs; 2) a "
    "simulation with known ground truth reporting calibration error for both.",
    ["simulation: calibration error under correlated vs independent panels",
     "negative control: a fully-correlated panel must NOT yield a near-certain pooled credence"],
    prof="council-vote-module",
    fc=["overclaim", "detector-failure", "stale-premise", "dependency-blocked"])

add("7A", "Veto, consent and no-objection decision modes",
    "Implement tools/council/vote/consent.py supporting veto rights and consent (no-objection) "
    "decisions with a recorded objection window. Falsifiable question: is silence within the window "
    "treated as consent, and is that policy explicit in the artifact rather than an implementation "
    "detail?",
    P7A,
    ["IMP-0300", "IMP-0324"],
    "1) a decision artifact containing the objection window, the silence policy and per-participant "
    "response state; 2) a late-objection fixture confirming the documented handling.",
    ["unit: veto, consent, late objection and window expiry",
     "negative control: an unrecorded silence policy must FAIL artifact validation"],
    to=1800, prof="council-vote-module")

add("7A", "Evidence gate overriding popularity",
    "Implement tools/council/vote/evidence_gate.py so a majority with no evidence anchors cannot "
    "produce a binding decision (spec 11198: agreement is not proof). Falsifiable question: does the "
    "gate distinguish a real evidence anchor from a plausible-looking citation that does not resolve?",
    P7A + [SPEC + ":11198", A_CPROD],
    ["IMP-0324", "IMP-0333"],
    "1) an anchor-resolution pass that fetches or stats every cited anchor, listing unresolved ones; "
    "2) a fabricated-citation fixture that must be caught.",
    ["unit: evidence-free majority is blocked",
     "control (spec 11235 vote-without-evidence class): fabricated anchors must not satisfy the gate",
     "negative control: a well-anchored minority position must NOT be blocked"],
    prof="council-vote-module",
    fc=["overclaim", "detector-failure", "injection", "dependency-blocked"])

# -- stopping and outcomes (5)
add("7A", "Boolean stopping-expression parser and evaluator",
    "Implement tools/council/stopping/expr.py parsing and evaluating composable AND/OR/NOT and "
    "weighted stopping expressions, including the six executable examples at spec 10937-10942. "
    "Falsifiable question: does every one of those six expressions parse, bind to a real runtime "
    "metric, and evaluate to a value that changes during a run?",
    P7A + [SPEC + ":10937-10942"],
    ["IMP-0287", "IMP-0320"],
    "1) all six spec examples parsed, with each bound metric printed per round; 2) a metric-binding "
    "census listing any referenced metric with no runtime producer.",
    ["unit: parser grammar including precedence and negation",
     "integration: all 6 spec expressions evaluated over a live run",
     "negative control: an expression referencing an unproduced metric must FAIL at bind time, not "
     "silently evaluate false forever"],
    prof="council-stopping-module")

add("7A", "Minimum-deliberation-condition gate",
    "Implement tools/council/stopping/minimum.py preventing a stop before declared minimums (rounds, "
    "independent briefs, objections considered) are met. Falsifiable question: can a council that "
    "reaches instant consensus stop before any independent brief exists?",
    P7A + [A_P7A],
    ["IMP-0329", "IMP-0345"],
    "1) an instant-consensus fixture that must NOT stop early; 2) the gate's own condition table "
    "printed with each condition's measured value at stop time.",
    ["unit: each minimum condition independently blocks a premature stop",
     "negative control (spec 11338 stop-before-minimum class): disable the gate and assert the "
     "fixture stops early"],
    to=1800, prof="council-stopping-module")

add("7A", "Deadlock detector with escalation and owner intervention",
    "Implement tools/council/stopping/deadlock.py detecting no-progress states and escalating "
    "through replacement, protocol change, or an owner-intervention request. Falsifiable question: "
    "how does the detector distinguish a deadlock from slow but genuine progress, and what is its "
    "false-positive rate on a corpus of slow-converging runs?",
    P7A,
    ["IMP-0329", "IMP-0348"],
    "1) false-positive rate on 20 recorded slow-but-converging runs; 2) true-positive rate on 10 "
    "constructed deadlocks, reported separately.",
    ["control: TPR and FPR reported separately, never a single accuracy figure",
     "negative control: a converging run must not be escalated"],
    prof="council-stopping-module")

add("7A", "Outcome kinds: no-decision, conditional decision and proof-of-impossibility",
    "Implement tools/council/outcomes/kinds.py making NO-DECISION, CONDITIONAL and "
    "PROOF-OF-IMPOSSIBILITY first-class, typed outcomes with required fields. Falsifiable question: "
    "is any of these three ever coerced into a plain decision by a downstream consumer that only "
    "understands PASS/FAIL?",
    P7A + [SPEC + ":10932", SPEC + ":10942"],
    ["IMP-0284", "IMP-0263"],
    "1) a downstream-consumer census listing every reader of the outcome field and how it handles "
    "each kind; 2) a fixture of each kind flowing through the full pipeline to the final artifact.",
    ["unit: required-field validation per outcome kind",
     "integration: each kind survives to the final artifact unmodified",
     "negative control: a consumer that maps NO-DECISION to FAIL must be caught by the census"],
    prof="council-outcomes-module")

add("7A", "Dissent and minority-report preservation pipeline",
    "Implement tools/council/outcomes/dissent.py so every dissent is captured, attributed and "
    "carried into the final artifact and any parent aggregation. Falsifiable question: does the "
    "count of dissents entering synthesis equal the count leaving it, and is a dissent ever "
    "summarised into non-existence?",
    P7A + [A_CPROD],
    ["IMP-0287"],
    "1) a dissent conservation count in vs out at every pipeline stage; 2) a text-presence check "
    "that each dissent's distinctive claim string survives verbatim or by resolvable id.",
    ["unit: dissent capture, attribution and propagation",
     "invariant: conservation across synthesis",
     "negative control (spec 11342): drop one dissent and assert conservation FAILS"],
    prof="council-outcomes-module",
    fc=["dissent-loss", "overclaim", "detector-failure", "dependency-blocked"])

# -- artifacts and audit (5)
add("7A", "Argument graph builder",
    "Implement tools/council/artifacts/argument_graph.py building a typed graph of claims with "
    "SUPPORTS, ATTACKS and REBUTS edges extracted from turns. Falsifiable question: what fraction of "
    "hand-labelled edges does the extractor recover on a 200-turn labelled transcript, and does it "
    "invent edges that no turn supports?",
    P7A + [A_P7A],
    ["IMP-0287"],
    "1) precision and recall against a 200-turn hand-labelled key, reported separately; 2) every "
    "emitted edge carries a turn id that resolves.",
    ["control: labelled-transcript precision/recall",
     "negative control: an invented edge with an unresolvable turn id must FAIL validation"],
    to=2700, prof="council-artifacts-module")

add("7A", "Evidence map, citation graph and circular-citation detector",
    "Implement tools/council/artifacts/evidence_map.py mapping every claim to its anchors and "
    "detecting citation cycles where A cites B citing A. Falsifiable question: does the detector "
    "distinguish a genuine cycle from two documents legitimately cross-referencing distinct facts?",
    P7A + [SPEC + ":11234"],
    ["IMP-0333"],
    "1) cycle reports on constructed cyclic and acyclic fixtures; 2) an anchor-resolution pass "
    "stat-ing every cited file path or URL.",
    ["unit: cycle detection on 6 graph shapes",
     "control (spec 11234 circular-citation class): a real cycle must FIRE",
     "negative control: legitimate cross-references must NOT fire (false-positive rate reported)"],
    prof="council-artifacts-module")

add("7A", "Transcript and event store with resume, replay and confidence trajectory",
    "Implement tools/council/artifacts/store.py as an append-only event store from which the full "
    "transcript, vote history and confidence trajectory are derived views, supporting pause/resume "
    "and deterministic replay. Falsifiable question: can the entire council state be rebuilt from "
    "the event log alone, with no side state, and does replay of the same log reproduce the same "
    "final artifact byte for byte?",
    P7A + [A_P7A, "command-center/events/EVENTS.jsonl"],
    ["IMP-0287"],
    "1) a rebuild-from-log run byte-compared against the original artifact; 2) a side-state audit "
    "listing any module attribute that survives a process restart.",
    ["integration: rebuild from log on 5 recorded councils",
     "negative control: introduce one piece of side state and assert the rebuild diverges"],
    sub="local-serialized", prof="council-artifacts-module")

add("7A", "Council audit and replay CLI",
    "Implement tools/council/cli/audit.py letting an owner replay a council, inspect any round, and "
    "export the decision lineage. Falsifiable question: can the CLI reconstruct WHY a decision was "
    "reached - naming the deciding rule, the tally and the evidence - from the stored artifact "
    "alone, with no live model call?",
    P7A + [A_CPROD],
    ["IMP-0335"],
    "1) an offline run with network disabled producing a complete lineage; 2) a spot check of 3 "
    "decisions against their raw event ranges.",
    ["integration: offline replay with egress blocked",
     "negative control: remove the deciding-rule id from the artifact and assert the CLI reports "
     "UNKNOWN rather than guessing"],
    to=1800, sub="local-serialized", prof="council-cli-surface")

add("7A", "Privacy, retention and persistence policy engine",
    "Implement tools/council/artifacts/retention.py applying declared retention, redaction and "
    "persistence rules to transcripts, including a hard rule that no credential or decrypted secret "
    "enters a council artifact. Falsifiable question: does a secret pasted into a participant turn "
    "reach the persisted artifact, and does the redactor handle JSON-embedded and camelCase key "
    "forms as well as plain assignments?",
    P7A + [A_FAIL, SPEC + ":11345"],
    ["IMP-0335"],
    "1) a planted-secret corpus (env-style, JSON-embedded, camelCase, base64) scanned in the "
    "persisted artifact, required zero survivors; 2) an independent gitleaks-style scan of the same "
    "artifact directory.",
    ["security: planted-secret corpus across 4 encodings",
     "negative control: disable the redactor and assert all 4 forms are found, proving the scanner "
     "is not silently passing"],
    rev=REV_OWNER, oa=True, sub="local-serialized", prof="council-privacy-module",
    fc=["secret-exposure", "detector-failure", "owner-blocked", "overclaim"])

# -- anti-failure controls (7)
add("7A", "Instant-unanimity trigger with blind re-evaluation and forced dissent",
    "Implement tools/council/antifail/unanimity.py so suspiciously fast unanimity triggers blind "
    "re-evaluation, forced dissent, strongest-counterexample generation, role rotation or recruitment "
    "of an independent critic. Falsifiable question: after the trigger fires, does the second pass "
    "ever change the outcome, or is it theatre that always confirms the first result?",
    P7A + [SPEC + ":10944"],
    ["IMP-0287", "IMP-0293"],
    "1) outcome-change rate across 20 triggered runs, reported as a number; 2) a planted-wrong-"
    "consensus fixture the second pass must overturn.",
    ["control: planted wrong consensus must be overturned",
     "measurement: outcome-change rate published, not assumed",
     "negative control: a genuinely correct consensus must survive re-evaluation"],
    prof="council-antifail-module")

add("7A", "Sycophancy detector for chair and owner alignment drift",
    "Implement tools/council/antifail/sycophancy.py measuring whether participant positions shift "
    "toward the chair's or owner's stated view without new evidence. Falsifiable question: does the "
    "detector separate legitimate persuasion (position change WITH new evidence cited) from "
    "sycophancy (position change with none)?",
    P7A + [SPEC + ":11232"],
    ["IMP-0333", "IMP-0287"],
    "1) a labelled corpus of 60 position changes with precision/recall reported; 2) an A/B run where "
    "the chair states the opposite view, measuring the flip rate.",
    ["control: chair-flip experiment, flip rate measured",
     "negative control: evidence-backed position change must NOT be flagged"],
    prof="council-antifail-module")

add("7A", "Role-collapse detector",
    "Implement tools/council/antifail/role_collapse.py measuring inter-participant output similarity "
    "and role-specific vocabulary to detect every participant behaving the same. Falsifiable "
    "question: does the detector fire on a council where all seats are the same model with different "
    "role prompts, and stay silent on a genuinely diverse one?",
    P7A + [SPEC + ":11230"],
    ["IMP-0299", "IMP-0287"],
    "1) similarity distributions for a collapsed and a diverse council plotted side by side; 2) a "
    "role-vocabulary presence check per seat.",
    ["control: collapsed council must FIRE, diverse council must not",
     "negative control: a single-model council with strong role prompts is the hard case - report "
     "its classification honestly rather than tuning until it passes"],
    prof="council-antifail-module")

add("7A", "Dominance and silence detector",
    "Implement tools/council/antifail/participation.py detecting a participant monopolising turns or "
    "a participant effectively silent. Falsifiable question: is dominance measured by substantive "
    "contribution or by token volume, and do those two measures disagree on any recorded run?",
    P7A + [SPEC + ":11238"],
    ["IMP-0322"],
    "1) both measures computed over 20 recorded councils with disagreements listed; 2) a manual read "
    "of the top disagreement confirming which measure was right.",
    ["unit: dominance and silence thresholds",
     "measurement: volume-vs-substance disagreement count published",
     "negative control: an even council must not be flagged"],
    to=1800, prof="council-antifail-module")

add("7A", "Circular-debate and no-information-gain detector",
    "Implement tools/council/antifail/no_gain.py measuring new-claim and new-evidence rate per round "
    "to detect debate that never converges. Falsifiable question: can the detector tell repetition "
    "from careful refinement of the same claim, and what does it do with a round that adds evidence "
    "but no new claims?",
    P7A + [SPEC + ":11236"],
    ["IMP-0333", "IMP-0329"],
    "1) per-round new-claim and new-evidence counts on 15 recorded councils; 2) a labelled "
    "repetition-vs-refinement sample with the discrimination rate reported.",
    ["control: constructed looping council must FIRE",
     "negative control: a refining council must NOT fire"],
    prof="council-antifail-module")

add("7A", "Premature-convergence detector",
    "Implement tools/council/antifail/premature.py detecting convergence before the declared "
    "divergence phase has met its idea and objection quotas. Falsifiable question: does it "
    "distinguish premature convergence from a genuinely easy question, and is the distinction made "
    "on quota attainment rather than on round count?",
    P7A + [SPEC + ":11236"],
    ["IMP-0320", "IMP-0330"],
    "1) quota-attainment values at convergence time for 20 runs; 2) an easy-question control set "
    "where early convergence is correct and must not be flagged.",
    ["control: easy-question set must not be flagged (FPR reported)",
     "negative control: a hard question converging in round 1 must FIRE"],
    to=1800, prof="council-antifail-module")

add("7A", "Prompt-injection and collusion defense on participant artifacts",
    "Implement tools/council/antifail/injection.py treating every participant turn, transcript and "
    "fetched source as untrusted DATA and detecting coordinated collusion signatures. Falsifiable "
    "question: can text inside a participant's turn cause a later stage to change its instructions, "
    "and does the defense survive base64, unicode-confusable and split-token encodings?",
    P7A + [SPEC + ":11344", A_FAIL],
    ["IMP-0287", "IMP-0335"],
    "1) an injection corpus of 30 payloads across 5 encodings with the block rate per encoding; 2) a "
    "downstream behaviour probe confirming no instruction change occurred, independent of the "
    "detector's own verdict.",
    ["security: 30-payload injection corpus, block rate per encoding",
     "control (spec 11344): a transcript-borne instruction must not alter a later stage",
     "negative control: disable the defense and assert the behaviour probe detects the change"],
    rev=REV_SEC, prof="council-antifail-module",
    fc=["injection", "detector-failure", "overclaim", "secret-exposure"])

# -- surfaces (5)
add("7A", "Council CLI",
    "Implement tools/council/cli/main.py exposing run, resume, inspect, list-presets and explain "
    "subcommands with typed exit codes. Falsifiable question: does every subcommand return a "
    "distinct, documented exit code, and does a failed council ever exit 0?",
    P7A + [A_PRED],
    ["IMP-0287", "IMP-0284"],
    "1) an exit-code matrix exercised by a shell harness; 2) a failed-council fixture checked for "
    "non-zero exit AND an absent success sentinel.",
    ["unit: exit-code matrix across all subcommands",
     "negative control (spec 11312 exit-zero-with-missing-artifact class): a run that writes no "
     "artifact must not exit 0"],
    to=1800, sub="local-serialized", tools=T_WP, prof="council-cli-surface")

add("7A", "Council SDK",
    "Implement tools/council/sdk.py so a CouncilSpec can be built, executed and inspected "
    "programmatically from another workflow, returning typed results rather than text. Falsifiable "
    "question: is every artifact reachable through the SDK also reachable through the CLI, and vice "
    "versa - or do the two surfaces expose different truths?",
    P7A,
    ["IMP-0284", "IMP-0287"],
    "1) a surface-parity set-difference between SDK-reachable and CLI-reachable artifact keys, both "
    "directions printed; 2) an end-to-end SDK-driven council.",
    ["unit: typed result objects, no stringly-typed returns",
     "parity: SDK vs CLI reachable-key sets equal",
     "negative control: hide one artifact from the CLI and assert parity FAILS"],
    prof="council-sdk-module")

add("7A", "Structured council builder",
    "Implement tools/council/builder/ as a guided structured builder that composes a CouncilSpec "
    "from typed questions and can express the five owner goal phrasings at spec 11198. Falsifiable "
    "question: can each of those five natural-language goals be produced by the builder, and does "
    "the resulting spec's stopping expression actually encode the stated goal?",
    P7A + [SPEC + ":11198"],
    ["IMP-0344", "IMP-0329"],
    "1) all five goals built and their stopping expressions printed for inspection; 2) each built "
    "spec executed against a fixture, confirming it stops for the stated reason.",
    ["integration: 5 owner goal phrasings round-tripped",
     "negative control: a goal whose stopping metric does not exist must be refused at build time"],
    prof="council-builder-surface")

add("7A", "Preset store, loader and editing round-trip",
    "Implement tools/council/presets/store.py loading the 72 measured presets, exposing editable "
    "dials, and writing edits back without losing unedited fields. Falsifiable question: after "
    "loading, editing one dial and saving, is any other field changed, reordered or dropped?",
    P7A + [C_PROTO],
    ["IMP-0284"],
    "1) a field-level diff of before and after for all 72 presets with only the edited key differing; "
    "2) a canonical-hash comparison of untouched presets.",
    ["unit: load/edit/save round trip on all 72 presets",
     "negative control: reorder keys on save and assert the diff check FAILS"],
    to=1800, prof="council-presets-module")

add("7A", "Post-run calibration report generator",
    "Implement tools/council/calibration/report.py scoring resolved predictions per participant and "
    "writing the calibration store consumed by IMP-0291 and IMP-0318. Falsifiable question: with "
    "fewer than 10 resolved predictions, does the report state that the calibration estimate is not "
    "yet meaningful rather than printing a confident number?",
    P7A + [A_P7A, A_CPROD],
    ["IMP-0339"],
    "1) a small-sample run whose output carries an explicit insufficient-data marker; 2) a "
    "large-sample run whose Brier score matches an independently computed value.",
    ["unit: scoring against a hand-computed fixture",
     "negative control: n<10 must not emit a bare confident score"],
    to=1800, prof="council-calibration-artifact")

# ============================================================================
# PHASE 8 - skill and capability routing (16 units, IMP-0353..IMP-0368)
# ============================================================================
P8 = [A_P8, A_FAIL]

add("8", "Global capability index builder",
    "Implement tools/router/index.py enumerating every skill, plugin, workflow, command and MCP tool "
    "across both the repo and the live trees into one index with source-of-truth tags. Falsifiable "
    "question: does the index count match an independent filesystem enumeration, and does it "
    "distinguish repo-only, live-only and both?",
    P8 + [D_PARITY, "rules/"],
    ["B06"],
    "1) index counts vs an independent PowerShell Get-ChildItem census, compared per category; 2) a "
    "three-way set report repo-only / live-only / both with the disagreements listed.",
    ["unit: index schema and tagging",
     "detector control: a known-present skill must be found before any absence is reported",
     "negative control: hide one skill and assert the census disagreement FIRES"],
    sub="local-serialized", tools=T_WP, prof="router-index-artifact")

add("8", "Routing-oriented description improver with measured effect",
    "Implement tools/router/describe.py which rewrites capability descriptions for routing and "
    "MEASURES the retrieval effect of each rewrite. Falsifiable question: does a rewritten "
    "description actually improve top-k recall on a held-out query set, or does it only look better "
    "to a reader?",
    P8,
    ["IMP-0353", "IMP-0364"],
    "1) before/after top-k recall on a held-out query set, per capability; 2) a rewrite that "
    "measurably HURTS must be reverted automatically, with the revert logged.",
    ["experiment: paired before/after recall, per-capability deltas published",
     "negative control: a deliberately vague rewrite must show a recall drop"],
    prof="router-quality-module")

add("8", "Rule-based capability matcher",
    "Implement tools/router/match_rules.py matching explicit trigger phrases, file globs and cwd "
    "scopes declared by each capability. Falsifiable question: when two capabilities declare "
    "overlapping triggers, does the rule matcher return both with their specificity, or silently "
    "pick one?",
    P8,
    ["IMP-0353"],
    "1) an overlap report over the full index listing every colliding trigger pair; 2) a specificity "
    "ordering test with hand-computed expected ranks.",
    ["unit: glob, phrase and scope matching",
     "negative control: a collision must be reported, not resolved by dictionary order"],
    to=1800, sub="local-parallel", prof="router-match-module")

add("8", "Semantic capability matcher",
    "Implement tools/router/match_semantic.py embedding queries and capability descriptions for "
    "similarity retrieval. Falsifiable question: on a labelled query-to-capability key, what are "
    "precision@1 and recall@5, and how do they compare with the rule matcher on the SAME key?",
    P8,
    ["IMP-0353"],
    "1) precision@1 and recall@5 on a labelled key of at least 120 queries; 2) the same key scored by "
    "the rule matcher, reported side by side rather than pooled.",
    ["control: labelled 120-query key, both matchers scored",
     "negative control: a query with no correct capability must return low scores, not a confident "
     "wrong pick"],
    to=3600, sub="cloud-batch", prof="router-match-module")

add("8", "Hybrid scorer with confidence-weighted top-k injection",
    "Implement tools/router/score.py fusing rule and semantic signals into a calibrated confidence "
    "and injecting only the top-k above a threshold. Falsifiable question: is the emitted confidence "
    "calibrated - among selections reported at 0.8, do about 80 percent turn out correct?",
    P8,
    ["IMP-0355", "IMP-0356"],
    "1) a reliability diagram over the labelled key with bin counts printed; 2) an ablation showing "
    "each signal's marginal contribution.",
    ["calibration: reliability diagram, bin counts published",
     "ablation: rule-only, semantic-only and hybrid compared",
     "negative control: a miscalibrated scorer must be visibly off-diagonal"],
    to=2700, prof="router-score-module")

add("8", "Capability conflict resolution",
    "Implement tools/router/conflict.py deciding between capabilities that both claim a query, using "
    "declared specificity, scope depth and an explicit precedence table. Falsifiable question: is "
    "the resolution deterministic and explainable for every colliding pair in the index, or are "
    "there pairs where the outcome depends on enumeration order?",
    P8,
    ["IMP-0355", "IMP-0357"],
    "1) all colliding pairs resolved twice with shuffled input order and compared; 2) an explanation "
    "string for each resolution naming the deciding rule.",
    ["property: order independence over all colliding pairs",
     "negative control: introduce an order-dependent tiebreak and assert the property test FAILS"],
    to=1800, prof="router-score-module")

add("8", "User override channel",
    "Implement tools/router/override.py letting the owner force, suppress or pin a capability per "
    "scope, with overrides outranking every automatic signal. Falsifiable question: can any "
    "automatic signal ever beat an explicit owner override, and are overrides persisted where the "
    "next session will read them?",
    P8,
    ["IMP-0357"],
    "1) an adversarial test where the strongest automatic signal opposes the override; 2) a "
    "cross-session persistence check reading the store from a fresh process.",
    ["unit: force, suppress and pin semantics",
     "negative control: remove the precedence rule and assert the adversarial test FAILS"],
    to=1800, sub="local-serialized", prof="router-policy-module")

add("8", "Selection explanation surface",
    "Implement tools/router/explain.py emitting, for every selection, the matched signals, the "
    "score, the runners-up and the reason each was not chosen. Falsifiable question: does the "
    "explanation reference real signal values from the actual decision, or is it regenerated "
    "post-hoc and therefore capable of disagreeing with the decision?",
    P8,
    ["IMP-0357"],
    "1) explanation values compared field-by-field against the decision record; 2) a mutation "
    "changing the decision path must change the explanation.",
    ["unit: explanation-to-decision field equality",
     "negative control: post-hoc regeneration must be detected by the field comparison"],
    to=1800, prof="router-explain-module")

add("8", "Fallback when no capability fits",
    "Implement tools/router/fallback.py producing an explicit NO-CAPABILITY-FITS result with the "
    "nearest misses and a suggested capability gap record. Falsifiable question: does the router "
    "ever return a low-confidence capability instead of admitting no fit, and is the gap record "
    "actionable enough to become a work unit?",
    P8,
    ["IMP-0357", "IMP-0359"],
    "1) an out-of-domain query set where NO-CAPABILITY-FITS must be returned; 2) the gap records "
    "checked against the work-unit schema.",
    ["control: out-of-domain query set",
     "negative control: lower the threshold and assert the out-of-domain set starts returning "
     "capabilities, proving the threshold is load-bearing"],
    to=1800, prof="router-policy-module")

add("8", "Context-flood guard on capability injection",
    "Implement tools/router/budget.py capping injected capability context by token budget with a "
    "documented eviction order. Falsifiable question: at the cap, which capability is dropped first, "
    "and does the router ever exceed the declared budget by streaming descriptions after the check?",
    P8 + [SPEC + ":10963"],
    ["IMP-0357"],
    "1) measured injected-token count vs the declared cap across 50 queries; 2) an eviction-order "
    "trace compared to the documented order.",
    ["unit: budget arithmetic and eviction order",
     "negative control: inject after the check and assert the measured count exceeds the cap, "
     "proving the measurement is real"],
    to=1800, prof="router-budget-module")

add("8", "Skill-use breadth and task-success measurement",
    "Implement tools/router/metrics.py measuring how much of the repertoire is actually reachable "
    "and whether selected capabilities correlate with task success. Falsifiable question: what "
    "fraction of indexed capabilities has NEVER been selected by the router on the benchmark query "
    "set, and is that because they are unreachable or because no query needed them?",
    P8 + [SPEC + ":10950"],
    ["IMP-0357", "IMP-0356"],
    "1) a never-selected census with each entry classified reachable-but-unneeded vs unreachable; 2) "
    "a targeted query authored for each never-selected capability, testing reachability directly.",
    ["measurement: never-selected census with per-entry classification",
     "control: a hand-authored query for each never-selected capability must reach it, or the "
     "capability is proven unreachable"],
    to=3600, sub="cloud-batch", prof="router-metrics-artifact")

add("8", "Router regression suite harness",
    "Implement tools/router/regress.py running the labelled query key on every change and failing on "
    "recall drop or context-budget growth. Falsifiable question: does the suite catch a real routing "
    "regression - if the semantic index is silently emptied, does it go red?",
    P8 + [SPEC + ":10963", D_NOREG],
    ["IMP-0356", "IMP-0357", "IMP-0362"],
    "1) a mutation run with the semantic index emptied, expected red; 2) a second mutation raising "
    "the injection budget, expected red on a different assertion.",
    ["mutation: empty index must go red",
     "mutation: budget inflation must go red",
     "negative control: an unrelated refactor must stay green, proving the suite is not "
     "constant-firing"],
    to=2700, prof="router-test-harness")

add("8", "Repo-versus-live capability presence reconciler",
    "Implement tools/router/reconcile.py reporting capabilities present in the repo but missing from "
    "the live tree and vice versa, with a two-directional content diff. Falsifiable question: for "
    "each differing capability, which side is newer and does either side hold unique content that a "
    "one-directional sync would destroy?",
    P8 + [D_PARITY, A_FAIL],
    ["IMP-0353"],
    "1) a two-directional diff with repo-larger and live-larger counts reported separately; 2) git "
    "log recency per path compared against live mtime.",
    ["control (spec 11330 repo-vs-live class): a planted live-only capability must be reported",
     "negative control: a byte-identical pair must NOT be reported as drift"],
    sub="local-serialized", tools=T_WP, prof="router-reconcile-artifact",
    fc=["green-not-live", "detector-failure", "overclaim", "dependency-blocked"])

add("8", "Lazy activation and gateway loader",
    "Implement tools/router/lazy.py so a capability's full body loads only when selected, keeping "
    "turn-zero context to the index summary. Falsifiable question: how many tokens does turn zero "
    "cost with lazy loading versus eager, measured rather than estimated, and does any capability "
    "still load eagerly by accident?",
    P8 + [D_ARCH],
    ["IMP-0353", "IMP-0362"],
    "1) measured turn-zero token counts for eager and lazy configurations; 2) a load-event trace "
    "listing every capability body loaded during a turn.",
    ["measurement: eager vs lazy turn-zero token counts",
     "negative control: mark one capability always-on and assert the load trace shows it, proving "
     "the trace can detect eager loads"],
    to=2700, sub="local-serialized", prof="router-loader-module")

add("8", "Capability deprecation, aliasing and anti-prune policy",
    "Implement tools/router/lifecycle.py handling renamed and deprecated capabilities via aliases, "
    "while enforcing the spec rule that rarity alone is never grounds for removal. Falsifiable "
    "question: does an old capability name still resolve after a rename, and is any removal path "
    "reachable without an explicit owner approval record?",
    P8 + [SPEC + ":10950"],
    ["IMP-0353", "IMP-0359"],
    "1) an alias-resolution test over every historical name in the index; 2) a code-path audit "
    "proving removal requires an owner-approval token.",
    ["unit: alias chains including two-hop renames",
     "negative control: attempt a rarity-based prune and assert it is refused"],
    to=1800, oa=True, rev=REV_OWNER, prof="router-lifecycle-module",
    fc=["owner-blocked", "overclaim", "green-not-live", "detector-failure"])

add("8", "Routing telemetry and observability surface",
    "Implement tools/router/telemetry.py recording every selection, its confidence, its outcome and "
    "the owner's overrides, exposed to the cockpit. Falsifiable question: is the telemetry stream "
    "free of prompt content and secrets, and can a stale telemetry writer make the cockpit show a "
    "dead router as healthy?",
    P8 + [A_FAIL],
    ["IMP-0357", "IMP-0362"],
    "1) a secret and prompt-content scan over a full telemetry capture; 2) a liveness test where the "
    "router is killed and the cockpit must report stale within the declared window.",
    ["security: telemetry content scan",
     "control (spec 11315 stale-monitor class): a killed router must be shown as stale, not healthy",
     "negative control: freeze the clock and assert the staleness check FAILS, proving it is "
     "time-sensitive"],
    to=2700, sub="local-serialized", tools=T_WP, prof="router-telemetry-module",
    fc=["secret-exposure", "uncontrolled-silence", "detector-failure", "green-not-live"])

# ============================================================================
# PHASE 9 - multi-session and cross-vendor coordination (12, IMP-0369..IMP-0380)
# ============================================================================
P9 = [A_P9, A_FAIL, A_PRED]

add("9", "Session discovery across vendors",
    "Implement tools/crossvendor/discover.py enumerating live agent sessions (Claude Code, Codex) "
    "with vendor, cwd, start time and liveness. Falsifiable question: how is a LIVE session "
    "distinguished from a crashed one whose files simply stopped changing, given that mtime alone "
    "cannot tell them apart?",
    P9,
    ["B06"],
    "1) process-table CPU delta over a 20s window; 2) byte-growth of the session log over the same "
    "window - both required before declaring LIVE.",
    ["unit: liveness AND-gate of two independent signals",
     "control: a deliberately paused session must be classified UNKNOWN, not DEAD",
     "negative control (mtime-only heuristic): assert a finished session is not reported as stalled"],
    prof="crossvendor-discovery-module",
    fc=["detector-failure", "uncontrolled-silence", "overclaim", "green-not-live"])

add("9", "Work-claim protocol with lease renewal",
    "Implement tools/crossvendor/claim.py so a unit is claimed atomically, renewed on a heartbeat and "
    "released on completion or crash. Falsifiable question: under two agents racing for the same "
    "unit, can both observe a successful claim, and what is the outcome when the winner dies before "
    "its first renewal?",
    P9,
    ["IMP-0369"],
    "1) a 100-iteration race harness counting double-claims, required zero; 2) a crash-before-renewal "
    "fixture where the unit must return to the pool after the lease window.",
    ["concurrency: 100-iteration race, double-claim count published",
     "chaos: claim-then-die, lease expiry reclaims the unit",
     "negative control: remove atomicity and assert the race harness reports double-claims"],
    prof="crossvendor-claim-module")

add("9", "Advisory file-lease manager",
    "Implement tools/crossvendor/leases.py granting per-path advisory leases so two agents do not "
    "edit the same file, integrating with the existing agent-mail reservation surface where "
    "available. Falsifiable question: what happens when an agent ignores the advisory lease - is the "
    "conflict detected after the fact, or lost?",
    P9,
    ["IMP-0370"],
    "1) a post-hoc conflict report generated from file mtimes and lease records; 2) a deliberate "
    "lease violation that the report must catch.",
    ["unit: grant, renew, release and expiry",
     "control: an ignored lease must appear in the post-hoc conflict report",
     "negative control: a compliant edit must NOT appear"],
    to=2700, prof="crossvendor-lease-module")

add("9", "Concurrent-edit conflict detection",
    "Implement tools/crossvendor/conflict.py detecting two-directional divergence between an agent's "
    "intended write and the current file state. Falsifiable question: does the detector catch the "
    "DIVERGED case where BOTH sides hold unique content, which a one-directional check reports as "
    "safe?",
    P9 + [SPEC + ":11320"],
    ["IMP-0371"],
    "1) a labelled fixture set of ahead / behind / diverged / identical with per-class accuracy; 2) "
    "a byte-level differ used as the oracle rather than a judgement call.",
    ["control: 4-class labelled fixture, per-class accuracy reported",
     "negative control: a one-directional check must MISS the diverged class, proving the "
     "two-directional test adds value"],
    prof="crossvendor-conflict-module",
    fc=["detector-failure", "overclaim", "green-not-live", "dependency-blocked"])

add("9", "Duplicate-work suppression",
    "Implement tools/crossvendor/dedupe.py suppressing a second execution of the same unit across "
    "sessions, keyed on unit id plus a normalized input fingerprint. Falsifiable question: does "
    "suppression trigger on two catalogs that collide on id but describe different work (spec "
    "11320), or does it wrongly merge them?",
    P9 + [SPEC + ":11320"],
    ["IMP-0370"],
    "1) a colliding-id fixture with different inputs that must NOT be suppressed; 2) an identical "
    "re-dispatch that MUST be suppressed.",
    ["control: id collision with differing fingerprints must run both, loudly flagged",
     "negative control: drop the fingerprint from the key and assert the collision fixture is "
     "wrongly suppressed"],
    to=2700, prof="crossvendor-dedupe-module")

add("9", "Crash recovery and orphan reclamation",
    "Implement tools/crossvendor/recover.py reclaiming units and leases from dead sessions and "
    "preserving their partial artifacts. Falsifiable question: is any partial artifact deleted or "
    "overwritten during reclamation, and can reclamation itself be interrupted safely?",
    P9,
    ["IMP-0370", "IMP-0371"],
    "1) an artifact census before and after reclamation; 2) an interrupted-reclamation fixture "
    "resumed to completion with the census still intact.",
    ["chaos: kill during reclamation, resume, census unchanged",
     "negative control: overwrite a partial artifact and assert the census FAILS"],
    sub="local-serialized", prof="crossvendor-recovery-module")

add("9", "Structured handoff protocol",
    "Implement tools/crossvendor/handoff.py enforcing that a session hands off a TYPED summary with "
    "the original goal re-anchored, never another agent's raw output as prefix context. Falsifiable "
    "question: can raw upstream output reach a downstream prompt, measured by scanning delivered "
    "prompts rather than by reading the protocol doc?",
    P9,
    ["IMP-0369"],
    "1) a delivered-prompt scan for verbatim upstream spans above a length threshold; 2) a schema "
    "check that every handoff carries goal, findings, residuals and evidence sections.",
    ["unit: handoff schema validation",
     "control: a raw-output handoff must be REFUSED",
     "negative control: scanner proven on a known verbatim span before its silence is trusted"],
    to=2700, prof="crossvendor-handoff-module")

add("9", "Shared completion reducer as the single implementation",
    "Implement tools/lib/completion.py as the ONE completion predicate consumed by local runners, "
    "cloud dispatchers, monitors, harvesters, workflow fan-in, cross-vendor adapters and final "
    "synthesis. Falsifiable question: how many distinct completeness implementations exist in the "
    "tree after this unit, and do any two of them disagree on a shared fixture set?",
    P9 + [A_PRED, R_GATES, SPEC + ":11314"],
    ["B06"],
    "1) a tree-wide census of completeness implementations by call graph, required exactly one "
    "reachable; 2) a 40-case fixture run through every consumer, verdicts compared for equality.",
    ["unit: all 12 predicate conditions",
     "invariant: exactly one reachable implementation",
     "control (spec 11314 two-predicates-disagree class): plant a second reducer and assert the "
     "census FIRES"],
    to=3600, sub="worktree-isolated", model=M_DUAL, rev=REV_CROSS,
    prof="shared-reducer-module",
    fc=["duplicate-control-plane", "overclaim", "detector-failure", "green-not-live"])

add("9", "Cross-vendor work-unit and artifact envelope",
    "Implement tools/lib/envelope.py defining the vendor-neutral work-unit and artifact contract "
    "(the 19 mandated fields plus the receipt) that every adapter must produce. Falsifiable "
    "question: does an artifact produced by the Codex rail validate against the SAME schema as one "
    "produced by the Claude rail, byte-for-byte on the shared fields?",
    P9 + [SPEC + ":10605-10625"],
    ["IMP-0376", "B06"],
    "1) the same logical unit executed on both rails, both receipts validated by one schema; 2) a "
    "field-level diff of the shared keys with only vendor-specific keys allowed to differ.",
    ["contract: both rails validate against one schema",
     "negative control: add a vendor-only field to the shared section and assert validation FAILS"],
    prof="crossvendor-contract-artifact", retry=R_NORETRY)

add("9", "Capability negotiation and vendor capability manifest",
    "Implement tools/crossvendor/negotiate.py so each vendor declares tools, context limits, "
    "streaming and schema support before dispatch, and units are routed only to a rail that can "
    "satisfy them. Falsifiable question: is a unit ever dispatched to a rail lacking a required "
    "capability, and is the manifest measured from the rail or merely declared in config?",
    P9,
    ["IMP-0377"],
    "1) a live probe per rail measuring each declared capability, compared against the config; 2) a "
    "dispatch audit proving no unsatisfiable routing occurred.",
    ["unit: capability matching including the unsatisfiable case",
     "control: a config claiming a capability the probe cannot confirm must be flagged",
     "negative control: remove the probe and assert the config-only path is detectable"],
    to=2700, model=M_DUAL, prof="crossvendor-negotiation-module")

add("9", "Codex/OpenAI rail adapter with prompt-by-file transport",
    "Implement tools/crossvendor/adapters/codex.py dispatching synchronously with a prompt FILE (not "
    "an inline argument), --ignore-user-config, an explicit output-last-message file and a 30-minute "
    "timeout. Falsifiable question: at what prompt size does the inline route fail on this box, and "
    "does the file route survive that same size - measured, not assumed?",
    P9 + [SPEC + ":10579", "rules/common/cross-vendor-dispatch.md"],
    ["IMP-0377", "IMP-0378"],
    "1) a size-sweep measuring the inline failure threshold and the file route at 2x that size; 2) "
    "an AND-gate on completion: exit 0 AND a non-empty parseable output file AND schema validation.",
    ["measurement: inline-vs-file size sweep with the failure point published",
     "control (win-arg-limit class): a payload above the limit must succeed via file and fail inline",
     "negative control: accept exit-0 alone and assert a severed-stream run is wrongly reported as "
     "SUCCESS"],
    to=5400, sub="local-serialized", tools=T_WX, model=M_DUAL, rev=REV_CROSS,
    prof="crossvendor-adapter-module",
    fc=["severed-stream", "win-arg-limit", "timeout", "schema-invalid", "green-not-live"])

add("9", "Abstraction-leak registry with loud degradation",
    "Implement tools/crossvendor/leaks.py as an explicit register of every place vendors are NOT "
    "interchangeable (tools, context, permissions, streaming, schema support), consulted at dispatch "
    "so degradation is announced rather than silent. Falsifiable question: for each registered leak, "
    "is there a runtime probe that would detect it if the vendor's behaviour changed, or is the "
    "register a static document that will silently go stale?",
    P9 + [SPEC + ":10983"],
    ["IMP-0379", "IMP-0378"],
    "1) a probe-coverage census: registered leaks with a runtime probe vs without, both counts "
    "published; 2) each probe executed against both rails today with its result recorded.",
    ["census: probe coverage per registered leak",
     "control: a leak with no probe must be reported as UNVERIFIED, not as handled",
     "negative control: change a vendor limit in a stub and assert the corresponding probe FIRES"],
    to=3600, model=M_DUAL, prof="crossvendor-leak-register",
    fc=["stale-premise", "overclaim", "detector-failure", "green-not-live"])

# ============================================================================
# PHASE 16 - self-improvement loop (4 units, IMP-0381..IMP-0384)
# ============================================================================
P16 = [A_P16, A_STOP]

add("16", "Improvement-candidate intake with baseline reproduction",
    "Implement tools/selfimprove/intake.py turning an observed failure or opportunity into a "
    "structured candidate that MUST carry a reproduced baseline before it can advance. Falsifiable "
    "question: can a candidate reach the implementation stage without a reproduction receipt, and "
    "does the intake distinguish a real failure from a flaky one (reproduced n times out of m)?",
    P16 + [D_NOREG],
    ["B06", "IMP-0376"],
    "1) a stage-gate audit proving no candidate advanced without a reproduction receipt; 2) a "
    "repeat-count field with the observed n-of-m recorded for each candidate.",
    ["unit: candidate schema and stage gates",
     "control: a flaky failure (3 of 10) must be labelled flaky, not accepted as a baseline",
     "negative control: remove the gate and assert an unreproduced candidate advances"],
    prof="selfimprove-intake-module")

add("16", "Isolated implementation with a measured benefit gate",
    "Implement tools/selfimprove/measure.py building each candidate in an isolated worktree and "
    "running the benchmark and regression suite before and after. Falsifiable question: is the "
    "measured delta outside the noise band of repeated identical runs, and is the noise band "
    "measured rather than assumed?",
    P16 + [D_NOREG],
    ["IMP-0381"],
    "1) a null-change control run measuring the noise band on the same harness; 2) the candidate's "
    "delta reported against that measured band, not against zero.",
    ["control: null-change run establishes the noise band",
     "measurement: candidate delta vs measured band",
     "negative control: a no-op candidate must NOT be reported as an improvement"],
    to=5400, sub="worktree-isolated", prof="selfimprove-measure-artifact")

add("16", "Automatic revert of neutral or harmful changes with a retention ledger",
    "Implement tools/selfimprove/retain.py keeping a change only when improvement is measured, "
    "reverting otherwise, and recording both outcomes in an append-only retention ledger. "
    "Falsifiable question: after a revert, is the tree byte-identical to the pre-change state, and "
    "does the revert path ever touch a file the candidate did not modify?",
    P16 + [SPEC + ":11146"],
    ["IMP-0382"],
    "1) a tree hash before the change and after the revert, required equal; 2) the revert's touched-"
    "file set compared against the candidate's modified-file set.",
    ["integration: apply-then-revert tree-hash equality",
     "safety: revert touches no unrelated file",
     "negative control: a revert that misses one file must be caught by the tree hash"],
    oa=True, rev=REV_OWNER, sub="local-serialized", tools=T_WP,
    prof="selfimprove-retention-module",
    fc=["owner-blocked", "overclaim", "green-not-live", "detector-failure"])

add("16", "Lesson writeback and benchmark augmentation",
    "Implement tools/selfimprove/writeback.py recording each retained lesson into the correct skill, "
    "rule or workflow AND adding a regression case so the same failure cannot silently return. "
    "Falsifiable question: does the new regression case actually fail against the pre-fix tree - if "
    "it passes there too, it protects nothing?",
    P16 + [SPEC + ":11148", D_NOREG],
    ["IMP-0383"],
    "1) the new test executed against the pre-fix commit, required RED; 2) the same test against the "
    "post-fix tree, required GREEN.",
    ["both-states control: new regression case must be RED pre-fix and GREEN post-fix",
     "control: writeback target verified in the REPO, not only in the live deployed tree",
     "negative control: a test that passes in both states must be REJECTED as non-protective"],
    prof="selfimprove-writeback-module")

# ============================================================================
# EMIT
# ============================================================================
START = 257
out = []
for i, u in enumerate(UNITS):
    ph = u["phase"]
    base = FAM[ph]
    kw = u["kw"]
    uid = "IMP-%04d" % (START + i)
    prof = kw.get("prof", base["prof"])
    out.append({
        "id": uid,
        "title": u["title"],
        "phase": ph,
        "question_or_target": u["q"],
        "inputs": u["inputs"],
        "dependencies": u["deps"],
        "assigned_model_vendor_role": kw.get("model", base["model"]),
        "tool_permissions": kw.get("tools", base["tools"]),
        "execution_substrate": kw.get("sub", base["sub"]),
        "timeout_seconds": kw.get("to", base["to"]),
        "output_path": "command-center/receipts/%s.json" % uid,
        "output_schema": ("command-center/schema/receipt.schema.json profile=%s "
                          "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
                          "test_ids[], negative_control_ids[], reviewer_verdict, "
                          "residual_unknowns[])" % prof),
        "evidence_requirement": u["ev"],
        "tests_required": u["tests"],
        "reviewer_requirement": kw.get("rev", base["rev"]),
        "completion_sentinel": "SUCCESS:%s" % uid,
        "retry_policy": kw.get("retry", base["retry"]),
        "failure_classification": kw.get("fc", base["fc"]),
        "owner_approval_required": kw.get("oa", False),
    })

dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "IMP-3.json")
with io.open(dest, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=True)
    fh.write("\n")
print("wrote", dest, len(out))
