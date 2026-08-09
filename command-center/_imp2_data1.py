# -*- coding: utf-8 -*-
"""IMP-2 slice, data part 1: units IMP-0129..IMP-0194.

Groups:
  A  (21) IMP-0129..0149  workflow spec / type-system extensions in tools/agentspec
  B  (17) IMP-0150..0166  foundry ingestion: discovery, provenance, license, import adapters
  B2 ( 3) IMP-0167..0169  extraction hardening
  C  (12) IMP-0170..0181  dedup, semantic graph, lineage, merge maps
  D  (13) IMP-0182..0194  fusion strategies + generation

Field keys are short here; _imp2_build.py expands each into the 19 mandated fields,
written explicitly ON EACH UNIT (no global defaults block - see ground/cc-reality F1).
"""

AGENTSPEC = "tools/agentspec/agentspec"
JSPARITY = "tools/agentspec-js"
RAIL = "tools/agentrail/agentrail"
FOUNDRY = "tools/foundry"  # new package, single home for Phase 7 foundry logic

SPEC_P7 = "_USER-PROMPTS.md:10873-10913 (Phase 7)"
SPEC_FOUNDRY = (
    "_USER-PROMPTS.md:11152-11170 (Workflow Foundry required production behavior)"
)
SPEC_LIB = "_USER-PROMPTS.md:10900-10907 (required library taxonomy)"
SPEC_FAIL = "_USER-PROMPTS.md:11298-11347 (known failure classes)"
SPEC_PRED = "_USER-PROMPTS.md:10627-10648 (one completion predicate everywhere)"
SPEC_SCALE = "_USER-PROMPTS.md:10570-10583 (scaling doctrine)"
NO_DUP_PLANE = "_USER-PROMPTS.md:10483 (do not create duplicate control planes)"

UNITS_1 = [
    # ---------------------------------------------------------------- GROUP A (21)
    dict(
        t="Add a Subworkflow node type to the frozen workflow spec",
        q="Target: add a frozen `Subworkflow` node (id, workflow_ref, param_bindings, id_namespace) to "
        f"{AGENTSPEC}/spec.py alongside FanOut/Barrier/Pipeline (:77-108), so a Workflow can embed another "
        "Workflow by reference. Acceptance: a two-level nesting validates, ids from the inner workflow are "
        "namespaced so they cannot collide with the outer unit ids, and a self-reference or reference cycle "
        "is rejected by a NEW closed violation id rather than recursing until stack exhaustion.",
        i=[f"{AGENTSPEC}/spec.py:32-120", f"{AGENTSPEC}/validate.py", SPEC_P7],
        d=["B06"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two independent signals: (1) pytest over a fixture with a 3-level nesting shows namespaced ids in "
        "the flattened plan; (2) a hand-built cyclic fixture returns the new violation id from validate_workflow "
        "with a bounded call count (assert recursion depth, not just 'it raised').",
        ts=[
            "a cyclic-reference fixture must FAIL validation (both-states control: the acyclic twin must PASS)",
            "mutation: delete the namespacing step and the id-collision test must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Add a Loop node with an explicit convergence predicate and a hard iteration bound",
        q="Target: add a frozen `Loop` node (id, body, convergence_expr, max_iterations, on_bound_reached) to "
        f"{AGENTSPEC}/spec.py. Acceptance: a Loop with no convergence_expr AND no max_iterations is a "
        "validation error, not a runtime hang; the bound is enforced in the type, so 'council loops forever "
        "without information gain' (spec failure class) is unrepresentable rather than merely tested for.",
        i=[f"{AGENTSPEC}/spec.py", f"{AGENTSPEC}/validate.py", SPEC_FAIL],
        d=["IMP-0129"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) the unbounded-Loop fixture yields the new violation id; (2) a property test over "
        "randomly generated Loop bodies shows the executor plan length is <= max_iterations for every sample.",
        ts=[
            "unbounded Loop fixture must FAIL validation; the bounded twin must PASS",
            "property test: plan length never exceeds max_iterations across 200 generated bodies",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Add a HumanCheckpoint node with a resumable pause token",
        q="Target: add a frozen `HumanCheckpoint` node (id, prompt_ref, allowed_responses, default_if_unanswered, "
        "pause_token) so a workflow can stop for an owner decision. Acceptance: reaching a checkpoint writes a "
        "durable pause record and returns a terminal envelope (not a hang), and the SAME workflow resumed with "
        "the token continues from the checkpoint with no re-execution of completed units.",
        i=[
            f"{AGENTSPEC}/spec.py",
            f"{AGENTSPEC}/envelope.py",
            "_USER-PROMPTS.md:11349-11370 (owner interaction)",
        ],
        d=["IMP-0129"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) the pause record exists on disk and parses; (2) a resumed run's event log shows zero "
        "re-dispatch events for units completed before the checkpoint (count from the ledger, not from prose).",
        ts=[
            "pause-then-resume round trip preserves completed-unit receipts byte-for-byte",
            "negative control: a checkpoint with no default_if_unanswered and no responder must terminate, never block",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["uncontrolled-silence", "owner-blocked"],
        oa=False,
    ),
    dict(
        t="Add DynamicFanOut whose cardinality is resolved from a producer receipt at runtime",
        q="Target: add a frozen `DynamicFanOut` node (id, producer_unit, item_path, unit_template, max_cardinality) "
        f"so fan-out width can come from data. Today {AGENTSPEC}/spec.py:77-83 FanOut carries a static tuple of "
        "unit ids. Acceptance: cardinality is read from the producer's SCHEMA-VALIDATED receipt only, a missing or "
        "unparseable producer receipt yields a typed failure instead of a zero-width silent success, and "
        "max_cardinality caps a runaway producer.",
        i=[f"{AGENTSPEC}/spec.py:77-83", f"{AGENTSPEC}/oracle.py", SPEC_PRED],
        d=["IMP-0129"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) a producer emitting 7 items yields exactly 7 planned units; (2) a producer emitting a "
        "PROGRESS stream instead of a receipt yields severed-stream, proven by asserting the taxonomy reason string.",
        ts=[
            "zero-item producer must produce an explicit empty-fanout verdict, never a silent pass",
            "mutation: bypass the oracle on the producer receipt and the severed-stream test must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["severed-stream", "detector-failure", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Add a typed workflow parameter model (Param, defaults, required, enum, secret-ref)",
        q="Target: give Workflow a typed `params` surface so a blueprint is instantiable rather than hardcoded. "
        "Acceptance: a param declared `secret_ref` NEVER carries a literal value in the serialized workflow (it "
        "carries an env/secret-store reference), and the export path refuses to write a workflow whose params "
        "hold a value matching a credential-shaped pattern.",
        i=[
            f"{AGENTSPEC}/spec.py:112-119",
            "tools/lib/security.mjs",
            "_USER-PROMPTS.md:10579-10580 (never bundle auth)",
        ],
        d=["IMP-0129"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) a fixture with a literal token in a param fails export with a named violation; (2) an "
        "independent grep of the exported bytes for the fixture token returns zero hits.",
        ts=[
            "credential-shaped literal in a param must FAIL export; the secret_ref twin must PASS",
            "mutation: weaken the pattern to match nothing and the leak test must go red",
        ],
        rev="cross-vendor reviewer (Codex) plus one Claude adversarial reviewer - secret-adjacent surface",
        retry="two-strikes",
        fc=["overclaim", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement param validation and coercion at load time with new closed violation ids",
        q="Target: validate params when a Workflow is loaded, not when a unit finally runs. Acceptance: a missing "
        "required param, a type mismatch, an out-of-enum value and an unknown param key each produce a DISTINCT "
        "violation id, and the id set stays closed (no free-form strings).",
        i=[f"{AGENTSPEC}/validate.py (28-id closed set)", "IMP-0133 output"],
        d=["IMP-0133"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) four fixtures yield four distinct ids; (2) the closure test that enumerates the module's "
        "id constants matches the documented set exactly (set equality, computed - not eyeballed).",
        ts=[
            "four distinct param-violation fixtures, four distinct ids, all in the closed set",
            "an unknown param key must be rejected (strict-parser failure class, spec:11302)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Add per-unit model/vendor/role routing that resolves through rails.toml, not a rival table",
        q="Target: add `routing` (vendor, model, role, fallbacks) to WorkUnit and resolve it through "
        f"{RAIL}/rails.toml. Acceptance: no second rail registry is introduced - "
        "tools/agentrail/tests/test_no_rival_core.py must still pass, and a routing value naming an unknown rail "
        "fails validation with a named id rather than falling back silently to a default vendor.",
        i=[
            f"{AGENTSPEC}/spec.py:63-75",
            f"{RAIL}/rails.toml",
            "tools/agentrail/tests/test_no_rival_core.py",
            NO_DUP_PLANE,
        ],
        d=["IMP-0129"],
        role="integrator",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) test_no_rival_core.py green after the change (it walks the AST for redeclarations); "
        "(2) an unknown-rail fixture returns the new violation id.",
        ts=[
            "unknown rail name must FAIL validation; a known rail must PASS",
            "mutation: hardcode a vendor default in the resolver and the unknown-rail test must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["dependency-blocked", "schema-invalid", "overclaim"],
        oa=False,
    ),
    dict(
        t="Add a per-unit least-privilege tool-permission set to the spec",
        q="Target: add `tool_permissions` to WorkUnit as a closed, declared set, and make the runtime refuse to "
        "dispatch a unit whose requested tools are not a subset of its declaration. Acceptance: the check runs "
        "BEFORE spawn (in dispatchpolicy), so an over-privileged unit never starts.",
        i=[
            f"{AGENTSPEC}/dispatchpolicy.py",
            f"{AGENTSPEC}/spec.py:63-75",
            "_USER-PROMPTS.md:11320-11321 (permission-boundary class)",
        ],
        d=["IMP-0129"],
        role="security-implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) an over-privileged fixture is rejected pre-spawn (assert zero process spawns, measured "
        "by a counting fake rail); (2) the permitted twin spawns exactly once.",
        ts=[
            "over-privileged unit must be rejected with zero spawns; the compliant twin spawns once",
            "mutation: move the check after spawn and the zero-spawn assertion must go red",
        ],
        rev="cross-vendor reviewer (Codex) - permission boundary",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Add a declared source-class policy per unit (which evidence classes a unit may consume)",
        q="Target: add `source_policy` (allowed source classes, e.g. official-docs, code, papers, forums, archival, "
        "public-tor) to WorkUnit and enforce it in the research stages. Acceptance: enabling the tor class requires "
        "an explicit owner flag; without it the class is unavailable and the workflow says so loudly rather than "
        "degrading to a silent subset.",
        i=[
            "_USER-PROMPTS.md:11280-11296 (Tor/onion safety policy)",
            f"{AGENTSPEC}/spec.py",
            "tools/lib/net-allowlist.mjs",
        ],
        d=["IMP-0136"],
        role="security-implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) a tor-requesting fixture without the flag returns owner-blocked, not a partial result; "
        "(2) the net-allowlist module is the ONLY egress gate referenced (grep shows no second allowlist).",
        ts=[
            "tor class without the owner flag must FAIL closed",
            "no second egress allowlist is introduced (AST/grep assertion)",
        ],
        rev="cross-vendor reviewer (Codex) - legal/egress surface",
        retry="two-strikes",
        fc=["owner-blocked", "overclaim"],
        oa=True,
    ),
    dict(
        t="Add a per-node failure policy expressed over the closed taxonomy",
        q="Target: add `on_failure` (abort | continue | quarantine | escalate | repair) per node, keyed by "
        f"{AGENTSPEC}/taxonomy.py families so policy branches on the FAMILY, not on a substring of an error "
        "message. Acceptance: a policy naming a reason outside the closed taxonomy fails validation.",
        i=[f"{AGENTSPEC}/taxonomy.py", f"{AGENTSPEC}/spec.py"],
        d=["IMP-0129"],
        role="spec-author",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) an out-of-taxonomy reason string fails validation; (2) a table-driven test asserts one "
        "policy outcome per taxonomy family with no family unmapped (set difference computed, not eyeballed).",
        ts=[
            "every taxonomy family has exactly one mapped policy (computed set difference == empty)",
            "an out-of-taxonomy reason must FAIL validation",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Add a RepairLoop node with an attempt limit and a proof-of-impossibility exit",
        q="Target: implement the spec's fix-review cycle (11272-11276) as a first-class node: send weak work back "
        "until it passes, the attempt limit is reached, OR a proof-of-impossibility record demonstrates why the "
        "evidence cannot be obtained. Acceptance: all THREE exits are reachable and each writes a distinct, "
        "typed terminal record - 'gave up' and 'proved impossible' must not share a code path.",
        i=[
            "_USER-PROMPTS.md:11272-11276",
            f"{AGENTSPEC}/spec.py",
            f"{AGENTSPEC}/retry.py",
        ],
        d=["IMP-0130", "IMP-0138"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) three fixtures drive the three exits and yield three distinct terminal records; "
        "(2) the proof-of-impossibility record schema-validates and names its settling experiment.",
        ts=[
            "three exits, three distinct records, asserted by code not by reading output",
            "mutation: collapse attempt-limit and impossibility into one code path and the discrimination test goes red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Separate workflow-level retry policy from the dispatch-level retry rail",
        q=f"Question: can a workflow declare its own retry policy without widening {AGENTSPEC}/retry.py, which "
        "deliberately retries ONLY win-arg-limit (once) and rate-limited (bounded backoff)? Target: implement "
        "workflow-level retry as a distinct layer that CALLS plan_retry and never re-implements it. Acceptance: "
        "test_no_rival_core-style AST assertion proves no redeclaration of the dispatch retry constants.",
        i=[
            f"{AGENTSPEC}/retry.py",
            "tools/agentrail/tests/test_no_rival_core.py",
            NO_DUP_PLANE,
        ],
        d=["IMP-0138"],
        role="integrator",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) AST walk finds zero redeclarations of the retry constants; (2) a fixture that exhausts "
        "workflow retries shows dispatch-level attempts unchanged in the ledger (counted, not inferred).",
        ts=[
            "AST assertion: dispatch retry constants are imported, never re-typed",
            "workflow retry exhaustion does not multiply dispatch retries (ledger count equality)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Implement a deterministic, clock-free artifact-cache key with an invalidation contract",
        q="Target: derive a content-addressed cache key from (workflow id, spec_version, unit id, resolved prompt, "
        "param values, tool policy, input artifact hashes) and define when it is invalid. Acceptance: the key is "
        f"stable across runs and machines ({AGENTSPEC}/determinism.py must still pass: no clock, no entropy), and "
        "changing ANY of the seven inputs changes the key - proven one input at a time.",
        i=[
            f"{AGENTSPEC}/determinism.py",
            f"{AGENTSPEC}/canonical.py",
            "_USER-PROMPTS.md:11305,11313 (stale cache masks a fixed package; corrupted-cache tests)",
        ],
        d=["IMP-0133"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) seven one-at-a-time mutations each change the key (7/7, computed); (2) two runs 6 hours "
        "apart on the same inputs produce an identical key (no clock leakage).",
        ts=[
            "7 single-input mutations produce 7 distinct keys (no collisions)",
            "corrupted cache entry must be detected and refetched, never served (both-states control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Define dry-run semantics in the spec so a plan can be produced with zero side effects",
        q="Target: add a dry_run evaluation mode that resolves routing, params, cardinality bounds and cost estimate "
        "while performing NO spawn, NO write outside a scratch dir, and NO network call. Acceptance: a dry run of "
        "the largest fixture workflow makes exactly zero process spawns and zero egress, measured by instrumented "
        "ports rather than asserted in prose.",
        i=[
            f"{AGENTSPEC}/ports.py" if False else f"{RAIL}/ports.py",
            f"{AGENTSPEC}/dispatchpolicy.py",
        ],
        d=["IMP-0135", "IMP-0136"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) a counting fake rail records zero spawns; (2) a net-allowlist shim records zero egress "
        "attempts during the same run.",
        ts=[
            "zero spawns and zero egress on a dry run of the largest fixture",
            "mutation: let one node escape dry-run and the zero-spawn counter must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement a pre-run cost, time and impact estimator over the budget ledger",
        q="Target: estimate micro-cost, wall-clock and blast radius (files/paths a workflow may write) BEFORE "
        f"execution, reusing {AGENTSPEC}/budget.py rather than a second accounting model. Acceptance: the estimate "
        "and the post-run actual are emitted in the same units and the estimator's error on the hermetic eval "
        "registry is reported as a number, not as 'accurate'.",
        i=[f"{AGENTSPEC}/budget.py", f"{AGENTSPEC}/evals/registry.py"],
        d=["IMP-0133", "IMP-0141"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) estimate-vs-actual table over the eval registry with a reported median absolute error; "
        "(2) budget ledger monotonicity and no-double-count assertions still pass.",
        ts=[
            "estimate-vs-actual error is COMPUTED and recorded (a number, not an adjective)",
            "writes declared in the estimate are a superset of writes actually observed in the fixture run",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Define the deterministic replay log format (event stream to identical plan)",
        q="Question: what minimal event record makes a run replayable such that replaying it reproduces the SAME "
        "plan and the SAME verdicts without re-dispatching? Target: specify and implement that record. Acceptance: "
        "replay of a recorded run produces a byte-identical plan and identical oracle verdicts, with zero spawns.",
        i=[
            f"{AGENTSPEC}/clock.py",
            "command-center/events/EVENTS.jsonl",
            "tools/event-ledger",
        ],
        d=["IMP-0141"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) byte-equality of the replayed plan; (2) zero spawns during replay, counted by the fake rail.",
        ts=[
            "record-then-replay yields a byte-identical plan and identical verdicts",
            "mutation: drop one event field and the byte-equality test must go red (proves the field is load-bearing)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Specify the resume state model so a partial run is never discarded",
        q="Target: define the resumable checkpoint record (completed unit ids + receipt hashes + open nodes + param "
        "bindings) and the rule that a resume NEVER re-runs a unit whose receipt still passes the oracle. "
        "Acceptance: killing a run at 40% and resuming produces the same final artifact set as an uninterrupted "
        "run, compared by content hash.",
        i=[
            f"{AGENTSPEC}/oracle.py",
            SPEC_PRED,
            "_USER-PROMPTS.md:11012 (resume tests)",
        ],
        d=["IMP-0144"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) hash-set equality of final artifacts between killed-and-resumed and clean runs; "
        "(2) the resumed run's dispatch count is strictly less than the clean run's.",
        ts=[
            "kill-at-40%-then-resume equals a clean run by artifact content hash",
            "a unit whose receipt FAILS the oracle must be re-run on resume (both-states control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Implement canonical export/import with a byte-stable round trip",
        q=f"Target: extend {AGENTSPEC}/canonical.py so any Workflow (including the new node types) exports to a "
        "canonical form and re-imports to an equal object. Acceptance: export(import(export(w))) == export(w) "
        "byte-for-byte, on LF bytes obtained via `git cat-file -p` (NOT `git archive`, which returns CRLF on this "
        "box and would silently validate the wrong bytes).",
        i=[
            f"{AGENTSPEC}/canonical.py",
            "rules/common/windows-shell.md (8b: blob vs archive)",
        ],
        d=["IMP-0129", "IMP-0130", "IMP-0131", "IMP-0132"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) round-trip byte equality over every fixture; (2) the same check run against the committed "
        "blob bytes (git cat-file) as well as the working tree, so a CRLF-only difference cannot masquerade as a pass.",
        ts=[
            "idempotent round trip over all fixtures including every new node type",
            "CRLF working-tree copy and LF blob copy both round-trip (the recorded EOL trap)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement spec_version migration rules and an executable migrator",
        q="Target: every new node type bumps spec_version and ships a migrator old->new plus a refusal for new->old. "
        "Acceptance: a workflow written at the pre-Phase-7 version loads after migration with identical semantics "
        "(same plan), and an unmigratable construct fails loudly instead of being dropped.",
        i=[
            f"{AGENTSPEC}/spec.py:116 (spec_version)",
            f"{AGENTSPEC}/validate.py (spec-version-unsupported)",
        ],
        d=["IMP-0146"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) plan equality between a migrated old workflow and its hand-written new twin; "
        "(2) an unmigratable fixture returns a typed refusal (asserted id), never a partial workflow.",
        ts=[
            "migrated-old plan equals hand-written-new plan",
            "silent-drop mutation: make the migrator skip an unknown key and the refusal test must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Keep the violation-id set closed after every Phase-7 spec extension",
        q="Target: a closure test that enumerates every violation id emitted anywhere in validate.py (AST-derived, "
        "not a hand-maintained list) and asserts set-equality with the documented set. Acceptance: adding an id "
        "without documenting it FAILS; the current 28-id set (measured this session) is the baseline.",
        i=[f"{AGENTSPEC}/validate.py", "tools/detector-self-test"],
        d=["IMP-0134", "IMP-0138"],
        role="test-author",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) AST-derived id set equals the documented set; (2) a deliberately undocumented id makes "
        "the test go red (detector control - the test must fire on the broken state).",
        ts=[
            "AST-derived id set == documented set (computed equality)",
            "planted undocumented id must turn the closure test red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure"],
        oa=False,
    ),
    dict(
        t="Port every new spec type to the JS parity package and prove parity mechanically",
        q=f"Target: mirror all Phase-7 spec additions into {JSPARITY}/src and extend {JSPARITY}/parity so the two "
        "implementations are compared on shared fixtures. Acceptance: the parity harness enumerates the Python "
        "violation ids and asserts the JS side emits the SAME set for the SAME fixtures - a missing id on either "
        "side is a failure, not a warning.",
        i=[f"{JSPARITY}/parity", f"{JSPARITY}/fixtures", f"{AGENTSPEC}/validate.py"],
        d=["IMP-0148"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=5400,
        ev="Two signals: (1) parity harness green with the id sets compared as SETS; (2) a planted JS-only omission "
        "turns it red.",
        ts=[
            "Python and JS emit identical violation-id sets over shared fixtures",
            "planted omission on the JS side must fail parity (both-states control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "dependency-blocked"],
        oa=False,
    ),
    # ---------------------------------------------------------------- GROUP B (17)
    dict(
        t="Build the discovery adapter for local repository, branches and worktrees",
        q="Target: enumerate every workflow-shaped artifact in the local repo including refs and worktrees, emitting "
        "candidate rows with a content hash and the exact access method for each path. Acceptance: a path that is "
        "readable only on a remote ref carries `git show <ref>:<path>` as its recorded access method, because a "
        "bare path there is unreadable and has already cost this estate seven independent rediscoveries.",
        i=["workflows/rtv-pdr.js", "tools/", "rules/common/fan-out-contract.md (A5)"],
        d=["B04"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) the adapter finds a KNOWN-PRESENT workflow (workflows/rtv-pdr.js) - detector control; "
        "(2) a sentinel name that exists nowhere returns zero hits.",
        ts=[
            "known-present control found; known-absent sentinel returns 0",
            "a ref-only path is recorded with its access method, verified by actually reading it back",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Build the discovery adapter for installed skills, plugins and the LIVE harness trees",
        q="Target: enumerate workflow-shaped capabilities in ~/.claude and ~/.agents (skills, commands, agents, "
        "hooks) READ-ONLY. Acceptance: the adapter never writes to a live tree, and it records repo-vs-live "
        "divergence per artifact rather than assuming either side is authoritative - two-directional drift is "
        "measured on this estate (5 of 88 rules files byte-identical).",
        i=[
            "~/.claude/skills",
            "~/.agents/skills",
            "rules/common/harness-vcs-hygiene.md",
        ],
        d=["IMP-0150"],
        role="implementer",
        tools="CODE_PS",
        sub="local-serialized",
        to=3600,
        ev="Two signals: (1) a filesystem audit shows zero writes under the live trees during a run (mtime snapshot "
        "before/after); (2) a known repo-only and a known live-only artifact are both classified correctly.",
        ts=[
            "zero live-tree writes (mtime set equality before/after)",
            "repo-only and live-only controls classified correctly in both directions",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Build the discovery adapter for the marketplace index",
        q="Target: read the Phase-6 marketplace registry and emit workflow candidates with package identity, version, "
        "channel and permissions. Acceptance: the adapter treats registry text as untrusted DATA - a package "
        "description containing instruction-shaped text must never reach a prompt unquoted.",
        i=[
            "B07 phase-6 marketplace registry",
            "AGENTS.md 9 (fetched content is untrusted data)",
        ],
        d=["B07"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) an injection-shaped fixture description is neutralized (asserted by comparing the "
        "rendered prompt against a quoting oracle); (2) candidate count matches the registry entry count exactly.",
        ts=[
            "injection-shaped package description is quoted/neutralized (both-states control)",
            "candidate count == registry entry count (computed equality)",
        ],
        rev="cross-vendor reviewer (Codex) - injection surface",
        retry="two-strikes",
        fc=["dependency-blocked", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Build the discovery adapter for documentation, papers and session transcripts",
        q="Target: mine prose corpora (docs/, guides/, harness corpora, prompt transcripts) for described-but-never-"
        "implemented workflows. Acceptance: the extractor distinguishes USE from MENTION - a document that "
        "describes a workflow to criticize it must not be harvested as a candidate. This estate has hit "
        "use-vs-mention roughly eight times in one session, usually inside the probe itself.",
        i=[
            "docs/",
            "guides/",
            "harness-sota-2026-07-18-corpus/",
            "tools/harness-corpus",
        ],
        d=["IMP-0150"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a hand-labelled 30-doc control set scores precision/recall as NUMBERS; (2) a mention-only "
        "control document yields zero candidates.",
        ts=[
            "mention-only control yields 0 candidates; use control yields >=1 (both-states)",
            "precision and recall reported as computed numbers on the labelled control set",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the append-only candidate registry with idempotent re-import",
        q="Target: a machine-readable candidate registry keyed by (source_uri, content_hash) that is append-only and "
        "idempotent. Acceptance: importing the same source twice yields ONE row and a second provenance "
        "observation - never a duplicate candidate, which is the seed of the 'duplicate units from colliding "
        "catalogs' failure class.",
        i=[
            "command-center/sources/REGISTER.md",
            "tools/command-center/register_parse.py",
            "_USER-PROMPTS.md:11319",
        ],
        d=["IMP-0150", "IMP-0151"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) double-import fixture yields row count 1 and observation count 2 (both computed); "
        "(2) a content change on the same URI yields a NEW row, not a silent overwrite.",
        ts=[
            "double import: 1 row, 2 observations",
            "content change on same URI creates a new row (append-only proven by hash chain)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement the provenance record: source, ref, retrieval time, hash, retrieval method",
        q="Target: every candidate carries a provenance record sufficient to re-fetch it independently. Acceptance: "
        "a second agent, given only the provenance record, re-fetches the identical bytes - proven by an actual "
        "re-fetch, not by asserting the fields are present.",
        i=["IMP-0154 output", SPEC_FOUNDRY],
        d=["IMP-0154"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) re-fetch from the record reproduces the recorded hash for 10/10 sampled candidates; "
        "(2) a record with a mutated ref fails the re-fetch (detector fires on the broken state).",
        ts=[
            "10/10 sampled provenance records re-fetch to the recorded hash",
            "mutated-ref record must fail re-fetch (both-states control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement license extraction and SPDX normalization for every candidate",
        q="Target: extract the licence for each candidate and normalize to an SPDX id, with UNKNOWN as a first-class "
        "value. Acceptance: UNKNOWN is never silently coerced to permissive; a candidate with no discoverable "
        "licence is marked UNKNOWN and blocked from redistribution paths.",
        i=["IMP-0154 output", "_USER-PROMPTS.md:10715 (legal and license review)"],
        d=["IMP-0155"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a labelled control set of 20 known licences normalizes correctly (20/20 computed); "
        "(2) a licence-less fixture yields UNKNOWN and is refused by the redistribution gate.",
        ts=[
            "20-licence control set normalizes exactly; no silent permissive default",
            "UNKNOWN blocks redistribution (both-states: a permissive twin passes)",
        ],
        rev="cross-vendor reviewer (Codex) - legal surface",
        retry="two-strikes",
        fc=["overclaim", "owner-blocked"],
        oa=True,
    ),
    dict(
        t="Implement the licence-compatibility matrix and the fusion licence solver",
        q="Question: when N source workflows with different licences are fused, what licence may the result carry, "
        "and when is the fusion forbidden outright? Target: encode the matrix and make the fusion path CALL it. "
        "Acceptance: a copyleft+proprietary fusion is refused with a named reason and a suggested alternative "
        "(clean-room reimplementation), never silently produced.",
        i=[
            "IMP-0156 output",
            "_USER-PROMPTS.md:10723 (CLEAN-ROOM-REIMPLEMENT disposition)",
        ],
        d=["IMP-0156"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) the matrix is exhaustive over the observed licence set (computed set difference == "
        "empty); (2) a forbidden pair is refused at the fusion entry point, asserted by a test that calls the real "
        "fusion API rather than the matrix directly.",
        ts=[
            "forbidden pair refused at the FUSION entry point (not just in the matrix unit test)",
            "matrix covers every licence observed in the registry (computed)",
        ],
        rev="cross-vendor reviewer (Codex) - legal surface",
        retry="two-strikes",
        fc=["owner-blocked", "overclaim"],
        oa=True,
    ),
    dict(
        t="Implement trust-tier assignment for candidate sources",
        q="Target: assign each candidate a trust tier (first-party | vendor | community | unknown) from evidence "
        "(publisher identity, signature, repo ownership), and make the tier an INPUT to admission, not a label. "
        "Acceptance: an unknown-tier candidate cannot be auto-adopted; it can only be adopted after clean-room "
        "reimplementation or explicit owner approval.",
        i=["IMP-0155 output", "B07 phase-6 publisher identity"],
        d=["IMP-0155", "B07"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) an unknown-tier fixture is refused by the admission path; (2) tier assignment is "
        "reproducible - the same inputs yield the same tier across two runs with no clock dependency.",
        ts=[
            "unknown-tier candidate cannot be auto-adopted (both-states: first-party twin can)",
            "tier assignment is deterministic across runs",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["owner-blocked", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement freshness decay plus a maintenance-state revalidation scheduler",
        q="Target: track how stale each candidate's evidence is (last verified, upstream last-commit, archived flag, "
        "issue velocity) and schedule re-probes. Acceptance: a stored green DECAYS - the scheduler must re-probe "
        "anything whose evidence is older than its class TTL, because a live-advisory-backed result from last week "
        "is not a control for today.",
        i=["IMP-0155 output", "rules/common/single-signal-verification.md"],
        d=["IMP-0155"],
        role="implementer",
        tools="NET",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a candidate aged past TTL appears in the due-list (computed from the record, with an "
        "injected clock so the test is deterministic); (2) an archived upstream is flagged without a network call "
        "when the cached maintenance record is still fresh.",
        ts=[
            "TTL expiry moves a candidate into the due-list (injected clock, no wall clock)",
            "archived-upstream control is flagged; maintained control is not (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["green-not-live", "rate-limited"],
        oa=False,
    ),
    dict(
        t="Build the import adapter for Claude Code saved workflows (.mjs) to the typed Workflow",
        q="Target: translate a saved Workflow script (the injected agent/parallel/phase globals) into a typed "
        "Workflow. Acceptance: workflows/rtv-pdr.js - the ONLY saved workflow in this repo, measured this session - "
        "imports, validates, and its fan-out shape is preserved; anything not expressible is recorded in the "
        "lossy-import ledger rather than dropped.",
        i=["workflows/rtv-pdr.js", ".claude/workflows (live)", f"{AGENTSPEC}/spec.py"],
        d=["IMP-0129", "IMP-0132"],
        role="adapter-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) rtv-pdr.js imports and validates clean; (2) its fan-out width in the imported plan equals "
        "the width counted by reading the script (two independent derivations of the same number).",
        ts=[
            "rtv-pdr.js round-trips through import + validate",
            "an inexpressible construct is written to the lossy ledger, not silently dropped (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Build the import adapter for Codex fan-out profiles",
        q="Target: translate tools/codex/profiles/schemas/fanout.schema.json instances into typed Workflows. "
        "Acceptance: the translation preserves the dispatch-safety properties agentspec owns - no fire-and-forget, "
        "explicit timeout, prompt routed off argv - and a profile that violates any of them is REFUSED at import "
        "rather than imported and left to fail at run time.",
        i=[
            "tools/codex/profiles/schemas/fanout.schema.json",
            "tools/fanout-schema/fanout_schema.mjs",
            "rules/common/cross-vendor-dispatch.md",
        ],
        d=["IMP-0135"],
        role="adapter-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) a background-flagged profile is refused at import with a named reason; (2) the imported "
        "plan's argv is built through agentspec.argv (AST assertion, no local argv builder).",
        ts=[
            "fire-and-forget profile refused at import (both-states: the blocking twin imports)",
            "no local argv builder is introduced (AST assertion)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["severed-stream", "win-arg-limit", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Build the import adapter for generic declarative DAGs (YAML/JSON)",
        q="Target: import a vendor-neutral YAML/JSON DAG into a typed Workflow. Acceptance: case-distinct keys must "
        "not collide (the recorded case-insensitive-parser failure class), unknown fields are REJECTED not ignored "
        "(strict parser), and a duplicate node id is a named violation.",
        i=[
            "_USER-PROMPTS.md:11302,11309 (strict parser; case collision)",
            f"{AGENTSPEC}/validate.py",
        ],
        d=["IMP-0134"],
        role="adapter-author",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) a case-distinct-key fixture is preserved distinctly (two keys in, two keys out); "
        "(2) an unknown field yields a rejection id.",
        ts=[
            "case-distinct keys survive as distinct (both-states: a true duplicate is rejected)",
            "unknown field rejected, not ignored",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Build the adapter conformance harness every import adapter must pass",
        q="Target: one shared suite that every adapter is run against (round trip, lossy-ledger completeness, "
        "injection quarantine, dispatch-safety preservation, deterministic output). Acceptance: adding a new "
        "adapter without registering it in the harness FAILS a meta-test that discovers adapters by AST.",
        i=[
            "IMP-0160..IMP-0162 outputs (the three import adapters)",
            "tools/detector-self-test",
        ],
        d=["IMP-0160", "IMP-0161", "IMP-0162"],
        role="test-author",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) all three adapters pass the shared suite; (2) a planted unregistered adapter turns the "
        "meta-test red (detector control).",
        ts=[
            "3/3 adapters pass the shared conformance suite",
            "planted unregistered adapter must fail the discovery meta-test",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement typed stage extraction from an imported workflow",
        q="Question: what are the STAGES of an imported workflow, expressed in a vocabulary that is comparable across "
        "sources? Target: extract an ordered typed stage list with evidence spans back to the source. Acceptance: "
        "every extracted stage carries a source span, and a stage with no span is a failure - an unanchored "
        "extraction is the seed of every later false comparison.",
        i=["IMP-0160..IMP-0162 outputs (imported workflows)", SPEC_FOUNDRY],
        d=["IMP-0163"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) 100% of extracted stages carry a resolvable source span (computed coverage); "
        "(2) hand-labelled control workflow matches the extracted stage list.",
        ts=[
            "span coverage == 100% (computed, not sampled)",
            "hand-labelled control workflow reproduces exactly",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement role extraction with a normalized role vocabulary",
        q="Target: extract participant roles and map them onto one normalized vocabulary so 'critic', 'red team' and "
        "'refuter' are comparable. Acceptance: the mapping is a declared table, unmapped roles surface as UNKNOWN "
        "(never force-fitted), and the UNKNOWN rate is reported as a number.",
        i=["IMP-0164 output"],
        d=["IMP-0164"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) UNKNOWN rate computed over the whole candidate set; (2) an invented role name maps to "
        "UNKNOWN rather than to its nearest neighbour (no silent snapping).",
        ts=[
            "invented role maps to UNKNOWN (both-states: a known synonym maps correctly)",
            "UNKNOWN rate reported as a computed number",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim"],
        oa=False,
    ),
    dict(
        t="Extract gates and stopping rules into composable Boolean predicates",
        q="Target: turn each candidate's stop rule into a typed predicate tree supporting ANY/ALL/NOT and weighted "
        "logic. Acceptance: the six executable stopping expressions the spec names (10937-10942) all parse and "
        "evaluate, and a rule that cannot be expressed is recorded as UNKNOWN-NEEDS-PROBE rather than approximated.",
        i=[
            "_USER-PROMPTS.md:10937-10942",
            "_USER-PROMPTS.md:10760 (composable stopping rules)",
        ],
        d=["IMP-0165"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) 6/6 named expressions parse and evaluate on synthetic states; (2) an inexpressible rule "
        "yields UNKNOWN-NEEDS-PROBE, asserted by id.",
        ts=[
            "6/6 spec-named stopping expressions parse and evaluate",
            "inexpressible rule is flagged, never approximated (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim"],
        oa=False,
    ),
    # --------------------------------------------------------------- GROUP B2 (3)
    dict(
        t="Extract tool requirements and reconcile them against the permission model",
        q="Target: derive each candidate's tool requirements and reconcile them with the per-unit permission "
        "declaration. Acceptance: a candidate needing a tool the host cannot grant is marked BLOCKED with the exact "
        "missing capability named - not silently imported to fail later at dispatch.",
        i=["IMP-0136 output", "IMP-0165 output"],
        d=["IMP-0136", "IMP-0165"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a candidate requiring an absent tool is BLOCKED at import with the capability named; "
        "(2) the grantable twin imports clean.",
        ts=[
            "absent-tool candidate BLOCKED with the capability named (both-states control)",
            "reconciliation is a subset check, computed - not a substring match on prose",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["dependency-blocked", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement the lossy-import ledger so translation losses are loud, not silent",
        q="Target: every import writes what did NOT survive translation (construct, source span, reason, whether it "
        "is semantically load-bearing). Acceptance: an import whose ledger is empty must PROVE emptiness by "
        "accounting for 100% of source constructs; unaccounted constructs are a failure, because 'degrade loudly' "
        "is the spec's explicit instruction for abstraction leaks.",
        i=["_USER-PROMPTS.md:10983 (degrade loudly)", "IMP-0160..IMP-0162 outputs"],
        d=["IMP-0160", "IMP-0161", "IMP-0162"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) construct accounting sums to 100% on every fixture (computed); (2) a planted "
        "inexpressible construct appears in the ledger with a load-bearing flag.",
        ts=[
            "construct accounting == 100% on all fixtures",
            "planted inexpressible construct appears in the ledger (detector fires on the broken state)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "uncontrolled-silence"],
        oa=False,
    ),
    dict(
        t="Quarantine untrusted imported text so a candidate artifact cannot inject instructions",
        q="Target: all imported prose (descriptions, transcripts, README bodies, council transcripts) is stored and "
        "rendered as DATA. Acceptance: an imported artifact containing instruction-shaped text cannot alter a "
        "downstream prompt's directives - proven by a differential: the rendered prompt with and without the "
        "hostile payload must differ ONLY inside the quoted data region.",
        i=[
            "AGENTS.md 9",
            "_USER-PROMPTS.md:11344 (transcript injects instructions into later stages)",
        ],
        d=["IMP-0152", "IMP-0153"],
        role="security-implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) the differential shows changes confined to the quoted region (computed diff regions); "
        "(2) a control payload placed OUTSIDE the data region is caught by the same check (detector fires).",
        ts=[
            "hostile payload confined to the quoted region (differential, computed)",
            "control: an unquoted payload must be caught (both-states)",
        ],
        rev="cross-vendor reviewer (Codex) - injection surface",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    # ---------------------------------------------------------------- GROUP C (12)
    dict(
        t="Implement a structural mechanism fingerprint for a workflow",
        q="Question: what makes two workflows the same MECHANISM rather than the same words? Target: a fingerprint "
        "over the typed structure (stage kinds, role set, gate predicates, tool classes, topology) that is "
        "invariant to renaming. Acceptance: renaming every identifier in a workflow leaves the fingerprint "
        "unchanged; changing one gate predicate changes it.",
        i=[
            "IMP-0164 output",
            "IMP-0166 output",
            "_USER-PROMPTS.md:10666 (mechanism-level deduplication)",
        ],
        d=["IMP-0164", "IMP-0166"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) rename-invariance proven on a mutant set (fingerprint equal for 20/20 renames); "
        "(2) single-gate mutation changes the fingerprint for 20/20 mutants.",
        ts=[
            "20/20 renames preserve the fingerprint; 20/20 gate mutations change it",
            "mutation: drop topology from the fingerprint and the gate-mutation test must go red",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the lexical near-duplicate detector with a planted-mutant control",
        q="Target: a token-Jaccard near-duplicate scan over candidate text, with its sensitivity CALIBRATED by "
        "planted mutants (exact rename, paraphrase, one-parameter fork, full rewrite). Acceptance: the report "
        "states the band each mutant class lands in, and explicitly scopes the verdict to LEXICAL similarity - a "
        "full semantic rewrite is NOT detectable by this instrument and the artifact must say so.",
        i=[
            "command-center/PROMPT-ONE-FLOOR-AUDIT.md (the same instrument, same scoping caveat)"
        ],
        d=["IMP-0170"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) planted-mutant bands reported as numbers; (2) a known distinct pair scores in the low "
        "band (control against a false-positive detector).",
        ts=[
            "planted mutant classes land in reported bands (calibration, not adjectives)",
            "known-distinct control pair scores low (false-positive control)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement semantic diff of two workflows over aligned stages, roles and gates",
        q="Target: align two workflows stage-by-stage and emit a typed diff (added/removed/changed stage, role, gate, "
        "tool). Acceptance: the diff is DIRECTIONAL and reports both sides' unique content, because a "
        "one-directional read cannot see two-directional divergence - the measured failure mode that produced 31 "
        "data-loss-pointing misclassifications on this estate.",
        i=["IMP-0170 output", "rules/common/fan-out-contract.md (C4)"],
        d=["IMP-0170"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a both-sides-unique fixture is classified DIVERGED, not one-sided; (2) the diff is "
        "antisymmetric: diff(a,b) reversed equals diff(b,a) (computed).",
        ts=[
            "both-sides-unique fixture classified DIVERGED (the exact measured blind spot)",
            "antisymmetry check computed over the fixture matrix",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement duplicate collapse that preserves duplicate-of edges instead of deleting rows",
        q="Target: collapse duplicates into a canonical row while KEEPING every duplicate-of edge and the losing "
        "row's provenance. Acceptance: the pre-collapse candidate set is fully reconstructible from the "
        "post-collapse graph - proven by reconstructing it and comparing sets.",
        i=["_USER-PROMPTS.md:10666-10677 (duplicate-of edges, source lineage)"],
        d=["IMP-0170", "IMP-0172"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) reconstruction equals the pre-collapse set exactly; (2) rank is computed from independent "
        "evidence and decision impact, NOT from how many sources repeated the idea (assert the count field is "
        "absent from the ranking function's inputs).",
        ts=[
            "pre-collapse set reconstructible from the graph (set equality)",
            "ranking function does not read repetition count (AST/param assertion)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Build the semantic component graph over extracted stages, roles and gates",
        q="Target: a graph whose nodes are reusable COMPONENTS (a stage kind with its contract) and whose edges are "
        "observed compositions. Acceptance: every component node traces to at least one candidate with a source "
        "span; an orphan component (no provenance) is a build failure.",
        i=["IMP-0165", "IMP-0166", "IMP-0167 outputs", SPEC_FOUNDRY],
        d=["IMP-0165", "IMP-0166", "IMP-0167"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) orphan-component count == 0 (computed); (2) a planted orphan makes the build fail "
        "(detector control).",
        ts=["orphan component count == 0", "planted orphan must fail the build"],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Build the merge/compatibility map: which components may legally and technically compose",
        q="Question: for each ordered component pair, may they compose, and under what precondition? Target: compute "
        "the map from contracts (output type, tool policy, licence, stop-rule compatibility). Acceptance: the map "
        "is exhaustive over the component set (no missing cells) and each FORBIDDEN cell names its reason.",
        i=["IMP-0174 output", "IMP-0157 output"],
        d=["IMP-0174", "IMP-0157"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) cell coverage == |components|^2 (computed); (2) every FORBIDDEN cell carries a machine-"
        "readable reason drawn from a closed set.",
        ts=[
            "cell coverage complete (computed, no missing pairs)",
            "forbidden reasons are drawn from a closed vocabulary",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement component conflict detection (contradictory stop rules, incompatible tool policy)",
        q="Target: detect pairs whose contracts CONFLICT even though both are individually valid - e.g. one requires "
        "unanimity, the other forbids it; one needs egress, the other declares an air-gapped policy. Acceptance: "
        "conflicts are detected structurally from the predicate trees, not by keyword matching on prose.",
        i=["IMP-0166 output", "IMP-0175 output"],
        d=["IMP-0166", "IMP-0175"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a synthetic contradictory pair is flagged; (2) a superficially similar but compatible "
        "pair is NOT flagged (false-positive control).",
        ts=[
            "contradictory pair flagged; compatible look-alike not flagged (both-states)",
            "detection reads the predicate tree, not the prose (AST assertion)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure"],
        oa=False,
    ),
    dict(
        t="Compute a capability-coverage vector per workflow",
        q="Target: express what each workflow can DO as a vector over a declared capability taxonomy, so coverage is "
        "comparable and gaps are computable. Acceptance: the taxonomy is declared once and versioned; adding a "
        "capability without a version bump fails a guard.",
        i=[SPEC_LIB, "IMP-0174 output"],
        d=["IMP-0174"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) vectors computed for 100% of registry candidates; (2) an unversioned taxonomy edit fails "
        "the guard (detector control).",
        ts=[
            "coverage vectors computed for every candidate (no nulls)",
            "unversioned taxonomy change must fail the guard",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement the coverage-gap finder against the required library taxonomy",
        q="Question: which of the library categories the spec mandates (research/evidence 15, engineering/reliability "
        "21, security/governance 12, product/design 15, data/science 16, collective-intelligence/meta 17 = 96 "
        "exactly, counted from _USER-PROMPTS.md:10902-10907) have ZERO covering candidate? Target: compute the gap "
        "set. Acceptance: the tool reproduces the 96 total independently from the spec text - a hardcoded 96 is a "
        "broken detector.",
        i=[SPEC_LIB, "IMP-0177 output"],
        d=["IMP-0177"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) the parser recounts the categories from the spec text and sums to 96 without a hardcoded "
        "constant; (2) a deliberately removed category changes the sum (detector fires).",
        ts=[
            "category counts derived from spec text, not hardcoded (sum == 96)",
            "removing a category from the fixture changes the computed sum",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Build the lineage graph linking every fused workflow to its source components",
        q="Target: record, for every generated or fused workflow, the exact source components, their versions, their "
        "licences and the fusion strategy used. Acceptance: lineage survives a round trip through export/import - "
        "'workflow provenance or license is lost' is a named failure class and must be impossible, not merely "
        "avoided.",
        i=["_USER-PROMPTS.md:11334", "IMP-0147 output"],
        d=["IMP-0147", "IMP-0174"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) lineage present after export/import round trip (field-by-field equality); (2) a "
        "lineage-stripped fixture is REFUSED by the publish path.",
        ts=[
            "lineage survives round trip (computed equality)",
            "lineage-stripped workflow refused at publish (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement decomposition: turn a fusion back into its source components, and test the inverse",
        q="Target: implement decompose(fusion) -> source components and prove it is a true inverse of the fusion "
        "operation for every strategy. Acceptance: for each of the eight fusion strategies, "
        "decompose(fuse(a,b)) yields components equal to {a,b} under the structural fingerprint - eight separate "
        "assertions, not one generic claim.",
        i=[
            "IMP-0170 output",
            "_USER-PROMPTS.md:10742,11170 (decomposable back into source mechanisms)",
        ],
        d=["IMP-0170", "IMP-0182"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) 8/8 strategies pass the inverse property; (2) a deliberately lossy fusion fails the "
        "inverse test (detector fires on the broken state).",
        ts=[
            "8/8 fusion strategies satisfy the decomposition inverse",
            "planted lossy fusion must fail the inverse test",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement the trivial-fork detector so renamed copies cannot inflate the candidate count",
        q="Target: detect renamed copies and trivial forks and EXCLUDE them from the 160-candidate floor. Acceptance: "
        "the floor count is reported twice - raw and de-forked - and the de-forked number is the one that counts, "
        "because the spec explicitly forbids counting trivial forks or renamed copies (10725).",
        i=["_USER-PROMPTS.md:10725", "IMP-0170", "IMP-0171 outputs"],
        d=["IMP-0170", "IMP-0171"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) a planted renamed copy is excluded; (2) a genuinely distinct sibling with similar naming "
        "is NOT excluded (false-positive control).",
        ts=[
            "planted renamed copy excluded; similar-name distinct sibling retained (both-states)",
            "raw and de-forked counts both reported",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    # ---------------------------------------------------------------- GROUP D (13)
    dict(
        t="Implement stage-splice fusion",
        q="Target: implement the stage-splice strategy - replace one workflow's stage with a better-performing stage "
        "from another, preserving the surrounding contract. Acceptance: the spliced stage's input/output contract "
        "is checked against its neighbours BEFORE the fusion is emitted; a contract mismatch is a refusal.",
        i=["_USER-PROMPTS.md:10737,11161", "IMP-0175 output"],
        d=["IMP-0174", "IMP-0175"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) contract-mismatch fixture refused; (2) a valid splice runs end to end on the fake rail "
        "and its plan differs from both parents (proving it is not silently one parent).",
        ts=[
            "contract mismatch refused (both-states: matching contract accepted)",
            "spliced plan differs from BOTH parents (computed, guards against no-op fusion)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["schema-invalid", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement common-core fusion",
        q="Target: extract the intersection of two or more workflows as a reusable core and re-express each source "
        "as core + delta. Acceptance: re-composing core+delta reproduces each source exactly (fingerprint equality) "
        "- otherwise the 'core' is a lossy summary masquerading as a factorization.",
        i=["_USER-PROMPTS.md:10737", "IMP-0170 output"],
        d=["IMP-0182"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) core+delta reproduces each source (n/n fingerprint equality); (2) an over-eager core "
        "that loses a source stage fails that equality (detector fires).",
        ts=[
            "core + delta reproduces every source exactly",
            "planted lossy core must fail reproduction",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement union fusion with duplicate-stage collapse",
        q="Target: union two workflows, collapsing structurally identical stages rather than concatenating them. "
        "Acceptance: the union of a workflow with ITSELF is that workflow (idempotence), which is the cheapest "
        "possible falsifier of a naive concatenating implementation.",
        i=["_USER-PROMPTS.md:10737", "IMP-0170 output"],
        d=["IMP-0182"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=1800,
        ev="Two signals: (1) union(w,w) == w by fingerprint; (2) union(a,b) contains every capability of a and of b "
        "(coverage-vector superset, computed).",
        ts=[
            "idempotence: union(w,w) == w",
            "capability superset property holds for both parents",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim"],
        oa=False,
    ),
    dict(
        t="Implement best-of-breed fusion driven by per-stage benchmark evidence",
        q="Question: for each stage slot, which source's implementation actually performs best on matched cases? "
        "Target: select per-stage by measured evidence, not by reputation. Acceptance: the selection record cites "
        "the benchmark run id for every chosen stage; a stage chosen with no evidence is a build failure.",
        i=["IMP-0197 output", "_USER-PROMPTS.md:10737"],
        d=["IMP-0182", "IMP-0197"],
        role="implementer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) 100% of chosen stages carry a benchmark run id; (2) forcing a no-evidence stage into the "
        "input makes the build fail (detector control).",
        ts=[
            "every chosen stage cites a benchmark run id",
            "no-evidence stage must fail the build",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement conditional-hybrid fusion (route to a source by runtime condition)",
        q="Target: emit a fusion that dispatches to different source sub-workflows based on a typed runtime "
        "predicate. Acceptance: every branch is reachable (static reachability proof) and the default branch is "
        "explicit - an unreachable branch is dead capability masquerading as coverage.",
        i=["_USER-PROMPTS.md:10737", "IMP-0195 output"],
        d=["IMP-0182", "IMP-0195"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) static reachability shows 0 unreachable branches; (2) a planted unreachable branch is "
        "detected (detector control).",
        ts=[
            "0 unreachable branches (computed)",
            "planted unreachable branch is detected",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement ensemble fusion with an explicit aggregation rule",
        q="Target: run N source workflows and aggregate. Acceptance: the aggregation rule is declared and typed "
        "(majority | weighted | evidence-gated | execution-consensus), and an ensemble that agrees only because "
        "its members share an input is flagged - correlated members are not independent evidence, which is the "
        "measured failure of counting agents instead of probes.",
        i=["_USER-PROMPTS.md:10737", "rules/common/single-signal-verification.md (5)"],
        d=["IMP-0182"],
        role="implementer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) a correlated-members fixture is flagged as non-independent; (2) an independent-members "
        "fixture is not flagged (false-positive control).",
        ts=[
            "correlated ensemble flagged; independent ensemble not flagged (both-states)",
            "aggregation rule is typed and declared, asserted by schema",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "detector-failure"],
        oa=False,
    ),
    dict(
        t="Implement progressive fusion (cheap tier first, escalate only on need)",
        q="Target: compose a cheap fast source and an expensive thorough source into a progressive workflow with an "
        "explicit escalation predicate. Acceptance: on the benchmark set the progressive form must match the "
        "expensive form's correctness within a declared tolerance while doing measurably less work - both numbers "
        "reported, and a failure to meet either is a REJECT not a caveat.",
        i=["_USER-PROMPTS.md:10737", "IMP-0197 output"],
        d=["IMP-0182", "IMP-0197"],
        role="implementer",
        tools="CODE",
        sub="cloud-batch",
        to=5400,
        ev="Two signals: (1) correctness delta vs the expensive form computed on matched cases; (2) work reduction "
        "computed from the budget ledger, not estimated.",
        ts=[
            "correctness within declared tolerance AND measured work reduction (both required)",
            "a progressive form that never escalates on a hard case must FAIL (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement meta-workflow composition (a workflow whose units are workflows)",
        q="Target: compose workflows as first-class units via the Subworkflow node, with budget and failure policy "
        "rolled up. Acceptance: a two-level meta-workflow's total budget equals the sum of its children (no "
        "double-count, asserted against the immutable budget ledger) and a child failure maps to the parent's "
        "declared policy rather than aborting the whole tree by default.",
        i=[f"{AGENTSPEC}/budget.py", "IMP-0129 output", "IMP-0138 output"],
        d=["IMP-0129", "IMP-0138"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=3600,
        ev="Two signals: (1) budget sum equality computed from the ledger; (2) a child failure under a `continue` "
        "policy leaves siblings running (observed in the event log, not inferred).",
        ts=[
            "budget roll-up has no double count (ledger assertion)",
            "child failure honours the parent policy (both-states: abort vs continue)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "dependency-blocked"],
        oa=False,
    ),
    dict(
        t="Implement the fusion admission gate: outperform or materially complement, or be rejected",
        q="Target: no fusion enters the library unless it beats its sources on a declared metric OR provides a "
        "capability none of them has. Acceptance: a fusion that is merely LARGER is rejected - 'a merged workflow "
        "is not accepted because it contains more stages' (11170) is implemented as a gate, not repeated as advice.",
        i=["_USER-PROMPTS.md:11170", "IMP-0197 output"],
        d=["IMP-0197", "IMP-0180"],
        role="implementer",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) a bigger-but-not-better fusion is rejected by the gate; (2) a genuinely complementary "
        "fusion passes on the capability-vector criterion with the new capability named.",
        ts=[
            "bigger-but-not-better fusion REJECTED (both-states: a better one passes)",
            "complementarity is proven by a capability-vector difference, not by prose",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
    dict(
        t="Implement the capability-loss detector for fusions",
        q="Target: assert that a fusion retains every capability of every source. Acceptance: the check is a "
        "computed set difference over capability vectors and it FIRES on a planted loss - 'workflow fusion loses a "
        "source capability' is a named failure class (11333).",
        i=["_USER-PROMPTS.md:11333", "IMP-0177 output"],
        d=["IMP-0177", "IMP-0182"],
        role="test-author",
        tools="CODE",
        sub="local-parallel",
        to=1800,
        ev="Two signals: (1) set-difference == empty on all admitted fusions; (2) a planted dropped stage makes the "
        "detector fire (both-states control).",
        ts=[
            "capability set difference empty for all admitted fusions",
            "planted capability loss detected",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement the duplicate-control-plane detector for fusions and imports",
        q="Question: does this fusion or import introduce a SECOND control plane (a rival scheduler, a rival "
        "completion oracle, a rival rail registry, a rival argv builder)? Target: an AST-level detector modelled on "
        "tools/agentrail/tests/test_no_rival_core.py, applied to every generated artifact. Acceptance: it fires on "
        "a planted rival oracle; the hard constraint at 10483 becomes mechanical rather than aspirational.",
        i=[
            "tools/agentrail/tests/test_no_rival_core.py",
            NO_DUP_PLANE,
            "_USER-PROMPTS.md:11333",
        ],
        d=["IMP-0182"],
        role="test-author",
        tools="CODE",
        sub="local-parallel",
        to=3600,
        ev="Two signals: (1) the detector fires on a planted rival completion oracle; (2) it is silent on the real "
        "library (zero false positives across all admitted workflows, computed).",
        ts=[
            "planted rival oracle detected (detector fires on the broken state)",
            "zero false positives across the admitted library",
        ],
        rev="cross-vendor reviewer (Codex) - architectural boundary",
        retry="two-strikes",
        fc=["detector-failure", "overclaim"],
        oa=False,
    ),
    dict(
        t="Implement workflow generation from a typed goal (natural language to Workflow)",
        q="Target: given a typed goal + constraints, emit a schema-valid Workflow. Acceptance: generation is gated by "
        "the scout - if an existing workflow already covers the goal, the generator must REFUSE and return the "
        "existing one, because 'workflow discovery ignores an existing superior workflow and rebuilds it' is a "
        "named failure class (11331).",
        i=["_USER-PROMPTS.md:11331", "IMP-0209 output"],
        d=["IMP-0209", "IMP-0134"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=5400,
        ev="Two signals: (1) a goal already covered by the library returns the existing workflow, not a new one; "
        "(2) an uncovered goal produces a schema-valid workflow that passes static validation.",
        ts=[
            "covered goal returns the incumbent (both-states: uncovered goal generates)",
            "generated workflow passes schema + static validation with no manual repair",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "schema-invalid"],
        oa=False,
    ),
    dict(
        t="Implement workflow generation from an execution trace or a measured benchmark gap",
        q="Target: synthesize a workflow from (a) a recorded successful ad-hoc execution trace, or (b) a coverage gap "
        "computed by the gap finder. Acceptance: a trace-derived workflow REPLAYS the trace's outcome on the same "
        "inputs, and a gap-derived workflow closes the specific gap it cites - each verified by re-running the gap "
        "finder afterwards and showing that gap absent.",
        i=["IMP-0144 output (replay log)", "IMP-0178 output (gap finder)"],
        d=["IMP-0144", "IMP-0178"],
        role="implementer",
        tools="CODE",
        sub="worktree-isolated",
        to=5400,
        ev="Two signals: (1) trace replay outcome equality; (2) the cited gap is absent from a fresh gap-finder run "
        "(re-measured, not asserted).",
        ts=[
            "trace-derived workflow reproduces the trace outcome",
            "gap-derived workflow removes the cited gap on re-measurement (both-states)",
        ],
        rev="one independent adversarial reviewer in a fresh context",
        retry="two-strikes",
        fc=["overclaim", "green-not-live"],
        oa=False,
    ),
]
