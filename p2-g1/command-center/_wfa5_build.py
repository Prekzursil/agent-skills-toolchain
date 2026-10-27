"""build/wfa-5 : assemble the final machine-readable registry for candidates 129-160.

Every measured field comes from the probe artifacts in this directory:
  _wfa5_resolve.json   - on-disk resolution of all 32 rows (32/32, detector-controlled)
  _wfa5_skillfeat.json - stages/roles/tools/stop-rules/failure/usage/nearest-neighbour
  _wfa5_drift.json     - LF-normalised digests per copy (EOL control both ways)
  _wfa5_licence.json   - frontmatter, attribution lines, LICENSE file heads
  _wfa5_verify.json    - the 6 targeted verification probes
Curated per-candidate judgement (classification + basis) is in DECISIONS below; every
entry names the evidence it rests on.
"""

import datetime
import json
import os
import re

REPO = "C:/Users/Prekzursil/source/ast-integrate"
CC = os.path.join(REPO, "command-center")
OUT = os.path.join(REPO, "platform", "registry", "workflow-candidates-5.json")
METHOD = os.path.join(REPO, "platform", "registry", "workflow-candidates-5.METHOD.json")
PINNED = "07f465f37d49710f7060dcc7b567d6c58213177b"
HEAD = "53c37c6cfb3e7bd1a48edbe604e1ea06a77b50b1"


def load(n):
    with open(os.path.join(CC, n), encoding="utf-8") as fh:
        return json.load(fh)


feat = {r["registry_index"]: r for r in load("_wfa5_skillfeat.json")["rows"]}
drift = {r["registry_index"]: r for r in load("_wfa5_drift.json")["rows"]}
lic = {r["registry_index"]: r for r in load("_wfa5_licence.json")}
ver = load("_wfa5_verify.json")

ECC_UNKNOWN = {
    "declared": "none in the artifact; frontmatter carries `origin: ECC` only",
    "spdx": None,
    "source_anchor": "frontmatter `origin:` line of the SKILL.md cited in provenance",
    "verdict": "SUMMARISE-ONLY (unknown upstream terms)",
    "verdict_basis": (
        "ECC is named as the origin but no licence text, URL or NOTICE for it exists "
        "anywhere on disk: a 529-file search of the repo markdown, root LICENSE/NOTICE "
        "globs, skills/*/SKILL.md and the two live vault roots returned 5 'ECC' hits, ALL "
        "of them in one unrelated gap-analysis document with no licence and no URL "
        "(_wfa5_verify.json P2_upstream_term_search). Settling experiment: locate the ECC "
        "upstream repository and read its LICENSE; until then the text is not "
        "redistributable and only the principle may be re-expressed in our own words."
    ),
}

DECISIONS = {
    129: dict(
        classification="TRANSLATE",
        basis=(
            "Eight named gates G0-G7 plus a mode router and a KEEP/REVERT revert-gate are "
            "all expressible in the shipped DSL: stages, gates, subworkflows (each mode "
            "jumps to a leaf skill), loops_with_convergence, human_checkpoints and "
            "failure_policy are mandated capabilities in "
            "platform/schema/workflow-dsl.capability-map.json. The deliverable is the "
            "declarative workflow, not 26,046 bytes of prose."
        ),
        task_fit=[
            "design-review",
            "ui-quality",
            "multi-stage-gated-loop",
            "code-to-canvas",
        ],
        mechanisms=[
            "8-gate loop",
            "mode router",
            "revert gate",
            "leaf-skill delegation",
        ],
        dsl=[
            "stages",
            "gates",
            "subworkflows",
            "loops_with_convergence",
            "human_checkpoints",
            "failure_policy",
        ],
        post=None,
    ),
    130: dict(
        classification="REPAIR",
        basis=(
            "MEASURED content defect. The two live deployments differ on 5 lines and three "
            "of them replace the word Claude with Codex: .agents SKILL.md:10 reads 'loop and "
            "Codex + Codex as rival suggesters' where .claude SKILL.md:10 reads 'Claude + "
            "Codex'; the same substitution hits :23 ('by:Codex|codex' vs 'by:claude|codex') "
            "and the :3 description. Cross-vendor rivalry IS this skill's load-bearing "
            "mechanism, so the .agents copy encodes a same-vendor council - the exact shared "
            "blind-spot failure the estate's own contract warns about. Repair, then adopt."
        ),
        task_fit=[
            "interactive-restyle",
            "element-to-source",
            "micro-commit",
            "dual-vendor-council",
        ],
        mechanisms=[
            "preview-then-apply",
            "micro-commit",
            "revert gate",
            "file-lease",
            "escalate-on-disagreement",
        ],
        dsl=["stages", "human_checkpoints", "gates", "roles", "failure_policy"],
        post="TRANSLATE once the vendor naming is restored and the two live copies are reconciled",
    ),
    131: dict(
        classification="REPAIR",
        basis=(
            "THREE distinct LF-normalised content versions exist simultaneously "
            "(live ~/.agents, live ~/.claude, and the repo pair which agrees with the pinned "
            "07f465f3 blob) - see the digests in _wfa5_drift.json. With no canonical byte-set "
            "the question 'which ui-audit does the platform adopt' has no answer, so reconcile "
            "is a precondition, not a follow-up. The engine itself is the richest deterministic "
            "gate in this slice (5 capture/lint/dead-button/axe/visual gates plus a 9-dimension "
            "DESIGN-EVAL rubric and an optional cross-vendor critic)."
        ),
        task_fit=[
            "accessibility-audit",
            "visual-regression",
            "design-quality-verdict",
            "dead-control-detection",
        ],
        mechanisms=[
            "two-track audit",
            "rubric scoring",
            "cross-vendor critic",
            "baseline diff",
        ],
        dsl=["stages", "gates", "tools", "artifact_caching", "model_routing"],
        post="ADOPT-WITH-WRAPPER (pin the vendored playwright/axe versions and expose the run as one DSL tool stage)",
    ),
    132: dict(
        classification="REPAIR",
        basis=(
            "Three distinct content versions live at once (live ~/.agents, live ~/.claude, "
            "repo+pinned) - same no-canonical-bytes blocker as ui-audit. This is also the "
            "single most-used candidate in the slice (58 executed workflow scripts and 108 run "
            "records name it; 169 repo files reference it), so adopting the wrong copy has the "
            "widest blast radius of anything here."
        ),
        task_fit=[
            "multi-source-research",
            "provider-routing",
            "citation-grading",
            "evidence-synthesis",
        ],
        mechanisms=[
            "provider preflight",
            "role-scoped routing",
            "query cache",
            "two-axis source grading",
            "FACT/RACE verification",
        ],
        dsl=["stages", "tools", "artifact_caching", "source_policy", "dynamic_fanout"],
        post="ADOPT-WITH-WRAPPER (the preflight at SKILL.md Step 2.5 is the seed of the wrapper the platform needs)",
    ),
    133: dict(
        classification="DISTILL",
        basis=(
            "1,955 bytes, 2 headings, zero measured stages, roles, tools or stop rules: the "
            "artifact is a pointer table that routes to deep-research ('The synthesis engine is "
            "deep-research', SKILL.md:10). Routing is the DSL's job (subworkflows + tool_policy), "
            "so the route table is what survives and the prose does not."
        ),
        task_fit=["research-routing"],
        mechanisms=["route table", "operator entry point"],
        dsl=["subworkflows", "tools"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    134: dict(
        classification="CLEAN-ROOM-REIMPLEMENT",
        basis=(
            "The mechanism is wanted whole - a 6-step search-before-you-build ladder (capture "
            "intent, search local, search remote, vet external, rank, present options) - but the "
            "text's provenance is 'salvaged from stale community PR #1232 by redminwang' "
            "(SKILL.md:13) with `origin: community` and no licence anywhere on disk. Rebuild the "
            "six steps from this description rather than carrying unlicensed third-party text."
        ),
        task_fit=["prior-art-search", "duplicate-avoidance", "candidate-ranking"],
        mechanisms=[
            "local-then-remote search ladder",
            "adversarial vetting",
            "ranked decision options",
        ],
        dsl=["stages", "tools", "human_checkpoints", "source_policy"],
        post=None,
        license={
            "declared": "none; frontmatter `origin: community`",
            "spdx": None,
            "source_anchor": "SKILL.md:4 (`origin: community`) and SKILL.md:13 (salvage note)",
            "verdict": "EXCLUDE (unknown terms on third-party contributed text)",
            "verdict_basis": (
                "The only provenance is a person's name and a PR number; a 529-file on-disk "
                "search found one hit for 'redminwang' - the salvage note itself - and no "
                "licence. Settling experiment: identify the upstream repository that carried "
                "PR #1232 and read its contribution terms."
            ),
        },
    ),
    135: dict(
        classification="TRANSLATE",
        basis=(
            "Four explicitly numbered phases (Inventory, Quality Evaluation by sequential "
            "subagent batches, Summary Table, Consolidation), two declared modes (Quick Scan / "
            "Full Stocktake) and a documented results-file schema. That is stages + typed_params "
            "+ dynamic_fanout + barriers in the DSL, with nothing left over."
        ),
        task_fit=["portfolio-audit", "batch-evaluation", "inventory"],
        mechanisms=[
            "inventory pass",
            "batched subagent evaluation",
            "summary table",
            "consolidation",
        ],
        dsl=["stages", "typed_params", "dynamic_fanout", "barriers"],
        post=None,
    ),
    136: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "The only candidate in the slice that declares a licence in its own frontmatter "
            "(`license: MIT`, SKILL.md:4) and needs no adaptation: it is an operator procedure "
            "with a named root cause (UI toggle writes PROJECT scope, so a disable returns when "
            "the cwd changes) plus a periodic drift audit. The platform consumes it unchanged."
        ),
        task_fit=["catalogue-hygiene", "config-scope-discipline", "drift-audit"],
        mechanisms=[
            "user-scope disable",
            "reversible park/restore",
            "periodic drift audit",
        ],
        dsl=["tools"],
        post=None,
        license={
            "declared": "MIT",
            "spdx": "MIT",
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/mcp-fleet-curation/SKILL.md:4",
            "verdict": "REDISTRIBUTABLE",
            "verdict_basis": "SPDX-recognised permissive licence declared in the artifact itself.",
        },
    ),
    137: dict(
        classification="ADOPT-WITH-WRAPPER",
        basis=(
            "The mechanism lives in an EXTERNAL runtime (a DevFleet MCP: plan -> dispatch -> "
            "monitor -> report, with per-agent worktree isolation), so the platform can only "
            "reach it through an adapter. The skill documents its own blocking hazard - "
            "`wait_for_mission` blocks the conversation for up to timeout_seconds, default 600 "
            "(SKILL.md:54) - so the wrapper must poll `get_mission_status` instead of blocking."
        ),
        task_fit=[
            "parallel-implementation",
            "worktree-isolated-fanout",
            "mission-monitoring",
        ],
        mechanisms=[
            "worktree fan-out",
            "mission state machine",
            "structured report contract",
            "poll-not-block",
        ],
        dsl=["dynamic_fanout", "barriers", "resume", "failure_policy"],
        post=None,
        license={
            "declared": "none; frontmatter `origin: community`",
            "spdx": None,
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/claude-devfleet/SKILL.md:4",
            "verdict": "NEEDS-OWNER-DECISION",
            "verdict_basis": (
                "The doc text is community-sourced with no licence on disk; the MECHANISM is "
                "reachable through the MCP's own API, so the platform can wrap the API without "
                "redistributing this text. Which of the two the release ships is an owner call."
            ),
        },
    ),
    138: dict(
        classification="ADOPT-WITH-WRAPPER",
        basis=(
            "Five named orchestration patterns over an external tool whose terms ARE established "
            "- standardagents/dmux, MIT (SPDX MIT via the GitHub API, 1,733 stars, 138 forks, "
            "pushed 2026-07-09, updated 2026-08-09, not archived). Blocking precondition measured "
            "on this box: neither `dmux` nor `tmux` resolves on PATH (shutil.which -> None for "
            "both, in the same call where npx.CMD DID resolve, so the .CMD-shim blind spot is "
            "ruled out). The wrapper must therefore gate on availability, not assume it."
        ),
        task_fit=[
            "parallel-agent-panes",
            "cross-harness-orchestration",
            "test-fix-loop",
        ],
        mechanisms=[
            "pane multiplexing",
            "research+implement split",
            "test-fix loop",
            "cross-harness dispatch",
            "worktree integration",
        ],
        dsl=["dynamic_fanout", "barriers", "tools", "failure_policy"],
        post=None,
        license={
            "declared": "skill text: none (frontmatter `origin: ECC`); external tool: MIT",
            "spdx": "MIT (standardagents/dmux only)",
            "source_anchor": "SKILL.md:25 links github.com/standardagents/dmux; licence read from the GitHub API repo object (license.spdx_id = MIT)",
            "verdict": "SUMMARISE-ONLY for the skill text, REDISTRIBUTABLE for the tool dependency",
            "verdict_basis": (
                "Two different objects with two different licence positions: the ECC-origin prose "
                "has unknown terms (see the ECC finding), the tool it drives is MIT."
            ),
        },
    ),
    139: dict(
        classification="REPAIR",
        basis=(
            "Three distinct content versions at once (live ~/.agents == repo .agents/skills, "
            "live ~/.claude alone, and repo skills/ == pinned) - no canonical byte-set. It also "
            "carries the slice's only RIDER-restricted dependency, which makes picking the right "
            "copy a licence question and not only a hygiene one."
        ),
        task_fit=["cross-vendor-fanout", "peer-messaging", "advisory-file-leases"],
        mechanisms=[
            "codex-as-MCP rail",
            "shared HTTP mailbox",
            "file leases",
            "contact handshake",
        ],
        dsl=["roles", "tools", "subworkflows", "failure_policy"],
        post="ADOPT-AS-IS once one copy is made canonical",
        license={
            "declared": "skill text: none; dependency mcp_agent_mail: MIT + an OpenAI/Anthropic rider",
            "spdx": "MIT-with-rider (non-standard)",
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/multi-ai-mingle/SKILL.md:108 and :113 (pinned to commit 35e774fa9ae636c6e1662ab7925d7e68938bb718)",
            "verdict": "NEEDS-OWNER-DECISION (rider-restricted)",
            "verdict_basis": (
                "A permissive base licence carrying an added restriction is exactly the "
                "'rider normalised to its base licence' failure the release lane names; the "
                "rider must be carried forward verbatim into any licence inventory, not "
                "flattened to MIT."
            ),
        },
    ),
    140: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "The cleanest candidate in the slice: 19 lines, a real LICENSE file next to it (MIT, "
            "Copyright (c) 2026 Matt Pocock) and an inline attribution naming the upstream, and "
            "ZERO drift - all five copies are byte-identical after LF normalisation. Usage is the "
            "highest in the slice by run records (16 executed scripts, 100 run records, 374 repo "
            "files reference the name). Nothing to change."
        ),
        task_fit=["session-handoff", "context-compaction", "typed-handoff-document"],
        mechanisms=["typed handoff document", "reference-not-duplicate rule"],
        dsl=["export_import"],
        post=None,
        license={
            "declared": "MIT",
            "spdx": "MIT",
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/handoff/LICENSE (head: 'MIT License / Copyright (c) 2026 Matt Pocock') and SKILL.md:19",
            "verdict": "REDISTRIBUTABLE WITH ATTRIBUTION",
            "verdict_basis": (
                "Vendored from github.com/mattpocock/skills (repo confirmed live via the GitHub "
                "API: 210,997 stars, updated 2026-08-09, not archived); the MIT notice travels "
                "with the folder, so the attribution obligation is already satisfied on disk."
            ),
        },
    ),
    141: dict(
        classification="TRANSLATE",
        basis=(
            "Five numbered steps, an adversarial review gate, a dependency graph and parallel "
            "steps, plus a declared degradation path ('Degrades gracefully to direct mode when "
            "git/gh is absent', SKILL.md:59). That set maps one-for-one onto stages, gates, "
            "dynamic_fanout and failure_policy; the self-contained per-step context brief is "
            "exactly the DSL's typed_params."
        ),
        task_fit=[
            "multi-session-planning",
            "cold-start-step-briefs",
            "dependency-ordered-build",
        ],
        mechanisms=[
            "step brief",
            "adversarial review gate",
            "dependency graph",
            "parallel steps",
            "graceful degradation",
        ],
        dsl=["stages", "gates", "dynamic_fanout", "typed_params", "failure_policy"],
        post=None,
        license={
            "declared": "none; frontmatter `origin: community`; 'Inspired by antbotlab/blueprint' (SKILL.md:96)",
            "spdx": None,
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/blueprint/SKILL.md:96",
            "verdict": "NEEDS-OWNER-DECISION",
            "verdict_basis": (
                "antbotlab/blueprint is confirmed to exist and be maintained (GitHub API: "
                "created 2026-03-10, updated 2026-07-22, not archived) but its LICENCE was "
                "NOT-CHECKED - the minimal API projection used here omits the license field. "
                "The attribution on disk is idea-level ('inspired by'), which is a weaker "
                "obligation than a code copy, but the terms should be read before release."
            ),
        },
    ),
    142: dict(
        classification="EXTEND",
        basis=(
            "Its acceptance rule is a fault-injection self-test - a forged hook 'is not done "
            "until a fault-injection self-test proves it actually fires' (SKILL.md:14) - plus "
            "mandatory fail-open on error (SKILL.md:28). The shipped DSL cannot type that: "
            "gate_spec.predicate enumerates exactly {completion-predicate-v1, quality-gate, "
            "coverage-threshold, reviewer-pass, custom-expression} and the whole schema contains "
            "no negative_control or mutation token, so a fault-injection proof can only be "
            "smuggled in as an untyped custom-expression even though completion-predicate "
            "condition 8 demands that evidence. Adopting this mechanism means EXTENDING the DSL "
            "with a typed negative-control stage/gate kind."
        ),
        task_fit=["hook-authoring", "behaviour-forging", "self-test-gated-install"],
        mechanisms=[
            "one-pass scaffold",
            "fault-injection self-test gate",
            "fail-open guarantee",
            "halt predicate",
        ],
        dsl=["gates", "tools", "stages"],
        dsl_gap="no typed negative-control / fault-injection gate kind (gate_spec.predicate enum, workflow-dsl.schema.json)",
        post=None,
    ),
    143: dict(
        classification="TRANSLATE",
        basis=(
            "A three-part pipeline - synthesize a PRD from conversation+codebase, STOP at the "
            "design-review gate ('STOP at the Design Review Gate ... PM, Architect, ...', "
            "SKILL.md:20), then publish as tracked agent-ready work - i.e. stages + a blocking "
            "human/council checkpoint + an export step. The licence obligation is already "
            "discharged on disk, so nothing blocks re-expressing it declaratively."
        ),
        task_fit=["spec-synthesis", "gated-publication", "issue-generation"],
        mechanisms=[
            "PRD template",
            "blocking design-review gate",
            "tracked-work publication",
        ],
        dsl=["stages", "human_checkpoints", "gates", "export_import"],
        post=None,
        license={
            "declared": "MIT (idea adapted; workspace-native rebuild)",
            "spdx": "MIT",
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/to-prd/LICENSE and SKILL.md:71",
            "verdict": "REDISTRIBUTABLE WITH ATTRIBUTION",
            "verdict_basis": (
                "The artifact states it is a workspace-native rebuild of the mattpocock/skills "
                "to-prd idea and ships the MIT notice beside it."
            ),
        },
    ),
    144: dict(
        classification="DISTILL",
        basis=(
            "Its core act - sort every skill/command/rule/hook into DAILY vs LIBRARY - is a "
            "MECHANICAL two-bucket classification, and it hands that to 'parallel repo-aware "
            "review passes'. On this estate that exact substitution was measured at 86% accuracy "
            "with 100% of the errors pointing one way (rules/common/fan-out-contract.md C4), so "
            "the durable value is the evidence table plus the DAILY/LIBRARY model; the classifier "
            "itself should be deterministic code with agents reserved for the judgement calls."
        ),
        task_fit=["install-plan", "context-budget", "bundle-trimming"],
        mechanisms=[
            "evidence table",
            "DAILY/LIBRARY split",
            "parallel review passes",
            "verify step",
        ],
        dsl=["stages", "dynamic_fanout", "barriers"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    145: dict(
        classification="DISTILL",
        basis=(
            "2,000 bytes of design rules (action-space granularity, observation design, an "
            "error-recovery contract requiring 'explicit stop condition' + 'safe retry "
            "instruction', context budgeting at phase boundaries). No stages, roles, tools or "
            "runnable machinery were measured: the rules are the asset, the prose is not."
        ),
        task_fit=["tool-surface-design", "observation-formatting", "context-budgeting"],
        mechanisms=[
            "action-space granularity rules",
            "error-recovery contract",
            "phase-boundary compaction",
        ],
        dsl=["tools", "roles"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    146: dict(
        classification="CLEAN-ROOM-REIMPLEMENT",
        basis=(
            "The whole capability is wanted - four numbered phases (Scope, Evidence Collection, "
            "Failure Mapping, Fix Strategy) over a 12-layer stack with a severity model and a "
            "declared tool surface in frontmatter - but its `origin: oh-my-agent-check` upstream "
            "could not be found: a GitHub repository search for that exact name returned 4 "
            "results, none of them a repo of that name, and the only on-disk mention is the "
            "frontmatter line itself. Rebuild the phases and the layer taxonomy from this "
            "description instead of shipping unattributable third-party text."
        ),
        task_fit=[
            "agent-stack-diagnosis",
            "hidden-repair-loop-detection",
            "severity-ranked-findings",
        ],
        mechanisms=[
            "12-layer stack model",
            "4-phase audit",
            "severity model",
            "declared tool surface",
        ],
        dsl=["stages", "tools", "gates"],
        post=None,
        license={
            "declared": "none; frontmatter `origin: oh-my-agent-check`",
            "spdx": None,
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/agent-architecture-audit/SKILL.md:4",
            "verdict": "EXCLUDE (upstream unidentifiable)",
            "verdict_basis": (
                "GitHub repository search for 'oh-my-agent-check' returned no repository of that "
                "name (4 unrelated hits), and the on-disk corpus carries no URL or licence. "
                "Settling experiment: ask the owner where oh-my-agent-check came from."
            ),
        },
    ),
    147: dict(
        classification="DISTILL",
        basis=(
            "A four-phase self-debug loop (Failure Capture, Root-Cause Diagnosis, Contained "
            "Recovery, Introspection Report) that the artifact itself says is 'a workflow skill, "
            "not a hidden runtime' (SKILL.md:11). The recovery heuristics table and the "
            "capture-before-retry rule are the transferable parts; the platform's own failure "
            "policy and receipt schema already own the reporting surface."
        ),
        task_fit=["agent-failure-triage", "contained-recovery", "introspection-report"],
        mechanisms=[
            "capture-before-retry",
            "root-cause table",
            "contained recovery",
            "report contract",
        ],
        dsl=["failure_policy", "repair_loops", "stages"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    148: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "18,418 bytes, 17 sections: this is the in-repo authoring contract for the very "
            "lifecycle harness modules the platform builds on (module registration, the stdin "
            "JSON protocol, the `emits` field being descriptive rather than runtime-enforced, "
            "redact-at-store-and-emit). It needs no adaptation; the platform's module authors "
            "are its audience. Recorded defect, not a blocker: it is the ONLY candidate in this "
            "slice deployed to NEITHER live vault, so no running agent can currently read it."
        ),
        task_fit=[
            "harness-module-authoring",
            "hook-check-review",
            "dispatcher-contract",
        ],
        mechanisms=[
            "module registry row",
            "stdin/stdout JSON protocol",
            "redaction discipline",
            "contradiction avoidance",
        ],
        dsl=["tools", "export_import"],
        post=None,
    ),
    149: dict(
        classification="TRANSLATE",
        basis=(
            "It carries a genuine composable stopping rule - 'stop when improvement is within "
            "noise, correctness fails, cost exceeds the ...' (SKILL.md:55) - gated behind a "
            "Required Baseline and closed by a Promotion Gate. That is exactly the DSL's "
            "loops_with_convergence + stopping_rules (ANY/ALL/NOT) + cost_estimate + gates, so "
            "the rule should be re-expressed as a typed stopping expression rather than prose."
        ),
        task_fit=["performance-optimisation", "variant-search", "promotion-gating"],
        mechanisms=[
            "required baseline",
            "variant table",
            "recursive search",
            "noise-aware stop rule",
            "promotion gate",
        ],
        dsl=["loops_with_convergence", "stopping_rules", "cost_estimate", "gates"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    150: dict(
        classification="MERGE",
        basis=(
            "It is a third parallel memory: the estate already runs an objective event ledger "
            "(Stop hook) and a semantic basic-memory vault, and this adds an instinct store with "
            "its own confidence thresholds, hooks and CLI. Its own strongest measured claim is "
            "an argument for merging rather than keeping it separate - 'v1 relied on skills to "
            "observe. Skills are probabilistic - they fire ~50-80% of the time' (SKILL.md:334) "
            "versus hooks at '100% reliable' (SKILL.md:40). Fold the instinct model into the one "
            "hook-fed substrate instead of maintaining three."
        ),
        task_fit=[
            "session-observation",
            "instinct-promotion",
            "project-scoped-learning",
        ],
        mechanisms=[
            "hook-fed observation",
            "confidence scoring",
            "project scoping",
            "instinct-to-skill promotion",
        ],
        dsl=["artifact_caching", "resume", "lineage"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    151: dict(
        classification="MERGE",
        basis=(
            "It declares SIX knowledge layers and an ingestion workflow (classify, deduplicate, "
            "store, index) whose Layer 3 targets an `mcp__memory__*` server that is NOT this "
            "estate's canonical store; the canonical semantic store is basic-memory and the "
            "objective one is the event ledger. The dedupe-then-index pipeline is worth keeping, "
            "so merge it onto the canonical substrate rather than adopting a competing layer map."
        ),
        task_fit=["knowledge-ingestion", "dedupe", "cross-store-sync", "retrieval"],
        mechanisms=[
            "layered store model",
            "classify/dedupe/store/index",
            "redact-before-commit",
        ],
        dsl=["artifact_caching", "source_policy", "stages"],
        post=None,
        license=ECC_UNKNOWN,
    ),
    152: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "It ships a real instrument, not advice: scripts/extract_workflow_agent.py is present "
            "in BOTH the live vault and the repo copy, and it recovers a named subagent's exact "
            "prompt or output from a past fan-out run. That is the only tool in this slice that "
            "can read the estate's largest untapped reservoir (the executed-workflow corpus - 822 "
            "run records and 416 surviving scripts measured today), and it names the trap that "
            "makes naive matching wrong (a synthesizer embeds every upstream agent's report, so a "
            "lens phrase hits two agents; SKILL.md:41)."
        ),
        task_fit=[
            "workflow-archaeology",
            "agent-output-recovery",
            "post-compaction-forensics",
        ],
        mechanisms=[
            "transcript index",
            "identify-by-phrase ladder",
            "bundled extractor tool",
        ],
        dsl=["export_import", "tools", "deterministic_replay"],
        post=None,
    ),
    153: dict(
        classification="DISTILL",
        basis=(
            "25 lines: one rule (name the cheapest falsifiable probe, RUN it, let its result "
            "choose the path) plus an extensible probe table, with a real citation for why the "
            "same-context alternative fails ('intrinsic self-correction degrades reasoning - "
            "Huang et al., ICLR 2024', SKILL.md:8). The rule belongs in the platform's gate "
            "preamble; the table is a lookup, not a workflow."
        ),
        task_fit=["approach-selection", "cost-avoidance", "probe-ordering"],
        mechanisms=["probe ladder", "cheapest-falsifiable-first rule"],
        dsl=["dry_run", "cost_estimate"],
        post=None,
    ),
    154: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "23 lines that define a protocol the platform's verification lane needs verbatim: "
            "re-derive a load-bearing value in a context that cannot inherit the current "
            "reasoning, and halt on disagreement. It is already load-bearing elsewhere - "
            "rules/common/single-signal-verification.md pairs its two-signal rule with this "
            "skill by name - and it is used across 4 executed scripts and 24 run records."
        ),
        task_fit=[
            "independent-re-derivation",
            "sunk-cost-break",
            "load-bearing-value-check",
        ],
        mechanisms=[
            "fresh-context subagent",
            "halt-on-disagreement",
            "no-self-recheck rule",
        ],
        dsl=["roles", "gates", "subworkflows"],
        post=None,
    ),
    155: dict(
        classification="ADOPT-AS-IS",
        basis=(
            "A keystone acceptance-test scaffold with a measured motivating failure recorded "
            "inline - 'v1.4 with 100% coverage and green units, and Make Shorts never produced a "
            "file on Windows' (SKILL.md:10) - an explicit assertion ladder that ends on a REAL "
            "artifact (ffprobe / file on disk, not element-present), a diagnostic snapshot on "
            "timeout, and a named reward-hack surface to forbid (xfail/skip/coverage-omit/"
            "addopts/markers/CI-trigger). Nothing here needs re-expressing to be useful."
        ),
        task_fit=[
            "packaged-artifact-acceptance",
            "golden-journey",
            "anti-reward-hacking",
        ],
        mechanisms=[
            "assertion ladder",
            "real-artifact postcondition",
            "timeout snapshot",
            "forbidden-surface list",
        ],
        dsl=["gates", "stages", "failure_policy"],
        post=None,
    ),
    156: dict(
        classification="TRANSLATE",
        basis=(
            "It is a bounded-automation design contract stated in DSL terms already: 'Prefer "
            "short, auditable loops with explicit stop rules over long-lived super-agent flows' "
            "(SKILL.md:10), a retry budget (:97), 'one bounded attempt per failure classification "
            "before escalation' (:109), required lane separation, and a named anti-pattern of one "
            "retry loop for unrelated failure lanes (:160). retries + failure_policy + "
            "repair_loops + stopping_rules cover all of it."
        ),
        task_fit=[
            "gate-automation-design",
            "pr-repair",
            "coverage-ratchet",
            "merge-governance",
        ],
        mechanisms=[
            "bounded repair loop",
            "per-classification retry budget",
            "lane separation",
            "escalation rule",
        ],
        dsl=["retries", "repair_loops", "failure_policy", "stopping_rules", "gates"],
        post=None,
    ),
    157: dict(
        classification="SPECIALIZE",
        basis=(
            "This is the repo-specific instance of the generic design in candidate 156: it is "
            "bound by name to Prekzursil/quality-zero-platform, which is confirmed live and "
            "maintained (GitHub API: created 2026-02-19, updated 2026-07-25, 4 open issues, not "
            "archived), and it carries its own Stop Rules section (SKILL.md:69) plus a required "
            "audit order. Keep it as the specialisation, not as a second generic control plane."
        ),
        task_fit=["governed-repo-audit", "ruleset-drift", "trusted-runner-remediation"],
        mechanisms=["control-plane audit order", "stop rules", "enrolment state check"],
        dsl=["stages", "gates", "stopping_rules"],
        post=None,
    ),
    158: dict(
        classification="DISTILL",
        basis=(
            "259 lines of per-language anti-pattern rules aimed at passing Codacy/SonarCloud/"
            "DeepSource/QLTY/Semgrep/Codecov on first push. The enforcement surface in the "
            "platform is the analyzer itself, not prose; what transfers is the checklist (and its "
            "measured claims, e.g. 'kills 70%+ of Codacy findings', SKILL.md:31) folded into the "
            "lint ladder."
        ),
        task_fit=[
            "static-analysis-prevention",
            "coverage-shaped-testing",
            "secret-avoidance",
        ],
        mechanisms=[
            "prevention checklist",
            "per-language rule packs",
            "no-suppression rule",
        ],
        dsl=["gates", "tools"],
        post=None,
    ),
    159: dict(
        classification="CLEAN-ROOM-REIMPLEMENT",
        basis=(
            "The mechanism is wanted - route a large/noisy payload to a file, surface only the "
            "derived answer, index the reusable bytes for on-demand recall - but this is the only "
            "artifact in the slice that declares a NON-permissive licence: `license: ELv2` "
            "(SKILL.md:4), the Elastic License 2.0. The repository it would ship from declares no "
            "licence at all (no LICENSE/NOTICE at the repo root, README has zero licence "
            "mentions, package.json has no license field and is private:true), so there is no "
            "declared release licence to test ELv2 against. Rebuild the three rules in our own "
            "words and leave the ELv2 text out of the release."
        ),
        task_fit=["context-hygiene", "payload-sandboxing", "on-demand-recall-index"],
        mechanisms=[
            "sandbox the payload",
            "surface only the derived answer",
            "index for recall",
        ],
        dsl=["artifact_caching", "tools", "source_policy"],
        post=None,
        license={
            "declared": "ELv2 (Elastic License 2.0)",
            "spdx": "Elastic-2.0",
            "source_anchor": "C:/Users/Prekzursil/.agents/skills/context-sandbox/SKILL.md:4",
            "verdict": "NEEDS-OWNER-DECISION",
            "verdict_basis": (
                "ELv2 is not an OSI-approved open-source licence and restricts providing the work "
                "as a managed service. Measured on this repo: no root LICENSE/NOTICE file, no "
                "license field in package.json (private:true), and no licence mention in "
                "README.md - so the release's own licence is UNDETERMINED and the compatibility "
                "test the release lane wants to run has no left-hand side yet."
            ),
        },
    ),
    160: dict(
        classification="DISTILL",
        basis=(
            "Its two mechanisms are already mandated DSL capabilities - model_routing and "
            "cost_estimate - so adopting the artifact would duplicate the platform. What does not "
            "exist in the DSL is its concrete threshold table (e.g. _SONNET_TEXT_THRESHOLD = "
            "10_000 chars / _SONNET_ITEM_THRESHOLD = 30 items, SKILL.md:28-29) and its "
            "cheapest-model-first rule (:164); distil those into the routing policy and drop the "
            "rest. Its pricing table is dated '2025-2026' and must be treated as decayed."
        ),
        task_fit=["model-routing", "budget-tracking", "prompt-caching", "narrow-retry"],
        mechanisms=[
            "complexity-threshold routing",
            "immutable cost tracking",
            "narrow retry",
            "prompt caching",
        ],
        dsl=["model_routing", "cost_estimate", "retries"],
        post=None,
        license=ECC_UNKNOWN,
    ),
}

ROLE_FIRED = sum(1 for r in feat.values() if r["roles"])
STOP_FIRED = sum(1 for r in feat.values() if r["stop_rule_hits"])
FAIL_FIRED = sum(1 for r in feat.values() if r["failure_hits"])
print(
    "detector yield across the 32: roles=%d stop_rules=%d failure=%d"
    % (ROLE_FIRED, STOP_FIRED, FAIL_FIRED)
)

SLICE = (
    "candidates 129-160 of the 160-candidate Phase 2A floor == indices 129-160 (1-based) of "
    "the ordered candidates[] array in "
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json "
    "(284 rows). That slice is G-skill rows 44-75. wfa-1 declared 1-32, wfa-2 33-64, wfa-3 "
    "65-96, wfa-4 97-128, so the partition is disjoint by construction."
)


def iso(epoch):
    if not epoch:
        return None
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat(
        timespec="seconds"
    )


STAGEY = re.compile(
    r"(?i)^(g[0-9]\b|step\s|phase\s|stage\s|wave\s|round\s|\d+[.)]\s|"
    r"the\s+\w+\s+(loop|cycle|ladder|pipeline)|loop\b|cycle\b|workflow\b|flow\b|"
    r"required\s|gate|stop\s+rules|promotion|outputs?\b|core\s+workflow)"
)


def stages_of(f, path):
    """Stages measured from the artifact: step/phase-shaped headings first, else the
    level-2 section sequence. Every entry carries the file:line it was read from.

    The feature pass indexed the LIVE vault copy; one candidate in this slice is deployed to
    neither vault, so when no headings were captured the artifact is re-read from the path
    actually used (the repo copy) rather than reported as stage-less."""
    hs = f["headings"]
    if not hs and path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        hs = [
            {"line": i + 1, "level": len(m.group(1)), "text": m.group(2).strip()}
            for i, ln in enumerate(body.splitlines())
            for m in [re.match(r"^(#{2,4})\s+(.{2,110}?)\s*$", ln)]
            if m
        ]
    picked = [h for h in hs if STAGEY.match(h["text"].strip())]
    if len(picked) < 2:
        picked = [h for h in hs if h["level"] == 2] or hs
    return [
        {"name": h["text"], "anchor": "%s:%d" % (path, h["line"]), "level": h["level"]}
        for h in picked[:12]
    ]


def drift_direction(d, f):
    groups = {}
    for k, v in d["digests_lf_normalised"].items():
        if v:
            groups.setdefault(v, []).append(k)
    if len(groups) == 1:
        return "none (all copies identical after LF normalisation)", [
            sorted(v) for v in groups.values()
        ]
    live_iso = iso(f.get("mtime_epoch"))
    repo_iso = (f.get("git_last_commit_skills") or " ").split(" ")[0] or None
    direction = "two-directional / undetermined"
    if live_iso and repo_iso:
        direction = (
            "live copy is NEWER than the repo commit (live-ahead)"
            if live_iso > repo_iso
            else "repo commit is NEWER than the live copy (repo-ahead)"
        )
    return "%d distinct content versions; %s" % (len(groups), direction), [
        sorted(v) for v in groups.values()
    ]


records = []
for i in range(129, 161):
    f = feat[i]
    d = drift[i]
    L = lic[i]
    dec = DECISIONS[i]
    name = f["skill_dir_name"]
    path = L["path_used"]
    fm_line = None
    for x in L["frontmatter_block"]:
        if x["text"].strip().startswith("name:"):
            fm_line = x["line"]
    drift_summary, drift_groups = drift_direction(d, f)
    license_block = dec.get(
        "license",
        {
            "declared": "none in the artifact (no frontmatter licence, no LICENSE/NOTICE in the folder, no SPDX header)",
            "spdx": None,
            "source_anchor": "%s (frontmatter read in full; keys=%s)"
            % (path, sorted(f["frontmatter"].keys())),
            "verdict": "OWNER-AUTHORED, TERMS UNDECLARED",
            "verdict_basis": (
                "Detector control for this claim: the same folder-level LICENSE/NOTICE scan "
                "finds such a file in 49 of the 330 live skill directories, so a zero here is a "
                "measurement, not a broken probe. The repository itself declares no licence "
                "either (no root LICENSE, no package.json license field, private:true), so the "
                "terms for this artifact are undeclared rather than permissive."
            ),
        },
    )
    records.append(
        {
            "id": "WFC-%04d" % i,
            "registry_index": i,
            "unit": "build/wfa-5",
            "slice_definition": SLICE,
            "name": name,
            "aka_prior_registry_id": f["prior_id"],
            "family": "G-skill (orchestration-bearing skill)",
            "origin_kind": (
                f["frontmatter"].get("origin")
                or (
                    f["frontmatter"].get("metadata") is not None
                    and "see metadata.origin"
                )
                or "undeclared"
            ),
            "what_it_does": f["frontmatter"].get("description", "")[:600]
            or f["prior_record"].get("does"),
            "provenance": {
                "primary_anchor": "%s:%s" % (path, fm_line or 2),
                "resolution_method": (
                    "the prior archaeology recorded only the token '%s'; resolved to a real "
                    "absolute path by probing all five candidate roots (agents-live, "
                    "claude-live, repo skills/, repo .agents/skills/, repo skills-claude-only/)"
                    % f["prior_record"].get("provenance")
                ),
                "all_copies": {k: v for k, v in f["copies"].items()},
                "pinned_repo_ref": "%s:skills/%s/SKILL.md" % (PINNED[:8], name),
                "head_repo_ref": "%s:skills/%s/SKILL.md" % (HEAD[:8], name),
                "bytes": f["bytes"] or L["bytes"],
                "lines": f["lines"],
                "upstream": [
                    a for a in L["attribution_lines"] if "github.com" in a["text"]
                ][:3],
            },
            "license": license_block,
            "maintenance_state": {
                "live_mtime_utc": iso(f.get("mtime_epoch")),
                "repo_last_commit_skills": f.get("git_last_commit_skills"),
                "repo_last_commit_agents_skills": f.get(
                    "git_last_commit_agents_skills"
                ),
                "deployed_in": sorted(f["copies"].keys()),
                "distinct_content_versions": d["distinct_content_versions"],
                "drift": drift_summary,
                "drift_groups": drift_groups,
                "eol_control": (
                    "comparisons are on LF-normalised bytes; the comparator was proven to "
                    "call a CRLF/LF pair identical AND a one-word change different in the "
                    "same run (_wfa5_drift.json.eol_control)"
                ),
            },
            "task_fit": dec["task_fit"],
            "stages": stages_of(f, path),
            "stage_source": (
                (
                    "measured from the SKILL.md itself: headings matching a step/phase/gate/wave "
                    "pattern where present, otherwise the level-2 section sequence; every entry "
                    "carries the file:line it was read from. step/phase tokens found: %s"
                    % (f["step_tokens"] or "none")
                )
                if stages_of(f, path)
                else (
                    "NONE FOUND - the artifact declares no stages at all. Detector: a "
                    "level-2-to-4 markdown heading regex plus a step/phase/stage/wave/round "
                    "token scan over the whole body; it returned 30 headings for the largest "
                    "candidate in this slice and 0 here, so the zero is a measurement. This "
                    "candidate is a single-shot template, not a staged workflow."
                )
            ),
            "roles": sorted(set(f["roles"] + [x for x in f.get("agent_types", [])])),
            "roles_measurement": (
                "%d role token(s) matched" % len(set(f["roles"]))
                if f["roles"]
                else (
                    "NONE FOUND - this candidate operates with an IMPLICIT single actor. "
                    "Detector: a role-suffix regex (-reviewer|-critic|-auditor|-architect|"
                    "-analyst|-judge|-operator|-engineer|-planner|-designer|-scout|-lead|"
                    "-worker|-adversary) plus an 'agents:/personas:/reviewers:/lenses:/roles:' "
                    "list pattern over the full body; the same detector fired on %d of the 32 "
                    "candidates in this slice, so a zero here is a measurement, not a dead probe."
                    % ROLE_FIRED
                )
            ),
            "role_evidence": f.get("role_lists", [])[:3],
            "tools": {
                "declared_frontmatter": f["frontmatter"].get("tools"),
                "observed_in_body": f["tools"],
                "mcp_tools": f["mcp_tools"],
            },
            "stop_rules": [
                {"anchor": "%s:%d" % (path, x["line"]), "text": x["text"]}
                for x in f["stop_rule_hits"][:5]
            ],
            "stop_rules_measurement": (
                "%d stop-rule line(s) matched and quoted with file:line"
                % len(f["stop_rule_hits"])
                if f["stop_rule_hits"]
                else (
                    "NONE FOUND - this candidate declares NO stopping rule, which is the class "
                    "the spec calls out. Detector: a stop/until/all-must-pass/halt/abort/"
                    "blocking-gate/revert-gate/max-rounds/threshold/convergence/saturation/"
                    "quorum/unanimity/consensus/two-strikes/capped-at regex over every line; it "
                    "fired on %d of the 32 candidates in this slice, so a zero is a measurement."
                    % STOP_FIRED
                )
            ),
            "failure_behaviour": {
                "anchors": [
                    {"anchor": "%s:%d" % (path, x["line"]), "text": x["text"]}
                    for x in f["failure_hits"][:4]
                ],
                "note": (
                    "no failure/fallback/retry construct was matched in the body"
                    if not f["failure_hits"]
                    else "matched constructs are quoted with file:line above"
                ),
            },
            "benchmark_evidence": {
                "executed_workflow_scripts_naming_it": f["usage"][
                    "executed_scripts_naming_it"
                ],
                "run_records_naming_it": f["usage"]["run_records_naming_it"],
                "example_scripts": f["usage"]["example_scripts"][:3],
                "repo_files_referencing_the_name": ver["P6_repo_reference_counts"].get(
                    name
                ),
                "measured_claims_in_the_artifact": [
                    {"anchor": "%s:%d" % (path, x["line"]), "text": x["text"]}
                    for x in f["measurement_hits"][:3]
                ],
                "caveat": (
                    "These are USAGE and TELEMETRY signals (how often the estate reached for it), "
                    "not a controlled benchmark. No candidate in this slice has an A/B measurement "
                    "against an alternative; that is NOT-CHECKED for all 32 and would require "
                    "executing the mechanism twice under a fixed task set."
                ),
                "usage_detector_controls": (
                    "corpus scan: the token 'agent(' was found in 200/200 sampled scripts and a "
                    "bogus token in 0/200; repo scan (mechanically different: git grep over the "
                    "repo) returned 0 files for a bogus name and non-zero for every real one"
                ),
            },
            "mechanisms": dec["mechanisms"],
            "dsl_capabilities_that_cover_it": dec["dsl"],
            "dsl_gap": dec.get("dsl_gap"),
            "classification": dec["classification"],
            "classification_basis": dec["basis"],
            "post_disposition": dec.get("post"),
            "distinctness": {
                "nearest_in_slice": f["nearest_neighbour_in_slice"]["name"],
                "token_jaccard": f["nearest_neighbour_in_slice"]["jaccard"],
                "verdict": (
                    "materially distinct - the highest pairwise similarity anywhere in this "
                    "slice is 0.177, far below any renamed-copy or one-parameter-fork threshold"
                ),
            },
            "unverified": dec.get("unverified", []),
        }
    )

# per-record defects
DEFECTS = {
    130: [
        "the ~/.agents deployment substitutes Codex for Claude at SKILL.md:3, :10 and :23, "
        "collapsing a deliberately cross-vendor pair of rival suggesters into a same-vendor one"
    ],
    131: ["three divergent copies with no canonical version"],
    132: ["three divergent copies with no canonical version"],
    139: [
        "three divergent copies with no canonical version",
        "rider-restricted dependency",
    ],
    148: [
        "present in the repo at HEAD but deployed to NEITHER live vault "
        "(~/.agents/skills and ~/.claude/skills both absent), so no running agent can read it"
    ],
    159: ["declares ELv2 inside a repository that declares no licence at all"],
}
for r in records:
    r["defects"] = DEFECTS.get(r["registry_index"], [])
    r["coverage_gaps"] = (
        "MEASURED here: on-disk resolution, all copies + LF-normalised drift, frontmatter, "
        "stages from headings/step tokens, tool + MCP surface, stop-rule and failure-construct "
        "anchors, licence anchors, repo commit dates, corpus usage, pairwise distinctness. "
        "NOT MEASURED: the referenced sub-files under each skill directory (references/*.md, "
        "scripts/*) except where explicitly named; whether the documented procedure actually "
        "succeeds when executed; and any A/B benchmark against an alternative mechanism."
    )

with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(records, fh, indent=1, ensure_ascii=True)
    fh.write("\n")

meta = {
    "unit": "build/wfa-5",
    "artifact": "platform/registry/workflow-candidates-5.json",
    "count": len(records),
    "slice_definition": SLICE,
    "what_this_unit_did": (
        "The prior archaeology recorded these 32 rows with a provenance string of the form "
        "'agents-live: <name>' - a token, not a retrievable anchor - and left licence, "
        "maintenance, stages, roles, tools, stop rules, failure behaviour and benchmark "
        "evidence either absent or MECHANICAL. This unit normalised them into 24 typed fields, "
        "resolved 32/32 to real absolute paths, measured every copy's content digest, read "
        "every licence anchor, and classified each with a stated basis."
    ),
    "detector_controls": {
        "on_disk_resolution": "known-present skill resolves True, known-absent sentinel resolves False",
        "eol_comparator": "CRLF-vs-LF pair judged identical AND a one-word change judged different, same run",
        "licence_file_scan": "finds a LICENSE/NOTICE in 49 of 330 live skill dirs, so a zero is a measurement",
        "usage_scan": "'agent(' in 200/200 sampled scripts, bogus token in 0/200; git grep returns 0 for a bogus name",
        "second_usage_signal": "git grep over the repo is mechanically independent of the executed-corpus JSON scan",
    },
    "classification_distribution": {},
    "honest_gaps": [
        "No candidate here has an A/B benchmark against an alternative; benchmark_evidence is "
        "usage telemetry only.",
        "Sub-files inside the skill directories (references/*.md, scripts/*) were not read "
        "except where a record names one.",
        "antbotlab/blueprint's licence is NOT-CHECKED: the minimal GitHub projection used omits "
        "the license field.",
        "The upstream terms for `origin: ECC` (9 records), `origin: community` (3) and "
        "`origin: oh-my-agent-check` (1) could not be established from any on-disk source.",
        "The repository declares no licence, so the release-side compatibility test that the "
        "ELv2 record needs cannot be computed yet.",
    ],
}
for r in records:
    meta["classification_distribution"][r["classification"]] = (
        meta["classification_distribution"].get(r["classification"], 0) + 1
    )
with open(METHOD, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(meta, fh, indent=1)
    fh.write("\n")

print("wrote", OUT)
print("wrote", METHOD)
print("classification distribution:", json.dumps(meta["classification_distribution"]))
