"""Build platform/registry/workflow-candidates-1.json.

MEASURED fields (provenance, bytes, lines, last-commit date, mechanism scan,
tree file counts, body hashes) come from the probe artifacts -- they are not
retyped by hand. JUDGEMENT fields (task_fit, classification, rationale,
stop_rules prose, failure_behaviour) are explicit literals below, each anchored
to a file:line or an exact command output.

Verdict vocabulary is the 15-item closed set from the spawn brief.
"""

import json
import subprocess

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
OUT = "platform/registry/workflow-candidates-1.json"

VOCAB = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}

with open("command-center/_wfa1_deep_scan.json", encoding="utf-8") as fh:
    SCAN = {r["id"]: r for r in json.load(fh)}


def last_commit(path):
    if not path:
        return None
    r = subprocess.run(
        ["git", "--git-dir", MIRROR, "log", "-1", "--format=%ci", REF, "--", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or "").strip()[:10] or None


# license: measured once, applies to every artifact in this range
LICENSE_TEXT = (
    "no license declared -- all rights reserved (owner-authored private estate)"
)
LICENSE_SRC = (
    "MEASURED: no LICENSE/LICENSE.md/LICENSE.txt/COPYING blob exists at "
    "07f465f37d49710f7060dcc7b567d6c58213177b (git cat-file -s returned rc=128 for all four; "
    "detector control: the same probe returns rc=0/19154 for README.md). "
    '07f465f3:package.json declares "private": true and has NO "license" key. '
    "Live-tree artifacts (~/.claude/workflows, ~/.agents) are owner-authored on the owner's own "
    "machine. NOT an OSI grant -- absence of a license means all rights reserved."
)

# ---------------------------------------------------------------- judgement
J = {
    "wf-saved-agentic-repair-reliability": dict(
        classification="DISTILL",
        prior="DISTILL",
        task_fit="Research/audit workflow whose durable value is its PROBLEM FRAMING (why agentic repair ships green-tested-but-non-functional software), not its 2-phase topology. Directly relevant to this program's completion-gate design.",
        stages=["Research-Audit (1 parallel fan-out)", "Synthesize"],
        roles=["research lens", "harness auditor", "gem designer", "synthesizer"],
        tools=[
            "Claude Code Workflow runtime (agent/parallel/phase globals)",
            "StructuredOutput fan-in",
        ],
        stop_rules=[
            "no explicit stop rule: phase sequence terminates after Synthesize",
            "null-tolerant barrier via filter(Boolean) x1",
        ],
        failure_behaviour="A throwing agent resolves to null and is filtered out (filter(Boolean) x1); no retry, no escalation, no terminal-state marker.",
        benchmark="none. Executed >=2x per prior run records (NOT re-measured by this unit).",
        rationale="Adopt the framing, not the script: 2 agents / 2 schemas is below the fan-out this program needs.",
    ),
    "wf-saved-bc-stage-compendium-enrichment": dict(
        classification="DISTILL",
        prior="SPECIALIZE",
        task_fit="Battle-Cats-specific content pipeline; the transferable asset is the generic Enrich -> Compile -> Critique spine with a terminal completeness critic.",
        stages=[
            "Enrich (parallel gap-closure)",
            "Compile (synthesis)",
            "Critique (completeness critic)",
        ],
        roles=["enricher", "compiler/synthesizer", "completeness critic"],
        tools=[
            "Claude Code Workflow runtime",
            "local game-data reads (read-only, no device)",
        ],
        stop_rules=["none declared; fixed 3-phase sequence"],
        failure_behaviour="filter(Boolean) x1. ZERO schema: keys -> UNTYPED fan-in, so a malformed agent return is not caught at the barrier. This is the defect, not a feature.",
        benchmark="none.",
        rationale="I DIFFER from the prior pass (SPECIALIZE -> DISTILL): a BC-domain workflow cannot be adopted as a specialization by a general workflow platform; only its 3-stage critic spine transfers. Prior classification is defensible if the intent was 'keep as a specialized variant'.",
    ),
    "wf-saved-codex-auth-research-fanout": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="HIGHEST fit in this range. The most complete reference implementation of the estate's fan-out contract: artifact-first, batched, resume-safe, with a DISK AND-gate that refuses to trust the vendor's own idle signal.",
        stages=[
            "Ground (load catalog + count disk AND-gate DONE)",
            "Fan-out (batched parallel lenses, default batch=4)",
            "Gate (C1 re-validate status vs disk)",
            "Synthesize",
        ],
        roles=[
            "ground/discovery agent",
            "research lens (per wave)",
            "gate/validator",
            "synthesizer",
        ],
        tools=[
            "Claude Code Workflow runtime",
            "cross-vendor Codex rail (22 codex refs)",
            "Write tool for per-agent artifact paths",
            "status_fanout probe",
        ],
        stop_rules=[
            "UNIT DONE = artifact >=1024 bytes AND its tail contains the exact line 'UNIT-COMPLETE: <id>' (file:line codex-auth-research-fanout.mjs:27)",
            "'CODEX THREADS IDLE is NOT done -- only disk UNIT-COMPLETE is done' (mjs:63)",
            "monitor_ok true only if the status probe's DONE count equals an INDEPENDENT re-count (mjs:171) -- a two-signal gate",
            "resume manifest written to STATE_DIR/workflow-ground.json (mjs:169) so a re-invocation skips completed units",
        ],
        failure_behaviour="filter(Boolean) x4. A blocked unit STILL writes a partial artifact + UNIT-COMPLETE + a BLOCKER section (mjs:237) -- i.e. write-as-you-go is enforced, so a dead agent is not a total loss.",
        benchmark="none numeric. 6 schema: fan-ins, 12 UNIT-COMPLETE references, 2 UNVERIFIED tags, 2 Sherman-Kent band references measured by regex scan.",
        rationale="Adopt whole. Its disk-AND-gate + independent re-count + partial-write-on-block is exactly the completion discipline this program's gate needs.",
    ),
    "wf-saved-design-gate": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Direct fit for a COUNCIL primitive: 5 fresh personas in parallel, each returning a typed verdict. Maps 1:1 onto a CouncilSpec instance.",
        stages=[
            "Review (5 fresh reviewers in parallel)",
            "Verdict (aggregate + append to bounded shadow sink)",
        ],
        roles=["PM", "Architect", "Designer", "Security", "CTO"],
        tools=[
            "Claude Code Workflow runtime",
            "bounded shadow sink (append-only)",
            "READ-ONLY reviewers",
        ],
        stop_rules=[
            "per-reviewer verdict enum ['APPROVE','REJECT'] + boolean blocking (design-gate.mjs:43-44)",
            "NO convergence loop in the script: 'the metaswarm gate iterates until all approve; here that convergence loop is the HUMAN's to run (re-invoke after edits)' (mjs:6-8)",
            "SHADOW mode: advisory, NEVER blocks (mjs:10-12)",
        ],
        failure_behaviour="filter(Boolean) x2; a throwing reviewer resolves to null and is dropped from the aggregate -- so a 5-persona council can silently become a 4- or 3-persona one. Quorum is NOT enforced. Flagged as a real gap for this program.",
        benchmark="none.",
        rationale="Adopt as the council reference; the missing quorum floor is an EXTEND item, not a blocker.",
    ),
    "wf-saved-harness-self-improve-sweep": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="14-lens discovery sweep with a verify stage -- the shape this program's archaeology phase itself uses.",
        stages=[
            "Ground (dedup-set + harness inventory)",
            "Discover (14 parallel lenses)",
            "Synthesize (dedup + cross-lens convergence + tiered queue)",
            "Verify (spot-check top items vs real config/code)",
        ],
        roles=["ground/dedup agent", "14 discovery lenses", "synthesizer", "verifier"],
        tools=[
            "Claude Code Workflow runtime",
            "model pinned to 'fable' (hardcoded const M)",
            "codex refs x6",
        ],
        stop_rules=[
            "fixed 4-phase sequence; the Verify phase is the only falsification gate",
            "no round cap / no convergence predicate",
        ],
        failure_behaviour="filter(Boolean) x2. 5 schema: fan-ins. No retry or escalation path.",
        benchmark="none.",
        rationale="Wrapper needed for two measured reasons: (1) the filename carries a typo -- 'harness-self-improve-sweep-imporant.js' -- rename on adoption; (2) the model is hardcoded to 'fable' rather than injected.",
    ),
    "wf-saved-plan-gate": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="The MECHANICAL-LINT-BEFORE-LLM pattern is the reusable core and is a direct instance of fan-out-contract C4 (never fan a mechanical comparison out to LLM judgement).",
        stages=[
            "Stage-0 (mechanical python lint of the plan)",
            "Review (3 fresh adversarial reviewers in parallel)",
            "Verdict (aggregate + shadow sink)",
        ],
        roles=[
            "mechanical linter",
            "Feasibility reviewer",
            "Completeness reviewer",
            "Scope & Alignment reviewer",
        ],
        tools=[
            "Claude Code Workflow runtime",
            "python stage-0 linter",
            "bounded shadow sink",
        ],
        stop_rules=[
            "stage-0 verdict enum ['clean','dirty','na'] (plan-gate.mjs:47)",
            "per-reviewer verdict enum ['PASS','FAIL'] + boolean blocking (mjs:73-74)",
            "'a structurally broken plan is caught by ~1 ms of Python before N Opus reviewers burn tokens' (mjs:6-7)",
            "SHADOW mode: advisory, never blocks (mjs:10-12)",
        ],
        failure_behaviour="filter(Boolean) x1; reviewers are READ-ONLY so no worktree isolation is needed (mjs:15). Same missing-quorum gap as design-gate.",
        benchmark="none.",
        rationale="Adopt whole; the cheap-mechanical-gate-first ordering is the single most cost-effective mechanism in this range.",
    ),
    "wf-saved-reconcile-all-branches-prs": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="Family-partitioned fan-out + a merge-ORDER planner. Relevant to this program only if it ships multiple stacked PRs (release mode is PR-ONLY, so it is).",
        stages=[
            "Analyze (PR families + branch landscape + overlap)",
            "Synthesize (reconciliation map + phased consolidation plan)",
        ],
        roles=["per-family analyst", "merge-order planner"],
        tools=["Claude Code Workflow runtime", "gh/git reads", "codex refs x4"],
        stop_rules=["fixed 2-phase sequence", "READ-ONLY by declaration (no mutation)"],
        failure_behaviour="filter(Boolean) x1, 2 schema: fan-ins, 1 retry token.",
        benchmark="none.",
        rationale="Wrapper needed: the PR numbers are HARDCODED to the 2026-07-18 landscape -> must be parameterised before reuse.",
    ),
    "wf-saved-trainer-gui-mega-plan": dict(
        classification="DISTILL",
        prior="DISTILL",
        task_fit="The 6-stage Research -> SolverDeepDive -> Design -> Critique -> Refine -> Finalize spine with an explicit REFINE-after-critique loop is the transferable asset; the Battle Cats content is not.",
        stages=[
            "Research (parallel deep research)",
            "SolverDeepDive (extra depth on the crux)",
            "Design",
            "Critique (adversarial + 5-perspective design gate)",
            "Refine (revise each section against critique)",
            "Finalize (compile + append phased build plan)",
        ],
        roles=[
            "researcher",
            "crux specialist",
            "designer",
            "adversarial critic",
            "refiner",
            "compiler",
        ],
        tools=["Claude Code Workflow runtime", "5 parallel() sites", "8 agent() sites"],
        stop_rules=[
            "fixed 6-phase sequence; ONE refine pass, not a loop-until-converged"
        ],
        failure_behaviour="filter(Boolean) x7 -- the highest barrier count in the range. But ZERO schema: keys: the largest saved workflow (280 lines) has NO typed fan-in at all, so barrier nulls are the ONLY error signal.",
        benchmark="none.",
        rationale="Distil the critique->refine edge; do not adopt the script (untyped fan-in at 280 lines is the estate's worst typed-fan-in gap).",
    ),
    "wf-saved-uiux-tooling-consolidation": dict(
        classification="MERGE",
        prior="SPECIALIZE",
        task_fit="Same Ground -> Fan-out -> Synthesize topology as wf-saved-workspace-gem-hunt and wf-saved-harness-self-improve-sweep, aimed at a different domain (UI/UX) with ~14 lenses instead of ~40.",
        stages=[
            "Ground (inventory + overlap map)",
            "Fan-out (~14 lenses)",
            "Synthesize (consolidation architecture + verify)",
        ],
        roles=["ground agent", "~14 domain lenses", "synthesizer/verifier"],
        tools=[
            "Claude Code Workflow runtime",
            "model:'opus' pinned x2",
            "codex refs x6",
        ],
        stop_rules=["fixed 3-phase sequence; no round cap"],
        failure_behaviour="filter(Boolean) x1, 4 schema: fan-ins.",
        benchmark="none.",
        rationale="I DIFFER from the prior pass (SPECIALIZE -> MERGE). Measured: this, #5 and #10 are three instances of ONE topology (Ground/Fan-out/Synthesize, opus-pinned, codex-assisted). Their bodies are materially distinct (0 hash collisions) but the MECHANISM is redundant 3x. MERGE into one parameterised sweep primitive rather than carrying three.",
    ),
    "wf-saved-workspace-gem-hunt": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="The canonical carrier of the sweep topology and the WIDEST measured mechanism set in the corpus -- the right base for the merged sweep primitive.",
        stages=[
            "Ground (dedup-set + workspace map + other-sessions eval)",
            "Fan-out (~40 distinct lenses)",
            "Synthesize (dedup + converge + verify load-bearing claims + tiered queue)",
        ],
        roles=["ground agent", "~40 discovery lenses", "synthesizer", "claim verifier"],
        tools=[
            "Claude Code Workflow runtime",
            "model:'opus' x2",
            "codex refs x7",
            "resume/checkpoint",
        ],
        stop_rules=[
            "fixed 3-phase sequence; the Synthesize phase verifies load-bearing claims before publishing (the only falsification gate)"
        ],
        failure_behaviour="filter(Boolean) x1, 4 schema: fan-ins.",
        benchmark="Executed at 43 agents (prior run record 'workspace-gem-hunt-2026-07-12') with mechanism set {adversarial, codex, gate, opus, parallel, resume, schema, synthesis}. NOT re-executed by this unit.",
        rationale="Wrapper needed: absolute output path and lens list are hardcoded; parameterise, then use as the merge target for #5 and #9.",
    ),
    "wf-repo-rtv-pdr": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="A real TOURNAMENT/VOTING mechanism with explicit degenerate-case handling and worktree isolation -- the only repo-versioned workflow, and the closest existing thing to a council with a bounded round count.",
        stages=[
            "Rollout (N independent parallel Opus rollouts)",
            "Tournament (recursive pairwise judging by fresh agents)",
            "Refine (optional PDR pass conditioned on winner + losers' failure_modes)",
        ],
        roles=["N contestants (rollouts)", "fresh pairwise judges", "PDR refiner"],
        tools=[
            "Claude Code Workflow runtime",
            "isolation:'worktree' x2",
            "model:'opus' x5",
            "5 schema: fan-ins",
        ],
        stop_rules=[
            "N clamped to 2..5, default 4: `args.n >= 2 && args.n <= 5 ? Math.round(args.n) : 4` (rtv-pdr.js:116)",
            "ZERO survivors -> return {winner:null, rounds:0, rationale:'All rollouts failed -- no survivors.'} (js:157)",
            "ONE survivor -> short-circuit, rounds:0, 'no tournament needed' (js:160)",
            "recursive pairwise elimination until one winner remains; rounds reported in the output schema (js:101-103)",
            "self-reported confidence is LOGGING ONLY -- 'judges, not this, determine the winner' (js:61, js:136)",
            "contestants never judge themselves (js:24)",
        ],
        failure_behaviour="Explicit degenerate-case returns instead of a throw (js:157, js:160) -- the only candidate in this range that handles an empty survivor set as a first-class terminal state. COST WARNING documented in-file: N parallel Opus rollouts per invocation; the file itself prescribes gating behind the ESE gate (#21).",
        benchmark="cites arXiv:2604.16529 as its methodology source (rtv-pdr.js:3). NOT RESOLVED -- this unit ran no network probe; the id is recorded verbatim.",
        rationale="Adopt whole as the tournament primitive. Its self-declared pairing with the ESE gate makes #11+#21 a COMPOSE candidate.",
    ),
    "wf-agents-grill-yaml": dict(
        classification="EXTEND",
        prior="EXTEND",
        task_fit="One of only TWO vendor-neutral (declarative, provider-mapped) workflow encodings in the estate -- the natural seed for this program's portable spec layer.",
        stages=[
            "scout",
            "recall",
            "choose-mode",
            "build-decision-queue",
            "ask-one-question",
            "record-decision",
            "repeat-until-resolved",
            "converge",
        ],
        roles=["not modelled -- this schema maps SKILLS and PROVIDERS, not roles"],
        tools=[
            "provider invocation map: claude '/grill-me', codex '$grill-me', discovery_fallback '/skills'"
        ],
        stop_rules=[
            "'repeat-until-resolved' then 'converge' -- a declarative convergence stage, but the predicate itself is NOT expressed in the YAML (no metric, no cap). This is the extension point.",
            "5 declared invariants constrain behaviour",
        ],
        failure_behaviour="none encoded -- the YAML has no error, retry, or terminal-state vocabulary.",
        benchmark="none. schema_version: 1.",
        rationale="EXTEND: adopt the vendor-neutral shape, then add the typed stopping predicate + failure vocabulary it lacks. Directly comparable to the CouncilSpec/Workflow-DSL that Phase 4 just built.",
    ),
    "wf-agents-lifecycle-yaml": dict(
        classification="EXTEND",
        prior="EXTEND",
        task_fit="The shared 10-stage lifecycle plus the machine-readable form of the one-level-nesting rule and the AGENTS.md S5 handoff contract.",
        stages=[
            "discover",
            "recall",
            "grill",
            "plan",
            "plan-review",
            "execute",
            "spec-review",
            "quality-review",
            "acceptance",
            "capture",
        ],
        roles=[
            "per-provider capability map (claude / codex); roles themselves live in core.yaml"
        ],
        tools=[
            "limits.max_threads=4",
            "limits.max_depth=1",
            "handoff.format=structured-summary",
        ],
        stop_rules=[
            "max_depth=1 caps nesting (machine-readable form of the workflow-authoring one-level-nesting rule)",
            "max_threads=4 caps concurrency",
            "no per-stage stopping predicate",
        ],
        failure_behaviour="handoff.required_fields = [original_goal, completed, evidence, remaining, risks] -- exactly AGENTS.md S5. 'risks' is the only failure-adjacent field; there is no error taxonomy.",
        benchmark="none.",
        rationale="EXTEND. CONFLICT (needs_owner, carried forward from the prior pass and re-verified in the file at limits.max_threads): max_threads=4 contradicts the owner's standing 'fan out LARGE (50-100 agents)' preference. Do not silently resolve.",
    ),
    "wf-agents-roles-core": dict(
        classification="EXTEND",
        prior="EXTEND",
        task_fit="A ready-made role -> model-tier -> sandbox-mode routing table; directly reusable as the assignment table for any fan-out in this program.",
        stages=["n/a -- this is a routing table, not a sequence"],
        roles=[
            "explorer (tier=fast, sandbox=read-only)",
            "planner (tier=flagship, read-only)",
            "worker (tier=worker, sandbox=workspace-write)",
            "reviewer",
            "+ others",
        ],
        tools=[
            "provider tiers: claude flagship=opus/worker=sonnet/fast=haiku; codex flagship=gpt-5.6-sol/worker=gpt-5.4/fast=gpt-5.4-mini"
        ],
        stop_rules=["none -- a table, not a process"],
        failure_behaviour="none encoded.",
        benchmark="none.",
        rationale="EXTEND. CONFLICT (needs_owner): the claude tier map assigns worker=sonnet, which collides with the owner's standing 'Opus for ALL substantive subagents' preference. The sandbox_mode column is independently valuable and conflict-free.",
    ),
    "tool-agentspec": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="HIGHEST-CONSEQUENCE candidate in this range for THIS program. It already IS a portable vendor-neutral agent-workflow SPEC with a closed validation set and a completion oracle -- the same two artifacts Phase 4 just built independently.",
        stages=[
            "spec (frozen declarative types: WorkUnit, FanOut, Barrier, Pipeline, Workflow, ReceiptSpec)",
            "validate (closed 28-id violation set)",
            "oracle (6-clause completion AND-gate)",
            "evals (hermetic regression registry)",
        ],
        roles=["consumed BY runtimes/vendor adapters; declares no roles of its own"],
        tools=[
            "stdlib-only, zero runtime dependencies",
            "no I/O on the dispatch path, no wall clock, no entropy",
            "48 files incl. tests/test_mutations.py",
            "a JS port exists at tools/agentspec-js (npm workspace member per 07f465f3:package.json)",
        ],
        stop_rules=[
            "COMPLETION: 'A unit is SUCCESS only on the AND of six clauses' -- exit-zero, receipt-present, receipt-non-empty, receipt-parses, receipt-schema, receipt-content (agentspec/oracle.py:3-10)",
            "'Blocking on process exit is NOT proof of completion' (oracle.py:12)",
            "judge() REFUSES a vacuous ReceiptSpec, fail-closed (oracle.py:24-27)",
            "VALIDATION: closed 28-id violation set incl. unit-dep-cycle, unit-dep-self, unit-timeout-missing, unit-receipt-clause-vacuous, unit-worktree-no-writes (validate.py:25-57)",
        ],
        failure_behaviour="Verdict carries a FINE cause (operator-facing) AND a coarse `severed` family so a consumer never has to parse the other's string (oracle.py:17-19). Named anti-pattern avoided by construction.",
        benchmark="MEASURED BY THIS UNIT: the README's 'closed 28-id violation set' claim is CONFIRMED -- ast.parse of the VIOLATIONS tuple yields exactly 28 ids, and a mechanically different regex slice of the same literal block yields the same 28 (AGREE: True). My first detector reported 0 and was WRONG (it assumed ALL-CAPS ids); that zero was a detector failure, not a finding.",
        rationale="ADOPT-AS-IS, and treat as a RIVAL-DIALECT RISK: platform/lib/wfdsl (Workflow DSL) and platform/lib/completion_predicate.py were authored this wave without consuming this package. agentspec's own README states the reason it exists -- 'two independent plans were building the same argv guard, the same completion oracle... any runtime or vendor adapter now CONSUMES these functions; it must not reimplement them.' That is happening again right now.",
    ),
    "tool-agentrail": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="The existing proof that the agentspec core is genuinely vendor-neutral: a config-driven multi-rail dispatch shell where adding an agent CLI is a TOML row, not new Python.",
        stages=[
            "rails (enumerate)",
            "resolve (rail -> concrete argv)",
            "plan (dry)",
            "run (dispatch + receipt)",
            "deploy (guarded shim install)",
        ],
        roles=["dispatch rails for 5 rails across 4 vendors"],
        tools=[
            "agentrail/rails.toml (config-driven topology)",
            "consumes agentspec",
            "29 files incl. tests/test_mutations.py + tests/test_no_rival_core.py",
        ],
        stop_rules=[
            "every command emits agentspec's four mandated envelope fields (status/summary/next_actions/artifacts) plus a `terminal` marker ALWAYS",
            "on failure adds error{code, root_cause, retry_instruction, stop_condition} (runner.py:309,313)",
        ],
        failure_behaviour="One output shape on BOTH the success and the failure path; 'error-only output without next steps' is a named anti-pattern with no code path that produces it (README). 91 mutation references and a test_no_rival_core.py that mechanically forbids re-implementing the spec core.",
        benchmark="none numeric. Subject of the prior corpus's executed workflow 'lane4-agentrail' (9 agents) -- NOT re-executed here.",
        rationale="Adopt with agentspec as a pair; test_no_rival_core.py is itself the mechanism that would have caught this wave's duplicate-dialect problem.",
    ),
    "tool-fanout-schema": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Directly targets the failure mode this program's fan-in surface will hit: typed StructuredOutput fan-ins rejecting the agents' own work.",
        stages=[
            "measure (mine transcripts vs declared schema literals)",
            "rules (the design guide)",
            "lint (lintSource over existing schemas)",
            "module (makes the dominant failure unrepresentable)",
        ],
        roles=["n/a -- a library + lint + fixture corpus"],
        tools=[
            "fanout_schema.mjs",
            "lint_fanout_schemas.mjs",
            "historical-rejection.fixture.json",
            "node --test suite",
            "test_preflight_mutations.mjs (31 mutation refs)",
        ],
        stop_rules=["lint verdict over a schema literal; no runtime stop rule"],
        failure_behaviour="Encodes the rule that required[] must be a FLOOR only (no conditional fields) so a valid agent return cannot be rejected. 5 both-states references.",
        benchmark="MEASURED BY THIS UNIT (arithmetic + internal cross-check): claimed 22.7% StructuredOutput failure rate; 849/3735 = 22.73% -> arithmetic CONSISTENT. A second, independent implementation in the same README reports 3694/846/22.9% -- two mechanically different miners agreeing within 1.1%. Population: 11,693 transcripts / 10.65 GB joined to 637 schema literals across 435 workflow scripts. NOT RE-MINED by this unit (a 10.65 GB re-scan is out of scope) -- I verified the arithmetic and the presence of the second signal, not the raw corpus.",
        rationale="Adopt whole. This is the only candidate in the range that carries a real, cross-checked failure-rate measurement.",
    ),
    "tool-repomap": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="The mechanised form of fan-out-contract A11 (inject a shared grounding pack) -- directly applicable to a 2,007-unit fan-out where re-reads dominate tool calls.",
        stages=[
            "scan tree",
            "rank files/symbols by PageRank over reference edges",
            "emit a digest sized to a token budget",
        ],
        roles=["n/a -- a generator consumed by a fan-out prompt"],
        tools=[
            "repo_map.py (stdlib-only, deterministic)",
            "--budget / --out flags",
            "NO embeddings, NO vector store, NO model call",
        ],
        stop_rules=["token budget is the terminating constraint (--budget)"],
        failure_behaviour="Deterministic: 'same tree in, same bytes out'. No retry surface.",
        benchmark="Quotes the A11 measurement it mechanises: 16/25 agents read the same file, 13/25 the same doc, one agent re-read hub.py x22; estimated 60-90 tool calls removed per 39-agent workflow. That is a PRIOR measurement quoted by the README, NOT a benchmark of this tool, and NOT re-measured here.",
        rationale="Wrapper needed: rule A11 warns the emitted path is repo-relative -> pass the ABSOLUTE form, or fan-out agents get 'Read failed' cwd confusion (the exact 10-failure class A12 records).",
    ),
    "tool-triage-router": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="Cost-tier routing for mechanical/cheap units. LOW fit for substantive units on this estate because of a standing owner preference conflict.",
        stages=[
            "read static code-health metrics of the target files",
            "map health score -> complexity budget",
            "emit cheapest sufficient tier",
            "escalate one tier on a failed verification gate",
        ],
        roles=["routes TO tiers: haiku / sonnet / opus"],
        tools=[
            "triage_router.py CLI + importable module",
            "--files / --health-score / --escalate flags",
            "auto-detect health tool (qlty/codacy)",
        ],
        stop_rules=[
            "escalation ladder: --escalate <tier> returns the NEXT tier up after a verification-gate failure (a bounded upward walk, not an unbounded retry)"
        ],
        failure_behaviour="Escalation is the failure path; 4 both-states references in its tests.",
        benchmark="cites arXiv:2604.07494 (three-tier SWE-bench protocol) as its basis. NOT RESOLVED -- no network probe run by this unit; id recorded verbatim.",
        rationale="Wrapper + needs_owner. CONFLICT: the owner's standing preference is Opus for ALL substantive subagents, so a cost-DOWNGRADE router fights it. Adopt only for provably mechanical units, or the routing table becomes a quality regression.",
    ),
    "tool-mutation-gate": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="The gate that distinguishes 'a line ran' from 'a test would notice if that line broke' -- the exact discipline this program's 12-condition predicate claims (condition 8: negative controls fail as expected).",
        stages=[
            "compute diff scope (git diff --name-only <base>...HEAD)",
            "mutate only the touched files",
            "run the test command",
            "fail on any surviving mutant, naming the mutant and the weak suite",
        ],
        roles=["n/a -- a CI/pre-commit gate"],
        tools=[
            "mutation_gate.py (stdlib + one pinned mutation tool)",
            "stryker.config.template.json",
            "sample/ strong+weak fixture pair",
            "--base/--repo-root/--include/--test-command flags",
        ],
        stop_rules=[
            "FAIL if any mutant survives the whole suite",
            "diff-scoped: never mutates the whole tree (the cost control)",
        ],
        failure_behaviour="Names the surviving mutant AND the weak suite that let it live -- actionable, not a bare red.",
        benchmark="Cites the DEFAULT_MIN_BYTES scar: a constant at 100% line coverage with ZERO protection because every test passed the value explicitly. Same scar independently recorded in rules/common/single-signal-verification.md. NOT re-executed by this unit.",
        rationale="Adopt whole. Note the range-internal coincidence I measured: wf-saved-codex-auth-research-fanout's own DONE gate uses a >=1024-byte floor (mjs:27), i.e. the same magic-constant shape as the scar this tool exists to catch. Worth a mutation check on that gate.",
    ),
    "tool-ese-gate": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="The estate's ALREADY-BUILT consensus mechanism, and the natural cheap pre-gate in front of the expensive rtv-pdr tournament (#11), which names it explicitly.",
        stages=[
            "receive N candidate patches via a JSON manifest",
            "isolate (copy workdir per candidate)",
            "apply (unified diff or files-map)",
            "execute the test command",
            "fingerprint (exit code + sorted pass/fail ids)",
            "cluster by behaviour",
            "emit verdict",
        ],
        roles=["one candidate per council model (Claude / Codex / Gemini)"],
        tools=[
            "ese_gate.py CLI",
            "patch -p1 / files-map apply",
            "per-candidate temp workdir",
        ],
        stop_rules=[
            "DEFAULT_THRESHOLD = 0.5 (ese_gate.py:34)",
            "escalate = entropy >= threshold (ese_gate.py:307)",
            "all candidates broken -> escalate REGARDLESS (ese_gate.py:301,309) -- fail-toward-escalation",
            "degenerate inputs escalate rather than pass: no candidates / no test_cmd / workdir not found each return escalate=True (ese_gate.py:370,377,388)",
        ],
        failure_behaviour="Fail-TOWARD-escalation on every degenerate input, which is the safe direction for a gate. Disagreement is measured on EXECUTION-equivalence, not self-reported confidence -- an external falsifiable signal.",
        benchmark="cites arXiv:2603.27098. NOT RESOLVED -- no network probe by this unit. DETERMINISM CHECKED BY THIS UNIT: neither 'random' nor 'time.time' appears anywhere in ese_gate.py, so the escalate decision has no entropy source (functions measured: _behaviour_signature, _cluster_candidates, _normalised_entropy, _build_verdict).",
        rationale="Adopt whole. #11 + #21 is the strongest COMPOSE pair in this range: ESE decides cheaply whether a unit is contentious, rtv-pdr pays the N-Opus tournament cost only when it is.",
    ),
    "tool-detector-self-test": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Mechanises the both-states rule for the program's OWN instruments -- i.e. it is the gate that would have caught my own broken 28-id detector earlier in this unit.",
        stages=[
            "run each detector against a known-BROKEN fixture",
            "run it against a known-FIXED fixture",
            "assert the two disagree in the right direction",
        ],
        roles=["n/a -- a harness self-test gate"],
        tools=[
            "detector_self_test.py",
            "examples/{debug_print,todo_marker}/{broken,fixed}/ fixture pairs",
            ".coveragerc",
            "12 files",
        ],
        stop_rules=[
            "FAIL on 'silent-in-both' (detector never fires) and on 'firing-in-both' (signal is noise)"
        ],
        failure_behaviour="Explicitly names the two silent failure modes it exists to catch; 22 both-states references measured.",
        benchmark="README states 100% line coverage catches NEITHER failure mode. NOT re-executed by this unit.",
        rationale="Adopt whole, and apply it to this program's own gates. Live evidence from this very unit: my first VIOLATIONS counter returned 0 against a true value of 28 -- a detector that was silent in the present state. This tool is the mechanical fix for that class.",
    ),
    "tool-harness-corpus": dict(
        classification="EXTEND",
        prior="EXTEND",
        task_fit="Distils ~10.6 GB of session JSONL into a bounded corpus. The EXTENSION this program needs is exactly the gap the prior pass named: it mines transcripts, NOT workflow run records.",
        stages=[
            "stream JSONL",
            "scan by record type",
            "aggregate into a bounded corpus",
        ],
        roles=["n/a -- a miner"],
        tools=[
            "mine.py (streaming, bounded-memory, fail-soft, read-only)",
            "test_hook_telemetry.py",
        ],
        stop_rules=["bounded-memory streaming; no round/retry semantics"],
        failure_behaviour="fail-soft on malformed records. Carries a documented DETECTOR defect and its fix: mine.py previously reported hooks:{} across the whole corpus and published DETECTOR_STATUS: BROKEN, from which the WRONG conclusion ('hooks write no durable telemetry') was drawn. Root cause was a nesting error -- the key `hookName` was correct but lives one level down on a record type scan() never inspected (0 matches in 1.56M lines).",
        benchmark="~10.6 GB corpus scale; 1.56M lines cited for the defect. NOT re-run by this unit.",
        rationale="EXTEND to mine workflow RUN RECORDS (projects/*/*/workflows/*.json), which is the reservoir the prior archaeology left largely unread (259 of 329 surviving scripts). Its own hooks:{} scar is a textbook instance of the rule that an unproven zero is a detector failure.",
    ),
    "tool-monitorcore": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="ADOPT-WITH-WRAPPER",
        task_fit="Domain-neutral monitoring/export core: a new monitor gets status/notify/export by implementing ONE contract. Relevant to observing a 2,007-unit run.",
        stages=[
            "poll -> Snapshot (per-adapter typed contract that never throws)",
            "render (ReportDoc -> md/html)",
            "export",
            "headline/alert",
        ],
        roles=["MonitorSource adapters (agents, codex, databricks, mcp, health)"],
        tools=[
            "103 files / 988,885 bytes",
            "redact (fail-closed, strict-by-default secret + home-path masking)",
            "textsafe (ANSI-strip, HTML-escape, UTF-8-safe truncation)",
            "timeline IR",
            "PDF engine ladder (Typst -> Playwright -> headless -> HTML)",
            "watchdog/discovery/spawn",
        ],
        stop_rules=[
            "stall.py exists as a module; the contract is poll-based with no terminating predicate of its own"
        ],
        failure_behaviour="The contract's poll 'never throws' by construction; MANDATORY redaction at ingest for codex primitives.",
        benchmark="none numeric. README describes an 11-PR roadmap with PR-A shipped (wfmon export).",
        rationale="Wrapper for two measured reasons: (1) it is the largest tree in the range (103 files) so adopt only the contract + redact + textsafe, not the cockpit UI; (2) a vendored duplicate exists inside .agents/skills/workflow-monitor/monitorcore/, so adoption must pick ONE home or add a third copy. NOTE for readers: rules/common/fan-out-contract A5 records tools/monitorcore as main-only, which cost 7 agents independent rediscovery -- read it via `git cat-file -p <ref>:tools/monitorcore/...`, not a working-tree path.",
    ),
    "tool-event-ledger": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Append-only typed event ledger that hooks write continuously and recovery replays as ground truth -- the durable-decision substrate AGENTS.md S3 already depends on.",
        stages=[
            "append(project, kind, **fields) every turn (Stop hook)",
            "replay(project, n) on resume/compact/clear (SessionStart hook)",
            "state(project)",
        ],
        roles=[
            "Stop hook (per-turn objective harvest: git HEAD/branch/dirty)",
            "SessionStart hook (inject ground-truth tail)",
            "note.py (manual durable decision/failure entry)",
        ],
        tools=[
            "ledger.py (stdlib core)",
            "stop-hook.py",
            "sessionstart-replay.py",
            "note.py",
            "test_ledger.py",
            "storage under ~/.claude/event-ledger/<project-slug>",
        ],
        stop_rules=[
            "record-only, exit 0 always; honors stop_hook_active so it NEVER loops"
        ],
        failure_behaviour="Failure entries are first-class (failure-aware by design) and a milestone can --supersede a failure so a dead end is retired rather than re-walked. Fail-open: exit 0.",
        benchmark="none numeric. Rationale documented: PreCompact does not fire on /clear (CC #13572), which the SessionStart replay covers.",
        rationale="Adopt whole. DRIFT WARNING measured in its own README: 'Deployed at ~/.claude/hooks/event-ledger/ (this is the versioned copy -- keep in sync)' -- i.e. it is a two-copy artifact and the repo copy is authoritative.",
    ),
    "tool-memory-bench": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Turns 'memory feels useful' into a measured pass-rate. The only candidate in this range with a reproducible numeric baseline committed alongside the code.",
        stages=[
            "load probes.jsonl",
            "query basic-memory per probe",
            "score with a deterministic substring/abstention scorer",
            "aggregate per ability-class",
        ],
        roles=[
            "five recall ability-classes: information-extraction, multi-session-temporal, knowledge-update, abstention, contradiction"
        ],
        tools=[
            "memory_bench.py",
            "probes.jsonl",
            "results.json (committed baseline)",
            "NO LLM-as-judge (explicitly rejected as a same-context placebo)",
        ],
        stop_rules=["fixed probe set; deterministic scorer -> no convergence loop"],
        failure_behaviour="Deterministic scoring; abstention is a scored class, so 'not found' is a CORRECT answer rather than a failure.",
        benchmark="MEASURED BY THIS UNIT: results.json parses to overall_pass_rate=0.8125, passed=13, total=16 -> 81.25%, exactly matching the README claim of '13/16 = 81.25%'. Per-class re-read: abstention 3/3, knowledge-update 3/3, information-extraction 4/5, multi-session-temporal 2/3, contradiction 1/2. Second independent signal: probes.jsonl contains exactly 16 non-blank rows, matching total=16. Cites arXiv:2410.10813 (LongMemEval) -- NOT RESOLVED, no network probe.",
        rationale="Adopt whole. The weakest measured class is contradiction (1/2), which is precisely the temporal-validity/superseded-by problem this program's registry must not repeat.",
    ),
    "tool-harness-drift": dict(
        classification="ADOPT-AS-IS",
        prior="UNKNOWN-NEEDS-PROBE",
        task_fit="DIRECTLY ADDRESSES A NAMED SUBSTRATE DEFECT IN THIS PROGRAM'S BRIEF: 'rules/ live-vs-repo drift is TWO-DIRECTIONAL (5/88 identical); no safe sync direction exists yet.' This tool is the deterministic two-directional differ that decides that question.",
        stages=[
            "walk the LIVE harness tree and the repo tree",
            "normalise line endings (CRLF/CR -> LF, drop BOM)",
            "difflib.SequenceMatcher every non-identical pair",
            "record BOTH only_repo and only_live line counts",
            "classify",
        ],
        roles=["n/a -- a deterministic differ"],
        tools=["harness_drift.py", "test_harness_drift.py", "difflib (stdlib)"],
        stop_rules=[
            "REPO-AHEAD requires only_live == 0",
            "LIVE-AHEAD requires only_repo == 0",
            "anything else is DIVERGED (errs toward DIVERGED by construction)",
            "byte-different but normalised-identical is NOISE-ONLY",
        ],
        failure_behaviour="Errs toward DIVERGED: a moved (not edited) block reads as both an insert and a delete, so it over-reports divergence rather than under-reporting it -- the safe error direction for a decision that can delete content.",
        benchmark="Its docstring cites the measurement that justifies it: an LLM fan-out classifying the same 338 files scored 86% with 100% of the errors in the DANGEROUS direction -- 31 files called deploy-safe that were actually two-way DIVERGED, because the agents read one-directionally. NOT re-executed by this unit.",
        rationale="I RE-CLASSIFY from the prior pass's UNKNOWN-NEEDS-PROBE to ADOPT-AS-IS. The prior pass marked it unknown solely because it has no README ('git show returned nothing'); I read harness_drift.py itself and its module docstring is a complete specification. This is the highest-value re-classification in my range: the program currently records 'no safe sync direction exists yet' as an open defect, and the tool that resolves it was sitting unread.",
    ),
    "tool-d001-dual-write": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="Filter-safe mirroring of the same blobs between two skill roots using git plumbing only -- the safe primitive for any repo->live projection this program performs.",
        stages=[
            "resolve source blobs",
            "mirror onto the target path via plumbing",
            "never materialise a second working tree",
        ],
        roles=["n/a -- an applier"],
        tools=[
            "d001_apply.py",
            "git plumbing only (no second worktree, no index restore, no content-filter round-trip)",
            "tests/d001_fixtures.py",
        ],
        stop_rules=[
            "protected paths are never opened for write -- their bytes AND mtime are unchanged by a full run (a falsifiable postcondition)"
        ],
        failure_behaviour="Fail-safe by construction against a specific measured hazard: the repo encrypts tools/mcp/*/accounts.json with git-crypt, and every materialising git operation writes through the filter's smudge side. If the filter has been reduced to an identity passthrough -- a state this repository was MEASURABLY in -- a second working tree writes STORED (encrypted) bytes over protected paths, and narrowing a later step does not help because the tree is already corrupt.",
        benchmark="none numeric. 17 both-states references measured.",
        rationale="Adopt whole. Its hazard analysis is a direct, in-repo instance of the estate's own credential-safety rules; any sync this program performs should route through it rather than hand-copying.",
    ),
    "tool-mcp-manager": dict(
        classification="ADOPT-AS-IS",
        prior="ADOPT-AS-IS",
        task_fit="LOW task fit for a workflow-orchestration platform: it is an MCP fleet control plane (inventory + PySide6 GUI), surfaced live as /mcp-gui. Included for completeness of the index range, not because it carries a workflow mechanism.",
        stages=["inventory three planes", "preset select", "apply bulk enable/disable"],
        roles=[
            "Claude plane (~/.claude.json)",
            "Codex plane (~/.codex/config.toml)",
            "Funnel plane (~/.mcp-funnel-profiles.json)",
        ],
        tools=[
            "app.py + ui/ (PySide6)",
            "core/{adapters,inventory,presets,loadout,status,surface_census,consolidation}.py",
            "42 files",
            "install.ps1 / launch.ps1",
        ],
        stop_rules=["none -- interactive tool"],
        failure_behaviour="Documents a hard timing constraint rather than pretending to solve it: 'MCP servers spawn once at session start. Every config change here applies to the NEXT session -- restart Claude Code to take effect. Nothing in this tool toggles a running session live.'",
        benchmark="none.",
        rationale="Adopt as-is for its own domain; explicitly NOT a workflow-orchestration mechanism. Flagged low-fit so a later phase does not mistake it for one.",
    ),
    "tool-mcpctl": dict(
        classification="ADOPT-AS-IS",
        prior="UNKNOWN-NEEDS-PROBE",
        task_fit="Its DOMAIN (MCP inventory) is low-fit, but it carries a HIGH-fit reusable MECHANISM: read-only-BY-CONSTRUCTION enforced mechanically over the AST of every module, rather than by a promise in prose.",
        stages=[
            "sources (read the five on-disk MCP scopes)",
            "resolve",
            "topology",
            "matrix (health/status)",
            "render",
        ],
        roles=["n/a -- a read-only CLI + pure-function core"],
        tools=[
            "python -m mcpctl {topology,credentials,conflicts,matrix --json}",
            "23 files",
            "tests/test_safety_contract.py",
            "tests/test_mutations.py (31 mutation refs)",
            "credential-NAME-only redaction",
        ],
        stop_rules=[
            "no enable/disable, no reconnect, no config edit, no file write anywhere in the package -- asserted mechanically, not trusted"
        ],
        failure_behaviour="'tests/test_cli.py asserts that mechanically over the AST of every module (no write call, no out-of-process call) rather than trusting this sentence.' Emits an observation envelope with machine-readable rows.",
        benchmark="none numeric. 16 terminal-state markers and 8 stop-condition references measured.",
        rationale="I RE-CLASSIFY from UNKNOWN-NEEDS-PROBE to ADOPT-AS-IS (the prior pass recorded 'present; unread'; I read the README and module list). Adopt the AST-ASSERTED-PROPERTY pattern for this program's own read-only agents -- it is the mechanical form of a scope promise that a prompt cannot enforce.",
    ),
    "tool-mcpapply": dict(
        classification="ADOPT-AS-IS",
        prior="UNKNOWN-NEEDS-PROBE",
        task_fit="Low-fit domain, high-fit mechanisms: an explicit PLAN -> APPLY separation with a pure planner, a fail-closed write guard, a timestamped backup that prints its own restore command, and an impact preview that refuses to render 'not measured' as 0.",
        stages=[
            "plan (current -> desired -> explicit diff; pure)",
            "guard (fail-closed write preconditions)",
            "backup (timestamped sidecar + printed restore command)",
            "apply (through an injected filesystem port)",
            "live (stream-json control_request behind an injected transport port)",
        ],
        roles=[
            "planner (pure)",
            "guard",
            "applier",
            "live-control channel",
            "loopback-only web GUI",
        ],
        tools=[
            "25 files",
            "mcpapply/{plan,apply,guard,backup,live,impact,server}.py",
            "tests/test_mutations.py (47 mutation refs)",
            "stdlib-only loopback GUI (no framework, no CDN, no daemon)",
        ],
        stop_rules=[
            "fail-closed write preconditions: a running host and a USER-scope human gate must both be satisfied before any write",
            "14 stop_condition references measured",
        ],
        failure_behaviour="Fail-CLOSED on writes (the safe direction), timestamped backup before mutation with the restore command printed, and impact.py 'never renders not measured as 0' -- i.e. it refuses to report an unmeasured quantity as a real zero, which is the same anti-pattern this program's honesty contract forbids.",
        benchmark="none numeric.",
        rationale="I RE-CLASSIFY from UNKNOWN-NEEDS-PROBE to ADOPT-AS-IS. The read/write split with mcpctl is deliberate and load-bearing: 'the writer, the process probe and the GUI would each break the mechanical gate that makes mcpctl true.' #30 and #31 are therefore a designed PAIR, not a fork -- material distinctness confirmed by disjoint module sets and opposite AST assertions.",
    ),
    "tool-otel-traces": dict(
        classification="ADOPT-WITH-WRAPPER",
        prior="UNKNOWN-NEEDS-PROBE",
        task_fit="Would give a latency-resolved span tree across tool/permission/hook/subagent/Bash boundaries -- the forensic view for a stalled orchestration run. BUT its own notes disqualify the primary use case for this program.",
        stages=[
            "start a local Jaeger all-in-one via Docker (OTLP http)",
            "print env vars to launch claude with enhanced trace export",
            "capture spans on demand",
        ],
        roles=["n/a -- a one-shot PowerShell enabler (44 lines, single file)"],
        tools=[
            "enable-otel-traces.ps1",
            "Docker (required)",
            "Jaeger UI (default port 16686) + OTLP (4318)",
            "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA",
        ],
        stop_rules=[
            "ON-DEMAND ONLY by instruction: 'do not leave telemetry always-on'"
        ],
        failure_behaviour="DOCUMENTED DEFECT, quoted verbatim from the file: 'native batching can lose the tail if the CLI is killed mid-run; for long/killable Ralph loops prefer the cc-trace hook (records per-tool, exports on Stop) instead of this native path.' Also beta-gated: 'span names/attributes may churn -- pin a CC version when you rely on it.'",
        benchmark="none.",
        rationale="I RE-CLASSIFY from UNKNOWN-NEEDS-PROBE to ADOPT-WITH-WRAPPER, but with a warning that matters for THIS program: long orchestration runs are exactly the killable case whose tail this path loses, and the file itself prescribes the cc-trace hook instead. The wrapper IS that fallback. Adopting this alone would give a trace that is silently truncated precisely when a run dies -- the failure mode you most need it for.",
    ),
}

# ---------------------------------------------------------------- assemble
rows = []
for cid, j in J.items():
    s = SCAN[cid]
    assert j["classification"] in VOCAB, f"bad verdict {j['classification']}"
    mech = {k: v for k, v in (s.get("scan") or {}).items() if v}
    prov_kind = s["kind"]
    if prov_kind == "file-live":
        anchor = s["provenance_claim"]
        commit_date = None
        mt = s.get("fs_mtime")
    else:
        anchor = f"{REF}:{s['mirror_path']}  (bare mirror {MIRROR})"
        commit_date = last_commit(s["mirror_path"])
        mt = None
    rows.append(
        {
            "id": cid,
            "n": s["n"],
            "name": s["name"],
            "family": s["family"],
            "classification": j["classification"],
            "classification_prior_pass": j["prior"],
            "classification_changed": j["classification"] != j["prior"],
            "classification_rationale": j["rationale"],
            "provenance": {
                "anchor": anchor,
                "kind": prov_kind,
                "resolved": True,
                "resolution_probe": (
                    "os.path.exists + os.stat"
                    if prov_kind == "file-live"
                    else "git --git-dir <mirror> cat-file -t <ref>:<path>"
                ),
                "bytes": s.get("fs_bytes") or s.get("tree_total_bytes"),
                "lines_measured": s.get("measured_lines"),
                "tree_file_count": s.get("tree_file_count"),
                "body_sha256_16": s.get("body_sha256"),
            },
            "license": LICENSE_TEXT,
            "license_source": LICENSE_SRC,
            "maintenance_state": {
                "last_commit_at_ref": commit_date,
                "live_file_mtime": mt,
                "ref": REF,
                "ref_committed": "2026-08-03",
                "note": (
                    "live-tree artifact: mtime only, no commit history (these paths are NOT versioned)"
                    if prov_kind == "file-live"
                    else "last commit that touched this path at or before the pinned ref"
                ),
            },
            "task_fit": j["task_fit"],
            "stages": j["stages"],
            "roles": j["roles"],
            "tools": j["tools"],
            "stop_rules": j["stop_rules"],
            "failure_behaviour": j["failure_behaviour"],
            "benchmark_evidence": j["benchmark"],
            "mechanism_scan_measured": mech,
            "phase_names_measured": s.get("phase_names") or None,
            "prior_pass_fields": {
                "does": s.get("prior_does"),
                "mechanisms": s.get("prior_mechanisms"),
                "evidence": s.get("prior_evidence"),
                "notes": s.get("prior_notes") or None,
            },
        }
    )

rows.sort(key=lambda r: r["n"])
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=2, ensure_ascii=False)
print(f"wrote {OUT} rows={len(rows)}")
print(
    "changed classifications:",
    [
        (r["id"], r["classification_prior_pass"], r["classification"])
        for r in rows
        if r["classification_changed"]
    ],
)
