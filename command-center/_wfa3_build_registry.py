"""wfa-3: emit platform/registry/workflow-candidates-3.json.

Mechanical fields (exists / bytes / mtime / git last-commit / license class + source file)
are READ FROM the probe outputs, never typed from memory. Prose fields are curated per row
and every unread field is explicitly NOT-CHECKED rather than guessed.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

CC = Path("C:/Users/Prekzursil/source/ast-integrate/command-center")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/platform/registry/workflow-candidates-3.json"
)
DOC = "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
MEASURED_AT = "2026-08-09"

verify = json.loads((CC / "_wfa3_verify_out.json").read_text(encoding="utf-8"))
plugincache = json.loads(
    (CC / "_wfa3_plugincache_out.json").read_text(encoding="utf-8")
)
lics = json.loads((CC / "_wfa3_licenses_out.json").read_text(encoding="utf-8"))

VROW = {r["prior_id"]: r for r in verify["rows"]}
PC = {r["dir"]: r for r in plugincache["rows"]}

# archaeology doc heading line for each prior id (from a `grep -n '^###'` pass)
DOCLINE = {
    "plugin-superpowers": 792,
    "plugin-metaswarm": 803,
    "plugin-ralph-loop": 814,
    "plugin-claude-reflect": 825,
    "plugin-hookify": 836,
    "plugin-remember": 847,
    "plugin-skill-creator": 858,
    "plugin-codex": 869,
    "plugin-modern-web-guidance": 880,
    "plugin-catalogue-tax": 891,
    "marketplace-anthropic-agent-skills": 903,
    "marketplace-claude-plugins-official": 914,
    "marketplace-context-mode": 925,
    "marketplace-googlechrome": 936,
    "marketplace-openai-codex": 947,
    "marketplace-claude-reflect-marketplace": 958,
    "marketplace-metaswarm-marketplace": 969,
    "marketplace-temp_1781578811820": 980,
    "marketplace-prekzursil-local-mcp": 991,
    "marketplace-mattpocock-skills": 1002,
    "marketplace-agentbridge": 1013,
    "skill-workflow-authoring": 1026,
    "skill-workflow-monitor": 1037,
    "skill-orchestration-patterns": 1048,
    "skill-gem-hunt": 1059,
    "skill-grill-me-extensive": 1070,
    "skill-council": 1081,
    "skill-critique-panel": 1092,
    "skill-rubric-verifier": 1103,
    "skill-agent-as-judge": 1114,
    "skill-execution-grounded-bon": 1125,
    "skill-diff-blind-test-synth": 1136,
}

NC = "NOT-CHECKED (body not read by this unit)"


def measured(prior_id):
    """Mechanical facts for an anchor row, straight from the verify probe."""
    r = VROW[prior_id]
    d = r.get("declared") or {}
    al = r.get("agents_live") or {}
    sk = r.get("skill_md") or {}
    out = {
        "declared_path": r["prior_provenance"],
        "declared_path_exists": d.get("exists", al.get("exists")),
    }
    for src, pfx in ((d, ""), (al, "vault_")):
        if src.get("git_last_commit"):
            out[pfx + "git_last_commit"] = src["git_last_commit"]
        if src.get("newest_mtime"):
            out[pfx + "newest_mtime_utc"] = src["newest_mtime"]
        if src.get("file_count_scanned") is not None:
            out[pfx + "file_count"] = src["file_count_scanned"]
    if sk:
        out["skill_md_bytes"] = sk.get("bytes")
        out["skill_md_mtime_utc"] = sk.get("mtime")
    if r.get("PROVENANCE_DEFECT"):
        out["provenance_defect"] = r["PROVENANCE_DEFECT"]
    if r.get("alternates_found"):
        out["real_body_found_under"] = list(r["alternates_found"])
    return out


def surface(dirname):
    r = PC.get(dirname) or {}
    s = r.get("surface") or {}
    return {
        k: v["count"] for k, v in s.items() if isinstance(v, dict) and "count" in v
    } or NC


ROWS = []


def add(**kw):
    # Wave-wide union key. Siblings workflow-candidates-4/-5 key rows as WFC-00NN where NN is
    # the prior-registry index (their WFC-0097 == prior index 97, immediately after my 96), so
    # every row carries that alias too and the five files merge on one key without a rename.
    if "range_index" in kw:
        kw = {"wfc_id": f"WFC-{kw['range_index']:04d}", **kw}
    ROWS.append(kw)


# --------------------------------------------------------------------------------------
# 65-73  the nine ENABLED plugins  (bodies newly measured; licences read at source)
# --------------------------------------------------------------------------------------
add(
    id="WFA3-065",
    range_index=65,
    counts_toward_range=True,
    prior_id="plugin-superpowers",
    name="superpowers (obra/superpowers) v6.2.0",
    family="F-plugin",
    candidate_kind="workflow-mechanism-pack",
    provenance={
        "upstream_repo": "https://github.com/obra/superpowers",
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/cache/claude-plugins-official/superpowers/6.2.0",
        "manifest": ".../superpowers/6.2.0/.claude-plugin/plugin.json",
        "enablement": "~/.claude/settings.json enabledPlugins['superpowers@claude-plugins-official']=true",
        "prior_record": f"{DOC}:792",
        "CORRECTION": "The prior record gave provenance as the marketplace clone "
        "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official. Measured: that "
        "clone's plugins/ dir has 39 entries and superpowers is NOT one of them. The body is "
        "version-keyed in the plugin CACHE (5 versions cached: 3dcbd5c4b48e, 5.1.0, 6.0.2, 6.1.1, 6.2.0).",
    },
    license={
        "name": "MIT",
        "spdx": "MIT",
        "copyright": "Copyright (c) 2025 Jesse Vincent",
        "source_file": ".../superpowers/6.2.0/LICENSE (read) AND plugin.json 'license':'MIT'",
        "CORRECTION": "The prior record said 'third-party (per-plugin; see marketplace LICENSE)'. The marketplace "
        "root LICENSE is Apache-2.0/11358B - a DIFFERENT licence and a different copyright holder "
        "(Anthropic vs Jesse Vincent). Following the prior record's own pointer yields the wrong terms.",
        "adoption_constraint": "MIT: redistribution and derivative works permitted with attribution.",
    },
    maintenance={
        "state": "ENABLED at user scope",
        "version": "6.2.0",
        "cached_versions": ["3dcbd5c4b48e", "5.1.0", "6.0.2", "6.1.1", "6.2.0"],
        "measured_at": MEASURED_AT,
    },
    task_fit="General software-delivery lifecycle: brainstorm -> plan -> execute -> review -> finish.",
    stages=[
        "brainstorming",
        "writing-plans",
        "executing-plans",
        "subagent-driven-development",
        "dispatching-parallel-agents",
        "test-driven-development",
        "systematic-debugging",
        "requesting-code-review",
        "receiving-code-review",
        "verification-before-completion",
        "using-git-worktrees",
        "finishing-a-development-branch",
        "writing-skills",
        "using-superpowers",
    ],
    roles=["planner", "implementer", "parallel subagents", "code reviewer"],
    tools=["claude-code skills", "hooks/", "scripts/", "tests/"],
    stop_rules="verification-before-completion + finishing-a-development-branch act as the terminal gates; "
    "exact predicate " + NC,
    failure_behaviour=NC,
    benchmark_evidence="None shipped in-tree. NOT-CHECKED upstream.",
    mechanisms=[
        "brainstorm stage",
        "plan stage",
        "parallel dispatch",
        "reviewer",
        "worktree isolation",
        "verification gate",
    ],
    classification="ADOPT-WITH-WRAPPER",
    classification_rationale="Reclassified from the prior ADOPT-AS-IS. The estate already wraps it: project "
    "CLAUDE.md 'Workflow Enforcement (MANDATORY)' overrides its defaults "
    "('Mandatory even if the brainstorming skill says to go directly to writing-plans') "
    "and inserts the metaswarm design/plan gates. An as-is adoption would contradict that "
    "governance, so the wrapper is not optional.",
    measured=measured("plugin-superpowers"),
    body_surface={"skills": 14, "skill_names_read": True},
    confidence="almost-certain (90-99): licence, version and skill list all read directly from the resolved body.",
)

add(
    id="WFA3-066",
    range_index=66,
    counts_toward_range=True,
    prior_id="plugin-metaswarm",
    name="metaswarm (dsifry/metaswarm) v0.12.0",
    family="F-plugin",
    candidate_kind="orchestration-framework",
    provenance={
        "upstream_repo": "https://github.com/dsifry/metaswarm",
        "marketplace_repo": "https://github.com/dsifry/metaswarm-marketplace.git",
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/cache/metaswarm-marketplace/metaswarm/0.12.0",
        "manifest": ".../metaswarm/0.12.0/.claude-plugin/plugin.json",
        "enablement": "enabledPlugins['metaswarm@metaswarm-marketplace']=true",
        "prior_record": f"{DOC}:803",
        "CORRECTION": "Prior provenance was the marketplace clone, which measured 2 files (README shell only, "
        "git 9c1df39 2026-06-16 David Sifry). The runnable body is the version-keyed cache path above.",
    },
    license={
        "name": "MIT",
        "spdx": "MIT",
        "copyright": "Copyright (c) 2026 Dave Sifry",
        "source_file": ".../metaswarm/0.12.0/LICENSE (read) AND plugin.json 'license':'MIT'",
        "CORRECTION": "Prior said 'third-party (per-plugin; see marketplace LICENSE)'; the marketplace clone "
        "carries NO LICENSE file at all, so the prior pointer resolves to nothing.",
        "adoption_constraint": "MIT: permits the TRANSLATE/DISTILL routes this program needs.",
    },
    maintenance={
        "state": "ENABLED at user scope; declared MANDATORY by project CLAUDE.md",
        "version": "0.12.0",
        "marketplace_git": "9c1df39 2026-06-16 David Sifry",
        "measured_at": MEASURED_AT,
    },
    task_fit="Full spec-driven delivery pipeline with quality gates - the estate's declared authority for "
    "multi-file work.",
    stages=[
        "research",
        "plan",
        "design-review-gate",
        "work-unit-decomposition",
        "orchestrated-execution (IMPLEMENT/VALIDATE/ADVERSARIAL-REVIEW/COMMIT)",
        "final-review",
        "PR",
    ],
    roles=[
        "19 agent definitions on disk (PM, architect, designer, security, CTO, reviewers, ...)"
    ],
    tools=[
        "agents/ (19)",
        "skills/ (14)",
        "commands/",
        "hooks/",
        "lib/",
        "cli/",
        "bin/",
        "knowledge/",
    ],
    stop_rules="Gate-shaped: design gate needs all 5 approvals; plan gate needs 3/3 PASS; coverage gate reads "
    "the project .coverage-thresholds.json. Exact predicates " + NC,
    failure_behaviour="Gates block progression rather than degrade; "
    + NC
    + " for retry/escalation policy.",
    benchmark_evidence="None in-tree. NOT-CHECKED.",
    mechanisms=[
        "9-phase pipeline",
        "design council (5)",
        "adversarial plan council (3)",
        "4-phase execution loop",
        "coverage gate",
        "pre-PR knowledge capture",
    ],
    classification="ADOPT-AS-IS",
    classification_rationale="Already the declared governing pipeline in project CLAUDE.md; MIT permits it; the "
    "body is complete (19 agents / 14 skills / 16 commands per its own manifest).",
    measured=measured("plugin-metaswarm"),
    body_surface={"agents": 19, "skills": 14, "commands_claimed_by_manifest": 16},
    corrections_vs_prior=[
        "Project CLAUDE.md says '18 specialized agents'; the manifest says 19 and the agents/ "
        "dir contains 19. Minor doc drift, flagged not fixed."
    ],
    confidence="almost-certain (90-99) on licence/version/counts - all read at the resolved body.",
)

_plug = [
    (
        "WFA3-067",
        67,
        "plugin-ralph-loop",
        "ralph-loop v1.0.0",
        "ralph-loop",
        814,
        "Autonomous long-running loop (Ralph Wiggum technique): run the same prompt in a while-true loop until done.",
        ["loop-iteration", "cancel"],
        ["loop operator"],
        ["commands (3)", "hooks (2)", "scripts (1)"],
        "Loop terminates on a task-complete condition or /cancel-ralph; exact predicate "
        + NC,
        NC,
        ["autonomous loop", "cancel control"],
        "ADOPT-WITH-WRAPPER",
        "Kept from prior. Four overlapping ralph artifacts exist in the estate (this plugin plus skills/ralph-loop, "
        "skills/ralph-hats, skills/ralph-orchestrator-setup, skills/ralphinho-rfc-pipeline) - a MERGE decision is "
        "owed before adoption, so as-is is not safe.",
    ),
    (
        "WFA3-069",
        69,
        "plugin-hookify",
        "hookify",
        "hookify",
        836,
        "Convert observed unwanted behaviour into a preventing hook.",
        ["observe conversation", "author rule", "install hook"],
        ["hook author"],
        ["agents (1)", "commands (4)", "skills (1)", "hooks (6)"],
        "N/A - authoring tool, no run loop.",
        NC,
        ["hook authoring", "rule config"],
        "ADOPT-AS-IS",
        "Apache-2.0 per-plugin LICENSE is byte-identical to the marketplace root, so the prior pointer happens to be "
        "correct here; body present in the marketplace clone.",
    ),
    (
        "WFA3-071",
        71,
        "plugin-skill-creator",
        "skill-creator",
        "skill-creator",
        858,
        "Author, improve and EVAL skills (18 skills incl. eval harness).",
        ["create", "improve", "eval"],
        ["skill author", "evaluator"],
        ["skills (18)"],
        "Eval-driven: a skill is done when its eval passes; exact threshold " + NC,
        NC,
        ["skill authoring", "skill eval"],
        "ADOPT-AS-IS",
        "Apache-2.0 verified identical to root; the eval sub-surface is directly reusable as a scoring mechanism.",
    ),
    (
        "WFA3-073",
        73,
        "plugin-modern-web-guidance",
        "modern-web-guidance (GoogleChrome)",
        "modern-web-guidance",
        880,
        "Chrome/modern-web guidance skill pack (2 skills).",
        ["guidance lookup"],
        ["advisor"],
        ["skills (2)"],
        "N/A - advisory.",
        "N/A - advisory.",
        ["guidance"],
        "ADOPT-AS-IS",
        "Apache-2.0 confirmed at BOTH the googlechrome marketplace root LICENSE and its package.json license field.",
    ),
]
for (
    pid,
    idx,
    prior,
    nm,
    dirn,
    line,
    fit,
    stages,
    roles,
    tools,
    stop,
    fail,
    mech,
    cls,
    why,
) in _plug:
    add(
        id=pid,
        range_index=idx,
        counts_toward_range=True,
        prior_id=prior,
        name=nm,
        family="F-plugin",
        candidate_kind="workflow-mechanism-pack",
        provenance={
            "verified_body": f"C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official/plugins/{dirn}"
            if prior != "plugin-modern-web-guidance"
            else "C:/Users/Prekzursil/.claude/plugins/marketplaces/googlechrome",
            "upstream_repo": "https://github.com/anthropics/claude-plugins-official"
            if prior != "plugin-modern-web-guidance"
            else "https://github.com/GoogleChrome/modern-web-guidance",
            "enablement": f"enabledPlugins['{prior.replace('plugin-', '')}@...']=true (9 of 99 keys are true)",
            "prior_record": f"{DOC}:{line}",
        },
        license={
            "name": (lics["plugins"].get(dirn, {}) or {}).get("class", "UNKNOWN"),
            "source_file": f".../plugins/{dirn}/LICENSE",
            "identical_to_marketplace_root": (lics["plugins"].get(dirn, {}) or {}).get(
                "identical_to_root"
            ),
            "verification": "sha256-compared against the marketplace root LICENSE",
        },
        maintenance={"state": "ENABLED at user scope", "measured_at": MEASURED_AT},
        task_fit=fit,
        stages=stages,
        roles=roles,
        tools=tools,
        stop_rules=stop,
        failure_behaviour=fail,
        benchmark_evidence="NOT-CHECKED.",
        mechanisms=mech,
        classification=cls,
        classification_rationale=why,
        measured=measured(prior),
        body_surface=surface(dirn),
        confidence="likely (55-80) on stages/roles (derived from the manifest description + on-disk surface, "
        "bodies not read); almost-certain on licence class and file counts.",
    )

add(
    id="WFA3-068",
    range_index=68,
    counts_toward_range=True,
    prior_id="plugin-claude-reflect",
    name="claude-reflect (bayramannakov/claude-reflect)",
    family="F-plugin",
    candidate_kind="learning-loop",
    provenance={
        "upstream_repo": "https://github.com/bayramannakov/claude-reflect",
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-reflect-marketplace",
        "prior_record": f"{DOC}:825",
    },
    license={
        "name": "MIT",
        "spdx": "MIT",
        "copyright": "Copyright (c) 2025 Bayram Annakov",
        "source_file": ".../claude-reflect-marketplace/LICENSE (1092 B, read) AND "
        ".claude-plugin/plugin.json 'license':'MIT'",
        "verification": "two independent readings (LICENSE text + manifest field) agree",
    },
    maintenance={
        "state": "ENABLED at user scope",
        "git_last_commit": "8dc9db4 2026-03-16 Bayram Annakov",
        "staleness": "~5 months since last upstream commit at measurement time",
        "measured_at": MEASURED_AT,
    },
    task_fit="Post-hoc correction capture: the owner's corrections become a calibration corpus.",
    stages=["observe session", "queue correction", "reflect", "apply to skills"],
    roles=["reflector"],
    tools=["commands/", "hooks/", "scripts/", "tests/"],
    stop_rules="Queue-drain shaped; " + NC,
    failure_behaviour=NC,
    benchmark_evidence="Named by the estate's agent-as-judge skill as the KAPPA calibration source "
    "('stays advisory while kappa < 0.6'). That is a declared dependency, not a measured score.",
    mechanisms=["reflection loop", "correction queue", "judge calibration source"],
    classification="ADOPT-AS-IS",
    classification_rationale="MIT, present, enabled, and already load-bearing for the judge-calibration design.",
    measured=measured("plugin-claude-reflect"),
    body_surface=surface("claude-reflect"),
    confidence="almost-certain (90-99) on licence/maintenance; likely on stages.",
)

add(
    id="WFA3-070",
    range_index=70,
    counts_toward_range=True,
    prior_id="plugin-remember",
    name="remember (Digital-Process-Tools/claude-remember) v0.18.0",
    family="F-plugin",
    candidate_kind="memory-pipeline",
    provenance={
        "upstream_repo": "https://github.com/Digital-Process-Tools/claude-remember",
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/cache/claude-plugins-official/remember/0.18.0",
        "prior_record": f"{DOC}:847",
        "CORRECTION": "Prior provenance was the marketplace clone; remember is NOT among that clone's 39 "
        "plugins. Body is version-keyed in the cache - 12 versions retained "
        "(0.7.3 through 0.18.0 plus 9bf9939dcaf2).",
    },
    license={
        "name": "Community License (bespoke, non-OSI)",
        "spdx": "NOT-AN-SPDX-IDENTIFIER",
        "copyright": "Copyright (c) 2026 Digital Process Tools (DPT)",
        "source_file": ".../remember/0.18.0/LICENSE (read: 'COMMUNITY LICENSE') AND "
        "plugin.json 'license':'Community License'",
        "CORRECTION": "Prior said 'see marketplace LICENSE' -> Apache-2.0. It is NOT Apache-2.0 and not any "
        "standard licence.",
        "adoption_constraint": "HAZARD: a bespoke licence must be read in full before any DISTILL/TRANSLATE "
        "of its mechanism into estate code. Terms NOT-CHECKED beyond the header.",
    },
    maintenance={
        "state": "ENABLED at user scope",
        "version": "0.18.0",
        "cached_versions_count": 12,
        "measured_at": MEASURED_AT,
    },
    task_fit="Continuous session memory: extract -> summarize -> compress into tiered daily logs.",
    stages=["extract", "summarize", "compress", "tiered daily log"],
    roles=["memory pipeline (headless claude sub-invocation)"],
    tools=[
        "pipeline/",
        "prompts/",
        "hooks/",
        "hooks.d/",
        "commands/",
        "skills/",
        "scripts/",
        "pyproject.toml",
    ],
    stop_rules="Consolidation runs under a hardcoded timeout.",
    failure_behaviour="MEASURED DEFECT (estate ledger, Program R 2026-07-26): consolidation ALWAYS skips because a "
    "headless claude invocation costs 80-169 s against a hardcoded 120 s timeout, so now.md grew "
    "to 774 KB. Fails silently by skipping, not by erroring - the worst shape.",
    benchmark_evidence="The 774 KB / 80-169 s vs 120 s figures are the estate's own measurement, carried from the "
    "prior record. NOT independently re-measured by this unit.",
    mechanisms=["memory capture", "tiered compression", "headless sub-invocation"],
    classification="REPAIR",
    classification_rationale="Kept from prior. The mechanism is wanted, the shipped timeout makes it a no-op, and "
    "the bespoke licence adds a redistribution question on top.",
    measured=measured("plugin-remember"),
    confidence="almost-certain (90-99) that the licence is bespoke and the body is cache-resident (both read "
    "directly); likely (55-80) that the timeout defect is still live - carried, not re-measured.",
)

add(
    id="WFA3-072",
    range_index=72,
    counts_toward_range=True,
    prior_id="plugin-codex",
    name="codex (openai/codex-plugin-cc)",
    family="F-plugin",
    candidate_kind="cross-vendor-rail",
    provenance={
        "upstream_repo": "https://github.com/openai/codex-plugin-cc",
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/marketplaces/openai-codex",
        "prior_record": f"{DOC}:869",
    },
    license={
        "name": "Apache-2.0",
        "spdx": "Apache-2.0",
        "copyright": "Copyright 2026 OpenAI",
        "source_file": ".../openai-codex/LICENSE (11145 B) + NOTICE (560 B) + package.json "
        "'license':'Apache-2.0'",
        "verification": "three independent readings agree (LICENSE text, NOTICE, package.json field)",
    },
    maintenance={
        "state": "ENABLED at user scope",
        "git_last_commit": "db52e28 2026-07-07 bryane-oai",
        "measured_at": MEASURED_AT,
    },
    task_fit="Cross-vendor dispatch to OpenAI Codex; result handling; GPT-5 prompting guidance.",
    stages=["rescue/forward", "result handling"],
    roles=["forwarder", "result handler"],
    tools=[
        "commands (/codex:rescue, /codex:setup)",
        "skills (codex-cli-runtime, codex-result-handling, gpt-5-4-prompting)",
        "app-server tsconfig",
        "tests",
    ],
    stop_rules="Per rules/common/cross-vendor-dispatch.md S2 an AND-gate of >=2 signals is required "
    "(exit 0 AND non-empty --output-last-message AND schema-valid); the plugin itself does not enforce it.",
    failure_behaviour="rules/common/cross-vendor-dispatch.md S6 records the hole: the shipped guidance's "
    "'if the Bash call fails ... return nothing' is an unrecoverable gap in a fan-in barrier.",
    benchmark_evidence="Estate-measured (cross-vendor-dispatch.md): 3 Codex-backed subagents produced 0 production "
    "artifacts in one wave; the failure was in the ADAPTER, not the vendor. Carried, not re-measured.",
    mechanisms=["cross-vendor rail", "result handling", "prompt-file transport"],
    classification="ADOPT-WITH-WRAPPER",
    classification_rationale="Kept from prior and independently supported by the estate rule: "
    "cross-vendor-dispatch.md S8 states codex:codex-rescue is a RESCUE FORWARDER, not a "
    "work-unit agent, and must not sit on a critical path. A wrapper enforcing the "
    "two-signal completion gate is mandatory.",
    measured=measured("plugin-codex"),
    body_surface=surface("codex"),
    confidence="almost-certain (90-99) on licence/provenance/git date.",
)

# --------------------------------------------------------------------------------------
# 74 + 82  the two REJECTED anchor rows (recorded, NOT counted)
# --------------------------------------------------------------------------------------
add(
    id="WFA3-074-REJECT",
    range_index=74,
    counts_toward_range=False,
    prior_id="plugin-catalogue-tax",
    name="98 installed plugins / 9 enabled (aggregate observation)",
    family="F-plugin",
    candidate_kind="meta-observation-NOT-A-CANDIDATE",
    provenance={
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/installed_plugins.json (36833 B)",
        "prior_record": f"{DOC}:891",
    },
    license={"name": "N/A - not a distributable artifact"},
    maintenance={
        "state": "CONFIRMED: exactly 9 of 99 enabledPlugins keys are true",
        "measured_at": MEASURED_AT,
    },
    task_fit="None. It is a measurement about the catalogue, not a workflow or mechanism.",
    stages=[],
    roles=[],
    tools=[],
    stop_rules="N/A",
    failure_behaviour="N/A",
    benchmark_evidence="Independently re-measured this unit: enabledPlugins has 99 keys, 9 true "
    "(claude-reflect, codex, hookify, metaswarm, modern-web-guidance, ralph-loop, remember, "
    "skill-creator, superpowers). The prior 9/98-99 claim is CONFIRMED.",
    mechanisms=[],
    classification="REJECT",
    classification_rationale="Not a candidate workflow or mechanism - it is an aggregate observation about the "
    "other rows, with an empty mechanisms list even in the prior registry. Counting it "
    "would pad the range. Its measurement is preserved here; the remediation it implies "
    "belongs to the existing mcp-fleet-curation skill.",
    measured=measured("plugin-catalogue-tax"),
    confidence="almost-certain (90-99): the 9/99 count was recomputed from settings.json this unit.",
)

_dup = verify["duplicate_probe_temp_vs_anthropic"]
add(
    id="WFA3-082-REJECT",
    range_index=82,
    counts_toward_range=False,
    prior_id="marketplace-temp_1781578811820",
    name="temp_1781578811820 - stale fork of anthropics/skills",
    family="F-plugin",
    candidate_kind="duplicate-source-clone-NOT-A-CANDIDATE",
    provenance={
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/marketplaces/temp_1781578811820",
        "upstream_repo": "https://github.com/anthropics/skills.git (same upstream as row 75)",
        "prior_record": f"{DOC}:980",
    },
    license={
        "name": "UNRESOLVED at source",
        "source_file": ".../temp_1781578811820/THIRD_PARTY_NOTICES.md (46566 B); no LICENSE file at root",
        "note": "Same licence posture as row 75 - which is itself unresolved.",
    },
    maintenance={
        "state": "NOT registered in known_marketplaces.json (9 keys, this is not one)",
        "git_last_commit": "5754626 2026-06-09 Lance Martin",
        "vs_canonical": "canonical anthropic-agent-skills is at f17010c 2026-08-07 CJ Avilla - "
        "this clone is ~2 months behind",
        "measured_at": MEASURED_AT,
    },
    task_fit="None distinct - it is the same upstream repository at an older commit.",
    stages=[],
    roles=[],
    tools=[],
    stop_rules="N/A",
    failure_behaviour="N/A",
    benchmark_evidence="",
    mechanisms=["skill/plugin source (duplicate of row 75)"],
    classification="REJECT",
    classification_rationale="The spec forbids counting trivial forks or renamed copies. Exact per-file sha256 "
    "manifest comparison against anthropic-agent-skills: "
    f"{_dup.get('identical_hash')} of {_dup.get('shared')} shared paths hash-identical, "
    f"a={_dup.get('a_files')} files vs t={_dup.get('t_files')} files. Same upstream, older "
    "commit => not materially distinct, so it is NOT counted toward the range.",
    measured={"duplicate_probe": _dup},
    corrections_vs_prior=[
        "REFUTED as stated: the prior record calls it a 'Byte-level duplicate top-level of anthropic-agent-skills'. "
        f"Measured: {_dup.get('differing_hash')} shared paths have DIFFERENT sha256, "
        f"{_dup.get('only_in_a_count')} paths exist only in the canonical clone and "
        f"{_dup.get('only_in_t_count')} exist ONLY in this temp clone. Verdict NEAR-DUPLICATE, not byte-identical.",
        "CONSEQUENCE: the prior action 'RETIRE the temp clone' is position-blind. Deleting it destroys the "
        f"{_dup.get('only_in_t_count')} paths it uniquely holds. Correct action: diff-then-retire - salvage the "
        "unique paths first, then remove. This is the estate's own recorded data-loss class (grade a containment "
        "heuristic by error DIRECTION, not accuracy).",
    ],
    confidence="almost-certain (90-99): sha256 per-path manifests on both trees, an exact algorithm, "
    "with only_in_* sets enumerated.",
)

# --------------------------------------------------------------------------------------
# 75-81, 83-85  the source channels
# --------------------------------------------------------------------------------------
add(
    id="WFA3-075",
    range_index=75,
    counts_toward_range=True,
    prior_id="marketplace-anthropic-agent-skills",
    name="anthropic-agent-skills (anthropics/skills)",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "upstream_repo": "https://github.com/anthropics/skills.git",
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/marketplaces/anthropic-agent-skills",
        "registration": "known_marketplaces.json key 'anthropic-agent-skills'",
        "prior_record": f"{DOC}:903",
    },
    license={
        "name": "UNRESOLVED AT SOURCE - adverse inference required",
        "source_file": "no LICENSE / LICENSE.md / COPYING at the clone root; only "
        "THIRD_PARTY_NOTICES.md (46566 B)",
        "verification": "8 licence filenames probed at the root; only THIRD_PARTY_NOTICES.md matched",
        "CORRECTION": "Prior recorded a bare 'third-party'. Measured: there is no root licence grant to point "
        "at, so redistribution terms for the 17 first-party skills are NOT established on disk.",
    },
    maintenance={
        "state": "registered; 411 files",
        "git_last_commit": "f17010c 2026-08-07 CJ Avilla",
        "newest_mtime_utc": "2026-08-07T17:38:39Z",
        "measured_at": MEASURED_AT,
    },
    task_fit="Source of 17 first-party skills (docx/pdf/pptx/xlsx, canvas-design, mcp-builder, skill-creator, "
    "webapp-testing, ...).",
    stages=["clone", "install skill"],
    roles=["skill source"],
    tools=["skills/", "spec/", "template/"],
    stop_rules="N/A - a channel.",
    failure_behaviour="N/A - a channel.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source"],
    classification="ADOPT-AS-IS",
    classification_rationale="Live, current (2 days old at measurement), and the canonical of the pair. Adoption of "
    "any individual skill from it is gated on resolving the missing root licence.",
    measured=measured("marketplace-anthropic-agent-skills"),
    confidence="almost-certain (90-99) on git date and the absence of a root LICENSE (8 filenames probed; the same "
    "probe DID find LICENSE files in 5 sibling clones, so the detector works).",
)

add(
    id="WFA3-076",
    range_index=76,
    counts_toward_range=True,
    prior_id="marketplace-claude-plugins-official",
    name="claude-plugins-official (anthropics)",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "upstream_repo": "https://github.com/anthropics/claude-plugins-official",
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official",
        "registration": "known_marketplaces.json, lastUpdated 2026-08-09T18:33:24.444Z",
        "inventory": "39 first-party plugins + 15 external_plugins (both enumerated)",
        "prior_record": f"{DOC}:914",
    },
    license={
        "name": "Apache-2.0 at the ROOT, but the root DOES NOT GOVERN the plugins",
        "source_file": ".../claude-plugins-official/LICENSE (11358 B, sha256 pinned in "
        "command-center/_wfa3_licenses_out.json)",
        "MEASURED_FINDING": "All 54 plugin dirs were probed for their own LICENSE: 42 Apache-2.0 "
        "(byte-identical to root), 1 PROPRIETARY-ALL-RIGHTS-RESERVED (claude-security, "
        "'proprietary to Anthropic, PBC. All rights reserved'), 11 with NO per-plugin "
        "licence at all (asana, context7, firebase, github, gitlab, greptile, "
        "laravel-boost, linear, playwright, serena, terraform). 5 differ from the root "
        "by sha256 (claude-security, discord, fakechat, imessage, telegram).",
        "CONSEQUENCE": "The prior registry's licence string for every plugin in this marketplace - "
        "'see marketplace LICENSE' - routes an adopter to Apache-2.0 for at least one "
        "PROPRIETARY plugin and for 11 plugins that carry no grant. Per-plugin licences must "
        "be read individually.",
    },
    maintenance={
        "state": "registered and freshest of all clones",
        "newest_mtime_utc": "2026-08-09T18:33:24Z",
        "measured_at": MEASURED_AT,
    },
    task_fit="Source of the 5 enabled first-party plugins in this range plus 34 uncatalogued first-party bodies "
    "and 15 external MCP-bridge plugins.",
    stages=["clone", "install plugin"],
    roles=["plugin source"],
    tools=["plugins/ (39)", "external_plugins/ (15)", "LICENSE", "README.md"],
    stop_rules="N/A - a channel.",
    failure_behaviour="N/A - a channel.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source"],
    classification="ADOPT-AS-IS",
    classification_rationale="Live and current. Adopted as a channel; its LICENCE RECORD needed repair, which this "
    "row supplies.",
    measured=measured("marketplace-claude-plugins-official"),
    corrections_vs_prior=[
        "The licence pointer used for 5 plugin rows in the prior registry is unsafe (see "
        "MEASURED_FINDING). Per-plugin sha256 + class table is in "
        "command-center/_wfa3_licenses_out.json."
    ],
    confidence="almost-certain (90-99): 54 LICENSE files hashed and keyword-classified by an exact algorithm; the "
    "proprietary header was read verbatim.",
)

add(
    id="WFA3-077",
    range_index=77,
    counts_toward_range=True,
    prior_id="marketplace-context-mode",
    name="context-mode (openclaw / Mert Koseoglu)",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/marketplaces/context-mode",
        "registration": "ABSENT from known_marketplaces.json (9 keys enumerated; not among them) and "
        "absent from enabledPlugins",
        "prior_record": f"{DOC}:925",
    },
    license={
        "name": "Elastic License 2.0 (ELv2) - source-available, USE-RESTRICTED, not OSI-approved",
        "spdx": "Elastic-2.0",
        "copyright": "Copyright 2026 Mert Koseoglu",
        "source_file": ".../context-mode/LICENSE (3840 B, read) AND package.json 'license':'Elastic-2.0' AND "
        ".claude-plugin/plugin.json 'license':'Elastic-2.0'",
        "verification": "three independent readings agree",
        "CORRECTION": "Prior recorded a bare 'third-party'. ELv2 forbids providing the software to others as a "
        "managed service and forbids circumventing licence keys - a material constraint the "
        "bare label hides.",
        "adoption_constraint": "HAZARD: ELv2 is NOT compatible with an unrestricted internal fork-and-ship "
        "posture. Read in full before any DISTILL/TRANSLATE.",
    },
    maintenance={
        "state": "ORPHANED on disk - present but unregistered and disabled",
        "git_last_commit": "dbbaca2 2026-03-31 github-actions[bot]",
        "file_count": 240,
        "measured_at": MEASURED_AT,
    },
    task_fit="Context-budget management (4 skills: context-mode, ctx-doctor, ctx-stats, ctx-upgrade).",
    stages=["measure context", "diagnose", "upgrade"],
    roles=["context doctor"],
    tools=["skills (4)", "hooks/", "bundled cli/server .mjs"],
    stop_rules="N/A - a channel.",
    failure_behaviour="N/A - a channel.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source", "context accounting"],
    classification="RETIRE",
    classification_rationale="Prior was UNKNOWN-NEEDS-PROBE; the probe is now done and resolves it. Three "
    "independent reasons to retire rather than adopt: (1) unregistered orphan clone - "
    "nothing can invoke it; (2) ELv2 use-restricted licence; (3) it ships its own hooks/ "
    "directory, which is exactly the untrusted-repo auto-loading hook surface AGENTS.md S9 "
    "warns about. If the context-accounting mechanism is wanted, CLEAN-ROOM-REIMPLEMENT it "
    "rather than adopt under ELv2.",
    measured=measured("marketplace-context-mode"),
    confidence="almost-certain (90-99) on licence (3 sources) and non-registration (key set enumerated).",
)

_mkt = [
    (
        "WFA3-078",
        78,
        "marketplace-googlechrome",
        "googlechrome (GoogleChrome/modern-web-guidance)",
        "https://github.com/GoogleChrome/modern-web-guidance",
        "ADOPT-AS-IS",
        "Apache-2.0 confirmed twice (root LICENSE 11560 B + package.json field). Registered, enabled, 185 files.",
        936,
    ),
    (
        "WFA3-079",
        79,
        "marketplace-openai-codex",
        "openai-codex (openai/codex-plugin-cc)",
        "https://github.com/openai/codex-plugin-cc",
        "ADOPT-AS-IS",
        "Apache-2.0 confirmed three times (LICENSE + NOTICE 'Copyright 2026 OpenAI' + package.json field).",
        947,
    ),
    (
        "WFA3-080",
        80,
        "marketplace-claude-reflect-marketplace",
        "claude-reflect-marketplace (bayramannakov)",
        "https://github.com/bayramannakov/claude-reflect",
        "ADOPT-AS-IS",
        "MIT confirmed twice (LICENSE 1092 B 'Copyright (c) 2025 Bayram Annakov' + plugin.json field). "
        "Upstream last commit 2026-03-16 - the stalest enabled channel in the range.",
        958,
    ),
]
for pid, idx, prior, nm, repo, cls, why, line in _mkt:
    m = measured(prior)
    add(
        id=pid,
        range_index=idx,
        counts_toward_range=True,
        prior_id=prior,
        name=nm,
        family="F-plugin",
        candidate_kind="source-channel",
        provenance={
            "upstream_repo": repo,
            "verified_path": m["declared_path"],
            "registration": "present in known_marketplaces.json",
            "prior_record": f"{DOC}:{line}",
        },
        license={
            "name": "Apache-2.0" if "Apache" in why else "MIT",
            "source_file": f"{m['declared_path']}/LICENSE (+ package.json / plugin.json field)",
            "verification": "multiple independent readings agree - see command-center/_wfa3_verify_out.json",
        },
        maintenance={
            "state": "registered",
            "git_last_commit": m.get("git_last_commit"),
            "newest_mtime_utc": m.get("newest_mtime_utc"),
            "file_count": m.get("file_count"),
            "measured_at": MEASURED_AT,
        },
        task_fit="Distribution channel for the plugin(s) adopted from it in this range.",
        stages=["clone", "install plugin"],
        roles=["plugin source"],
        tools=["marketplace manifest", "plugin dirs"],
        stop_rules="N/A - a channel.",
        failure_behaviour="N/A - a channel.",
        benchmark_evidence="",
        mechanisms=["skill/plugin source"],
        classification=cls,
        classification_rationale=why,
        measured=m,
        confidence="almost-certain (90-99) on licence and git date.",
    )

add(
    id="WFA3-081",
    range_index=81,
    counts_toward_range=True,
    prior_id="marketplace-metaswarm-marketplace",
    name="metaswarm-marketplace (dsifry) - shell only",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "upstream_repo": "https://github.com/dsifry/metaswarm-marketplace.git",
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/marketplaces/metaswarm-marketplace",
        "real_plugin_body": "C:/Users/Prekzursil/.claude/plugins/cache/metaswarm-marketplace/metaswarm/0.12.0",
        "registration": "known_marketplaces.json, lastUpdated 2026-07-29T15:31:05.213Z",
        "prior_record": f"{DOC}:969",
    },
    license={
        "name": "NONE at the marketplace clone; MIT at the cached plugin body",
        "source_file": "clone root: 8 licence filenames probed, none present. "
        "Body: .../metaswarm/0.12.0/LICENSE 'MIT License Copyright (c) 2026 Dave Sifry'",
        "verification": "detector control - the same 8-filename probe DID find LICENSE files in 5 sibling "
        "clones, so the null here is a real absence, not a broken matcher",
    },
    maintenance={
        "state": "registered; clone holds 2 files (README shell)",
        "git_last_commit": "9c1df39 2026-06-16 David Sifry",
        "cached_body_version": "0.12.0",
        "measured_at": MEASURED_AT,
    },
    task_fit="Channel for the metaswarm framework (row 66).",
    stages=["clone", "resolve plugin from cache"],
    roles=["plugin source"],
    tools=["README.md"],
    stop_rules="N/A - a channel.",
    failure_behaviour="N/A - a channel.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source"],
    classification="REPAIR",
    classification_rationale="Reclassified from ADOPT-AS-IS. As a provenance record it is broken: the registered "
    "clone contains no licence and no plugin body, so a reader following it cannot "
    "establish terms or find the code. The repair is to record the cache path + the "
    "upstream repo, which this row does.",
    measured=measured("marketplace-metaswarm-marketplace"),
    confidence="almost-certain (90-99): both the empty clone and the MIT body were read directly.",
)

add(
    id="WFA3-083",
    range_index=83,
    counts_toward_range=True,
    prior_id="marketplace-prekzursil-local-mcp",
    name="prekzursil-local-mcp (owner-authored local marketplace)",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "declared_by_prior": "C:/Users/Prekzursil/.claude/plugins/marketplaces/prekzursil-local-mcp "
        "(does NOT exist - verified absent)",
        "verified_path": "C:/Users/Prekzursil/.claude-runtime/local-mcp-marketplace",
        "manifest": ".../local-mcp-marketplace/.claude-plugin/marketplace.json (read: name "
        "'prekzursil-local-mcp', owner 'Prekzursil', 1 plugin 'local-mcp-bridge')",
        "registration": "known_marketplaces.json 'prekzursil-local-mcp', source.type=directory, "
        "installLocation=C:\\Users\\Prekzursil\\.claude-runtime\\local-mcp-marketplace, "
        "lastUpdated 2026-05-28T10:09:23.766Z",
        "prior_record": f"{DOC}:991",
    },
    license={
        "name": "owner-authored / private estate",
        "source_file": "manifest owner field = 'Prekzursil'",
        "adoption_constraint": "none - owner-authored",
    },
    maintenance={
        "state": "PRESENT and registered; body dirs .claude-plugin/ + plugins/local-mcp-bridge",
        "manifest_lastUpdated": "2026-05-28T10:09:23.766Z",
        "measured_at": MEASURED_AT,
    },
    task_fit="Exposes local analyzer and reverse-engineering MCP servers to Claude via the plugin system.",
    stages=["expose local MCP", "install bridge plugin"],
    roles=["local MCP bridge"],
    tools=["plugins/local-mcp-bridge"],
    stop_rules="N/A - a channel.",
    failure_behaviour="N/A - a channel.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source", "local MCP bridge"],
    classification="ADOPT-AS-IS",
    classification_rationale="Prior was UNKNOWN-NEEDS-PROBE on the premise that it is 'NOT present under "
    ".claude/plugins/marketplaces'. Resolved: it is present, at the location its own "
    "registration names. The prior probe looked in the wrong directory.",
    measured=measured("marketplace-prekzursil-local-mcp"),
    corrections_vs_prior=[
        "REFUTED: 'In known_marketplaces.json but NOT present under "
        ".claude/plugins/marketplaces'. It is a source.type=directory marketplace whose "
        "installLocation is ~/.claude-runtime/local-mcp-marketplace - and it IS there, with a "
        "valid marketplace.json and its plugins/local-mcp-bridge body. Absence from "
        "marketplaces/ is expected for a directory-source marketplace, not evidence of absence."
    ],
    confidence="almost-certain (90-99): manifest read verbatim and both body directories listed.",
)

add(
    id="WFA3-084",
    range_index=84,
    counts_toward_range=True,
    prior_id="marketplace-mattpocock-skills",
    name="mattpocock-skills (third-party skill directory)",
    family="F-plugin",
    candidate_kind="source-channel",
    provenance={
        "declared_by_prior": "C:/Users/Prekzursil/.claude/plugins/marketplaces/mattpocock-skills "
        "(does NOT exist - verified absent)",
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/cache/mattpocock-skills/694fa30311e0",
        "registration": "known_marketplaces.json 'mattpocock-skills', source.type=directory "
        "(~/source/repos/mattpocock-skills), lastUpdated 2026-06-11",
        "prior_record": f"{DOC}:1002",
    },
    license={
        "name": "UNKNOWN - NOT-CHECKED",
        "source_file": "not read: only the cache path was located this unit, its contents were not opened",
        "adoption_constraint": "adverse inference until read - treat as all-rights-reserved",
    },
    maintenance={
        "state": "body present ONLY in the plugin cache under a content-hash dir; "
        "the registered directory source was not checked",
        "measured_at": MEASURED_AT,
    },
    task_fit="NOT-CHECKED.",
    stages=NC,
    roles=NC,
    tools=NC,
    stop_rules="NOT-CHECKED.",
    failure_behaviour="NOT-CHECKED.",
    benchmark_evidence="",
    mechanisms=["skill/plugin source"],
    classification="UNKNOWN-NEEDS-PROBE",
    classification_rationale="Kept from prior, but the probe is now NAMED and half-done: the body was located at "
    "cache/mattpocock-skills/694fa30311e0. Settling experiment: list that dir, read any "
    "SKILL.md frontmatter and any LICENSE, and check whether "
    "~/source/repos/mattpocock-skills (the registered directory source) still exists.",
    measured=measured("marketplace-mattpocock-skills"),
    confidence="almost-certain that the declared path is absent and a cache body exists; the CONTENT is "
    "NOT-CHECKED and no classification beyond needs-probe is claimed.",
)

add(
    id="WFA3-085",
    range_index=85,
    counts_toward_range=True,
    prior_id="marketplace-agentbridge",
    name="agentbridge v0.1.30 (RETIRED cross-agent bridge)",
    family="F-plugin",
    candidate_kind="cross-vendor-rail",
    provenance={
        "declared_by_prior": "C:/Users/Prekzursil/.claude/plugins/marketplaces/agentbridge "
        "(does NOT exist - verified absent)",
        "verified_path": "C:/Users/Prekzursil/.claude/plugins/cache/agentbridge/agentbridge/0.1.30",
        "upstream": "npm @raysonmeng/agentbridge",
        "registration": "STILL registered in known_marketplaces.json ('agentbridge' is one of the 9 keys)",
        "prior_record": f"{DOC}:1013",
    },
    license={
        "name": "UNKNOWN - NOT-CHECKED at the cached body",
        "source_file": "not read this unit",
        "adoption_constraint": "moot - the artefact is retired, not a candidate for adoption",
    },
    maintenance={
        "state": "RETIRED. Two mechanically independent estate signals: `claude plugin list` reports "
        "v0.1.30 Status: disabled, AND ~/.claude/settings.json enabledPlugins"
        "['agentbridge@agentbridge']=false. Corroborated here by a third: 'agentbridge' is "
        "absent from the 9 true enabledPlugins keys measured this unit.",
        "cached_version": "0.1.30",
        "measured_at": MEASURED_AT,
    },
    task_fit="Was: cross-agent Claude<->Codex bridge with budget pacing (get_budget / check_budget).",
    stages=["register", "message", "budget query"],
    roles=["bridge daemon"],
    tools=["MCP tools (removed)"],
    stop_rules="N/A - retired.",
    failure_behaviour="Windows-broken; its daemon does not run. Repo CLAUDE.md records that acting on the old "
    "protocol makes an agent call removed tools and wait for a peer that is not listening.",
    benchmark_evidence="Its retirement removed the only automated budget-pacing enforcement; pacing is now "
    "advisory. Recorded in three estate files (repo CLAUDE.md, ~/CLAUDE.md, ~/AGENTS.md).",
    mechanisms=["cross-vendor rail (retired)", "budget pacing (removed)"],
    classification="RETIRE",
    classification_rationale="Kept from prior and strengthened: the registration is stale in known_marketplaces.json "
    "while every enablement signal says disabled. Its replacement rails "
    "(codex mcp-server; mcp_agent_mail) are already live, so nothing is lost by retiring "
    "the registration. The dangling registry entry is the actionable residue.",
    measured=measured("marketplace-agentbridge"),
    confidence="almost-certain (90-99) on retirement (3 independent signals) and on the cache body path.",
)

# --------------------------------------------------------------------------------------
# 86-96  owner-authored orchestration skills (live vault, measured)
# --------------------------------------------------------------------------------------
_skills = [
    (
        "WFA3-086",
        86,
        "skill-workflow-authoring",
        "workflow-authoring",
        1026,
        "Authoring saved Claude Code Workflows correctly.",
        ["author", "lint", "fan-out", "schema fan-in"],
        ["workflow author"],
        ["SKILL.md"],
        "plan-lint stage-0 must pass before a workflow is run.",
        "Documents the failure modes it prevents: args-as-string, banned Date.now(), one-level nesting limit, "
        "deadlock from a hung agent in parallel().",
        [
            "fan-out topology",
            "schema fan-in",
            "worktree isolation",
            "per-WU pipeline",
            "plan-lint stage-0",
        ],
        "ADOPT-AS-IS",
        "The normative spec for the runtime this whole program targets; 20310 B and live in BOTH vaults.",
    ),
    (
        "WFA3-087",
        87,
        "skill-workflow-monitor",
        "workflow-monitor",
        1037,
        "Live monitoring of running workflows; vendors monitorcore.",
        ["attach", "render board", "export"],
        ["monitor operator"],
        ["monitorcore/", "codex_monitor.py", "fixtures/", "conftest.py"],
        "N/A - observational.",
        "Estate-recorded hazard: stall detection from file mtimes alone is impossible; only a live-activity count is "
        "defensible.",
        ["monitor", "board", "cockpit", "export"],
        "ADOPT-AS-IS",
        "Executable (110 files, scripts present) and the only observability surface for the fan-out this program runs.",
    ),
    (
        "WFA3-088",
        88,
        "skill-orchestration-patterns",
        "orchestration-patterns",
        1048,
        "Cross-vendor orchestration patterns for this Windows workspace.",
        ["architect emits change-spec", "editor applies", "lint ladder"],
        ["architect", "editor", "lead", "worker"],
        ["SKILL.md"],
        "max_reflections=3 on the per-edit lint ladder; escalate to the lead on N worker failures.",
        "Escalate-not-grind: on repeated worker failure the lead re-decomposes rather than retrying.",
        [
            "architect/editor split",
            "sandbox ladder",
            "repo map",
            "failure-threshold escalation",
            "retry cap",
        ],
        "ADOPT-AS-IS",
        "Carries the explicit numeric stop rule (max_reflections=3) that this program's stopping-rule work needs.",
    ),
    (
        "WFA3-089",
        89,
        "skill-gem-hunt",
        "gem-hunt",
        1059,
        "Wide multi-lens discovery fan-out then a consolidated adopt/prune decision.",
        ["scout", "wide fan-out", "synthesis", "decision queue"],
        ["lens agents", "consolidator"],
        ["SKILL.md"],
        "Decision-queue completeness, not agent exhaustion.",
        NC,
        ["discovery stage", "wide fan-out", "synthesis", "decision queue"],
        "ADOPT-AS-IS",
        "The estate's proven DISCOVERY topology; this very archaeology phase is an instance of its shape.",
    ),
    (
        "WFA3-090",
        90,
        "skill-grill-me-extensive",
        "grill-me-extensive",
        1070,
        "Program-scale grilling of an under-specified decision space.",
        [
            "scout",
            "brainstorm fan-out",
            "categorized decision list",
            "one-question loop",
        ],
        ["grill master", "brainstormers"],
        ["SKILL.md", "references/"],
        "One decision at a time until the decision list is exhausted; every decision durably captured.",
        NC,
        ["scout", "fan-out", "decision ledger", "one-question loop"],
        "ADOPT-AS-IS",
        "Directly reusable as the interactive counterpart to the council protocols this program specifies.",
    ),
    (
        "WFA3-091",
        91,
        "skill-council",
        "council",
        1081,
        "Four-voice council for ambiguous decisions and go/no-go calls.",
        ["convene", "structured disagreement", "decide"],
        ["4 named voices"],
        ["SKILL.md"],
        "Go/no-go emitted after structured disagreement; quorum rule " + NC,
        NC,
        ["council", "structured disagreement"],
        "ADOPT-AS-IS",
        "The estate's existing council primitive and the natural CouncilSpec conformance target. Oldest file in the "
        "range (mtime 2026-05-28) - stable, not stale.",
    ),
    (
        "WFA3-092",
        92,
        "skill-critique-panel",
        "critique-panel",
        1092,
        "Multi-persona critique panel with typed schemas and a rubric.",
        ["persona critique", "rubric score", "synthesis"],
        ["personas (schema-typed)"],
        [
            "critique_panel.mjs",
            "panel_schema.mjs",
            "persona.schema.json",
            "synthesis.schema.json",
            "panel_rubric.md",
            "fixtures/",
            "tests/",
            "package.json",
        ],
        "Synthesis emitted once every persona has scored; rubric thresholds in panel_rubric.md.",
        NC,
        ["persona panel", "typed schema", "rubric scoring", "synthesis"],
        "ADOPT-AS-IS",
        "One of only two rows in the range shipping EXECUTABLE schema files plus tests - the strongest reuse target "
        "for the council/preset work (persona.schema.json + synthesis.schema.json are directly consumable).",
    ),
    (
        "WFA3-093",
        93,
        "skill-rubric-verifier",
        "rubric-verifier",
        1103,
        "Score candidates against a rubric in code rather than by opinion.",
        ["load rubric", "score", "rank"],
        ["verifier"],
        ["SKILL.md", "score_candidates.py"],
        "Threshold-based on the rubric; exact numbers " + NC,
        NC,
        ["rubric scoring", "code-computed verdict"],
        "ADOPT-AS-IS",
        "Ships score_candidates.py - a code-computed score, which is exactly the estate rule that mechanical "
        "comparisons must not be delegated to LLM judgement.",
    ),
    (
        "WFA3-094",
        94,
        "skill-agent-as-judge",
        "agent-as-judge",
        1114,
        "Advisory evidence-citing judge over a Definition of Done.",
        [
            "decompose DoD",
            "cite evidence per item",
            "execute-to-confirm",
            "ICD-203 score",
        ],
        ["judge"],
        ["SKILL.md"],
        "NEVER gates: 100% advisory, SHADOW mode. Auto-demotes while kappa < 0.6 against claude-reflect corrections.",
        "Fails open by design - it observes and logs, never blocks.",
        [
            "advisory judge",
            "chain-of-custody evidence",
            "kappa calibration",
            "shadow mode",
        ],
        "ADOPT-AS-IS",
        "Its self-imposed non-gating constraint is precisely the guard this program's completion predicate needs "
        "(a same-vendor judge shares the fixer's blind spots).",
    ),
    (
        "WFA3-095",
        95,
        "skill-execution-grounded-bon",
        "execution-grounded-bon",
        1125,
        "Pick among N candidate patches by EXECUTION consensus, not model opinion.",
        [
            "synthesize distinguishing inputs",
            "execute all candidates",
            "cluster by behaviour",
            "knock out crashers",
            "aspect jury",
        ],
        ["candidate generators (cross-vendor)", "jury"],
        ["SKILL.md", "rerank.mjs"],
        "Winner = the behavioural cluster where an independent Claude candidate and an independent Codex candidate "
        "agree; ties broken by a BoN-MAV aspect jury.",
        "SHADOW mode: observe + log only, never blocks.",
        [
            "execution consensus",
            "behavioural diff",
            "cross-vendor independence",
            "shadow mode",
        ],
        "ADOPT-AS-IS",
        "Ships rerank.mjs and cites external evidence (JudgeBench: model-opinion rerank approx chance) - the "
        "strongest anti-LLM-judgement mechanism in the range.",
    ),
    (
        "WFA3-096",
        96,
        "skill-diff-blind-test-synth",
        "diff-blind-test-synth",
        1136,
        "Synthesize tests from the SPEC ONLY, never the diff, then run both trees.",
        [
            "read spec + public API",
            "synthesize tests",
            "run pre-patch (expect FAIL)",
            "run patched (expect PASS)",
        ],
        ["independent test synthesizer"],
        ["SKILL.md"],
        "Expected pattern is FAIL-then-PASS; any divergence flags a spec-miss or an over/under-fitted patch.",
        "SHADOW mode: observe + log only, never blocks.",
        ["diff-blind test synthesis", "both-states control", "spec conformance"],
        "ADOPT-AS-IS",
        "A literal implementation of the both-states rule this program is required to honour; cites UTBoost "
        "(arXiv 2506.09289).",
    ),
]
for (
    pid,
    idx,
    prior,
    stem,
    line,
    fit,
    stages,
    roles,
    tools,
    stop,
    fail,
    mech,
    cls,
    why,
) in _skills:
    m = measured(prior)
    add(
        id=pid,
        range_index=idx,
        counts_toward_range=True,
        prior_id=prior,
        name=f"skills/{stem}",
        family="G-skill",
        candidate_kind="workflow-mechanism-skill",
        provenance={
            "verified_path": f"C:/Users/Prekzursil/.agents/skills/{stem}",
            "skill_md": f"C:/Users/Prekzursil/.agents/skills/{stem}/SKILL.md",
            "also_deployed_at": f"C:/Users/Prekzursil/.claude/skills/{stem}"
            if (VROW[prior].get("claude_live") or {}).get("exists")
            else "NOT deployed to ~/.claude/skills (agents vault only)",
            "origin": "owner-authored; agent-skills-toolchain repo projects into the live vault",
            "prior_record": f"{DOC}:{line}",
        },
        license={
            "name": "owner-authored / private estate",
            "source_file": "no LICENSE file - estate-internal artefact; origin asserted by the "
            "agent-skills-toolchain repo being the source of truth for the vault",
            "adoption_constraint": "none - owner-authored",
        },
        maintenance={
            "state": "DEPLOYED live",
            "vaults": ["agents-live"]
            + (
                ["claude-live"]
                if (VROW[prior].get("claude_live") or {}).get("exists")
                else []
            ),
            "skill_md_bytes": m.get("skill_md_bytes"),
            "skill_md_mtime_utc": m.get("skill_md_mtime_utc"),
            "dir_file_count": m.get("vault_file_count"),
            "measured_at": MEASURED_AT,
        },
        task_fit=fit,
        stages=stages,
        roles=roles,
        tools=tools,
        stop_rules=stop,
        failure_behaviour=fail,
        benchmark_evidence="See classification_rationale where an external citation exists; otherwise NOT-CHECKED.",
        mechanisms=mech,
        classification=cls,
        classification_rationale=why,
        measured=m,
        confidence="almost-certain (90-99) on existence/bytes/mtime/vault placement (measured this unit); "
        "likely (55-80) on stages and stop rules - carried from the prior catalogue's summary, "
        "bodies NOT re-read by this unit.",
    )

# --------------------------------------------------------------------------------------
# 2 NEW candidates replacing the 2 rejects - from the archaeology's own declared gap
# --------------------------------------------------------------------------------------
add(
    id="WFA3-NEW-01",
    range_index=74,
    counts_toward_range=True,
    prior_id=None,
    name="claude-security v0.10.0 (Anthropic) - challenged-finding scan workflow",
    family="F-plugin",
    candidate_kind="workflow-mechanism-pack",
    provenance={
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official/plugins/"
        "claude-security",
        "manifest": ".../claude-security/.claude-plugin/plugin.json (read verbatim)",
        "workflow_artifact": ".../claude-security/workflows/scan.js (31932 B)",
        "agents": ".../claude-security/agents/{claude-security,explore,patch-generator,patch-verifier,"
        "scan-inventory,scan-researcher,scan-verifier}.md",
        "upstream_repo": "https://github.com/anthropics/claude-plugins-official",
        "why_new": "The prior archaeology's 'NOT searched' section names the plugin bodies as an unsearched gap: "
        "'The plugin CACHE ... only the marketplace clones were listed.' It catalogued the 9 ENABLED "
        "plugins and the 11 marketplaces but none of the 39 first-party bodies. This is one of them and "
        "appears nowhere in the 284-row prior registry (id-set checked).",
    },
    license={
        "name": "PROPRIETARY - ALL RIGHTS RESERVED",
        "spdx": "NOT-OPEN-SOURCE",
        "copyright": "Copyright (c) 2026 Anthropic, PBC. All rights reserved.",
        "source_file": ".../plugins/claude-security/LICENSE (1500 B, read verbatim: 'This software, including "
        "its prompts, agent and skill definitions, workflows, server code, and documentation "
        '(the "Plugin"), is proprietary to Anthropic, PBC\')',
        "verification": "sha256 differs from the marketplace root Apache-2.0 LICENSE; keyword-classified "
        "PROPRIETARY-ALL-RIGHTS-RESERVED - the ONLY such row among 54 plugin dirs probed",
        "adoption_constraint": "HARD BLOCK on ADOPT/TRANSLATE/DISTILL of its prompts, agents or workflow code. "
        "The licence explicitly covers prompts and agent definitions, so paraphrasing "
        "them into estate code is a licence question, not a clean-room. Only the "
        "ARCHITECTURE (challenge-then-tally) may be independently reimplemented.",
    },
    maintenance={
        "state": "present in the marketplace clone but NOT enabled "
        "(absent from the 9 true enabledPlugins keys)",
        "version": "0.10.0",
        "newest_mtime_utc": "2026-08-09T21:33Z (clone refresh)",
        "measured_at": MEASURED_AT,
    },
    task_fit="Deep vulnerability scanning of first-party code at a chosen EFFORT TIER, with adversarial challenge "
    "of every finding before it is reported, then targeted patches each verified by an agent panel.",
    stages=[
        "explore",
        "scan-inventory",
        "scan-researcher",
        "scan-verifier (challenge)",
        "tally computed in code",
        "patch-generator",
        "patch-verifier (panel)",
        "apply on user choice",
    ],
    roles=[
        "explore",
        "scan-inventory",
        "scan-researcher",
        "scan-verifier",
        "patch-generator",
        "patch-verifier",
        "claude-security (lead)",
    ],
    tools=[
        "workflows/scan.js (31932 B)",
        "agents/ (7)",
        "skills/claude-security",
        "hooks/ (3, incl. hooks.json)",
        "scripts/ (3)",
        "SECURITY.md",
    ],
    stop_rules="Effort TIER selects the budget; a finding survives only if it survives its challenge; "
    "'the verification tally computed in code' (manifest, verbatim) is the reported figure. "
    "Exact tier thresholds "
    + NC
    + " - settled by reading workflows/scan.js and the README.",
    failure_behaviour="Findings that fail their challenge are dropped rather than reported (false-positive "
    "suppression by construction); patches are proposed, never auto-applied - "
    "'that you apply when you choose'.",
    benchmark_evidence="No benchmark in-tree. NOT-CHECKED.",
    mechanisms=[
        "effort tiers",
        "adversarial challenge of every finding",
        "tally computed in code (not by opinion)",
        "panel-verified patches",
        "propose-not-apply",
        "banner hook",
    ],
    classification="CLEAN-ROOM-REIMPLEMENT",
    classification_rationale="Its architecture is the closest first-party match to this program's own verification "
    "doctrine - challenge each finding before reporting, and compute the tally in CODE "
    "rather than trusting the model. But the licence is proprietary and explicitly covers "
    "prompts and agent definitions, so ADOPT/TRANSLATE/DISTILL are all barred. The only "
    "lawful route is an independent reimplementation of the shape.",
    measured={
        "body_surface": surface("claude-security"),
        "license_class_from_probe": lics["plugins"]
        .get("claude-security", {})
        .get("class"),
        "identical_to_marketplace_root": lics["plugins"]
        .get("claude-security", {})
        .get("identical_to_root"),
        "workflow_file_bytes": 31932,
    },
    confidence="almost-certain (90-99) on licence, version, agent roster and the existence of workflows/scan.js "
    "(all read directly); likely (55-80) on the stage ORDER, which is inferred from agent filenames "
    "plus the manifest description - scan.js was NOT read.",
)

add(
    id="WFA3-NEW-02",
    range_index=82,
    counts_toward_range=True,
    prior_id=None,
    name="math-olympiad v0.1.0 (Anthropic) - fresh-context adversarial verifier",
    family="F-plugin",
    candidate_kind="workflow-mechanism-pack",
    provenance={
        "verified_body": "C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official/plugins/"
        "math-olympiad",
        "skill": ".../math-olympiad/skills/math-olympiad/SKILL.md (frontmatter read verbatim, version 0.1.0)",
        "references": ".../skills/math-olympiad/references/{adversarial_prompts,attempt_agent,"
        "known_constructions,model_tier_defaults,presentation_prompts,solver_heuristics,"
        "verifier_patterns}.md",
        "upstream_repo": "https://github.com/anthropics/claude-plugins-official",
        "why_new": "Same declared gap as WFA3-NEW-01: one of the 39 first-party plugin bodies the prior "
        "archaeology never catalogued. Absent from the 284-row prior registry.",
    },
    license={
        "name": "Apache-2.0",
        "spdx": "Apache-2.0",
        "source_file": ".../plugins/math-olympiad/LICENSE",
        "verification": "sha256 byte-identical to the marketplace root Apache-2.0 LICENSE",
        "adoption_constraint": "Apache-2.0 permits TRANSLATE/DISTILL with attribution - unlike WFA3-NEW-01.",
    },
    maintenance={
        "state": "present in the marketplace clone; NOT enabled",
        "version": "0.1.0",
        "measured_at": MEASURED_AT,
    },
    task_fit="Nominally competition math - but the transferable payload is a domain-agnostic "
    "attempt -> strip -> fresh-context adversarial verify -> calibrated-confidence-or-abstain loop.",
    stages=[
        "solve (thinking only, no tools)",
        "strip thinking from the proof",
        "fresh-context verifier attacks with SPECIFIC failure patterns",
        "calibrated confidence or abstain",
        "presentation (PDF) only after verification passes",
    ],
    roles=[
        "solver (attempt_agent)",
        "adversarial verifier (fresh context)",
        "presenter",
    ],
    tools=[
        "skills/math-olympiad",
        "7 reference docs incl. verifier_patterns.md, adversarial_prompts.md, "
        "model_tier_defaults.md",
    ],
    stop_rules="Verification must PASS before presentation. Explicit abstain rule, quoted verbatim: "
    "'Say \"no confident solution\" - wrong-and-confident is worse than honest abstain.' "
    "Also a two-strikes rule: 'Same gap twice -> step back'.",
    failure_behaviour="Abstains rather than bluffs; emits calibrated confidence instead of a binary claim.",
    benchmark_evidence="Claims adversarial verification 'catches the errors self-verification misses'. No numeric "
    "benchmark in-tree; NOT-CHECKED.",
    mechanisms=[
        "strip-thinking-before-verify (anti-agreement-bias)",
        "fresh-context adversarial verifier",
        "specific failure patterns not generic 'check logic'",
        "calibrated confidence with honest abstain",
        "two-strikes step-back",
        "model tier defaults",
    ],
    classification="DISTILL",
    classification_rationale="The math domain is irrelevant to this program; the VERIFIER DESIGN is not. Three of "
    "its rules are independent first-party restatements of estate rules this program must "
    "honour - fresh-context re-derivation, two-strikes pivot, and calibrated-confidence "
    "with abstain - and it adds one the estate does NOT have written down: STRIP THE "
    "REASONING before handing work to a verifier, because a verifier that sees the "
    "reasoning is biased toward agreement. Apache-2.0 permits the distillation.",
    measured={
        "body_surface": surface("math-olympiad"),
        "license_class_from_probe": lics["plugins"]
        .get("math-olympiad", {})
        .get("class"),
        "identical_to_marketplace_root": lics["plugins"]
        .get("math-olympiad", {})
        .get("identical_to_root"),
    },
    confidence="almost-certain (90-99) on licence, version, reference-file roster and the quoted stop rules "
    "(SKILL.md frontmatter and body head read verbatim); the 7 reference docs were NOT opened.",
)

# --------------------------------------------------------------------------------------
counted = [r for r in ROWS if r["counts_toward_range"]]
assert len({r["id"] for r in ROWS}) == len(ROWS), "duplicate ids"
header = {
    "id": "WFA3-MANIFEST",
    "_manifest": True,
    "unit": "build/wfa-3",
    "range": "candidates 65-96 of 160",
    "generated_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "generated_by": "command-center/_wfa3_build_registry.py from three measured probe outputs "
    "(_wfa3_verify_out.json, _wfa3_plugincache_out.json, _wfa3_licenses_out.json)",
    "rows_total": len(ROWS),
    "candidates_counted_toward_range": len(counted),
    "rows_rejected_not_counted": len(ROWS) - len(counted),
    "slice_definition": "Sibling-disjoint deterministic anchor: indices 65-96 (1-based) of the ordered "
    "candidates[] array in 08-WORKFLOW-CANDIDATE-REGISTRY.json (284 rows) = all 21 F-plugin "
    "rows + the first 11 G-skill rows. wfa-1 declared 1-32, wfa-2 33-64, so no overlap is "
    "possible.",
    "honest_composition": {
        "verified_prior_anchors_counted": 30,
        "prior_anchors_REJECTED_as_not_materially_distinct": 2,
        "NEW_candidates_added_from_a_declared_unsearched_gap": 2,
        "of_the_30_counted_anchors": {
            "workflow-mechanism-pack_or_skill": 20,
            "source-channel": 9,
            "cross-vendor-rail": 1,
        },
        "DISCLOSURE": "9 of the 32 counted rows are SOURCE CHANNELS (marketplaces), not workflows. They carry the "
        "provenance and licence records that everything downstream inherits, and the prior "
        "archaeology counted them in family F, so they are kept and tagged rather than silently "
        "dropped or silently counted. If the orchestrator's 160-candidate floor is meant to count "
        "only executable workflow mechanisms, this unit contributes 23, not 32. Stated so the floor "
        "is not accidentally inflated.",
    },
    "classification_histogram": {},
    "corrections_to_prior_archaeology": [
        "REFUTED: temp_1781578811820 is NOT a byte-level duplicate of anthropic-agent-skills "
        f"({_dup.get('differing_hash')} shared paths differ by sha256; {_dup.get('only_in_t_count')} paths exist "
        "only in the temp clone). The prior 'RETIRE the temp clone' action would destroy those. Diff-then-retire.",
        "REFUTED: prekzursil-local-mcp is NOT missing. It is a source.type=directory marketplace whose registered "
        "installLocation is ~/.claude-runtime/local-mcp-marketplace, and it is present there with a valid manifest.",
        "PROVENANCE DEFECT (3 rows): the declared paths for prekzursil-local-mcp, mattpocock-skills and "
        "agentbridge do not exist. Real bodies located for the latter two under ~/.claude/plugins/cache/.",
        "PROVENANCE DEFECT (2 rows): superpowers and remember are given the marketplace clone as provenance, but "
        "neither is among that clone's 39 plugin dirs; both bodies are version-keyed in the plugin cache.",
        "LICENCE DEFECT (systemic): the prior string 'third-party (per-plugin; see marketplace LICENSE)' was used "
        "for every claude-plugins-official plugin. The root LICENSE is Apache-2.0 but does not govern: measured "
        "42 Apache-2.0 / 1 PROPRIETARY-ALL-RIGHTS-RESERVED / 11 with no per-plugin licence at all. superpowers is "
        "MIT (Jesse Vincent) and remember is a bespoke 'Community License' (DPT) - neither is Apache-2.0.",
        "LICENCE DEFECT: context-mode is Elastic License 2.0 (use-restricted), recorded before as bare "
        "'third-party'.",
        "LICENCE GAP: anthropic-agent-skills and metaswarm-marketplace clones carry NO root licence file at all "
        "(detector control: the same 8-filename probe found LICENSE files in 5 sibling clones).",
        "DRIFT since the 2026-08-07 archaeology: skills/workflow-monitor measured 4683 B / 110 files today vs the "
        "prior 4998 B / 178 files. The corpus is moving; every size in this registry carries measured_at.",
        "MINOR DOC DRIFT: project CLAUDE.md says metaswarm has '18 specialized agents'; the plugin manifest says "
        "19 and agents/ contains 19.",
    ],
    "coverage_and_gaps": {
        "read_this_unit": [
            "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md headings + counts + findings + coverage sections",
            "08-WORKFLOW-CANDIDATE-REGISTRY.json (all 284 rows; the 32-row anchor printed in full)",
            "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json (466 nodes / 1025 edges; schema + counts + "
            "licence rules)",
            "~/.claude/settings.json enabledPlugins (99 keys, 9 true)",
            "~/.claude/plugins/known_marketplaces.json (9 keys, verbatim)",
            "all 8 marketplace clones + 54 plugin dirs + 91 cache plugin dirs (enumerated)",
            "54 per-plugin LICENSE files (sha256 + keyword class)",
            "resolved bodies: superpowers 6.2.0, remember 0.18.0, metaswarm 0.12.0, claude-security, "
            "math-olympiad, receipts, code-modernization",
            "11 live skill dirs + their SKILL.md bytes/mtimes",
        ],
        "NOT_read_this_unit": [
            "the BODIES of the 11 owner-authored skills (rows 86-96) - their stages/stop-rules are carried from "
            "the prior catalogue and tagged likely, not almost-certain",
            "claude-security/workflows/scan.js (31932 B) - so its tier thresholds are NOT-CHECKED",
            "the 7 math-olympiad reference docs",
            "cache/mattpocock-skills/694fa30311e0 contents and licence (row 84 stays UNKNOWN-NEEDS-PROBE)",
            "cache/agentbridge/agentbridge/0.1.30 licence",
            "the remaining 32 uncatalogued first-party plugin bodies and 15 external_plugins - only surface "
            "counts and manifest descriptions were taken. plugin-dev (57), mcp-server-dev (19), "
            "code-modernization (18 with a named 10-stage pipeline), security-guidance (12 hooks), "
            "pr-review-toolkit (6 agents) and code-review (confidence-scored multi-agent) are the strongest "
            "remaining leads for a future range",
            "the 91-dir plugin cache beyond superpowers/remember/metaswarm - it holds ~37 plugins with no "
            "marketplace-clone counterpart (agentforce-adlc, aikido, brightdata-plugin, buildkite, "
            "chrome-devtools-mcp, circleback, cloudflare, coderabbit, codspeed, ...), an entirely untapped "
            "reservoir inside family F",
        ],
        "detector_controls_run": [
            "path existence: known-present marketplaces/claude-plugins-official -> True; known-absent "
            "marketplaces/__definitely_not_here__ -> False",
            "plugin dir probe: known-present hookify -> True; known-absent __nope__ -> False",
            "licence-absence: the 8-filename LICENSE probe that returned NOTHING for anthropic-agent-skills and "
            "metaswarm-marketplace DID return hits for 5 sibling clones, so the null is a real absence",
            "prov-graph join returned 0/32 on a first pass; that was a DETECTOR FAILURE (node ids are prefixed "
            "'cand:'), diagnosed and recorded rather than reported as a finding",
            "sibling-collision check ran TWICE with different keys: by prior-registry id (0 overlap, but that "
            "detector could not see workflow-candidates-4/-5 at all because they use a WFC-00NN scheme - an "
            "unmeasurable, NOT a clean result) and then by normalised NAME, which could see all four and found "
            "exactly 1 hit. Control: 36/36 self-overlap on both passes.",
        ],
    },
    "cross_file_consistency": {
        "collision_check": "0 real candidate collisions across the 4 populated sibling registries. Boundary "
        "verified: workflow-candidates-4 begins at WFC-0097 (skill two-tier-verify = prior "
        "index 97), immediately after this file's last index 96.",
        "one_name_collision_adjudicated": "The normalised-name pass flagged 'ralph-loop' against "
        "workflow-candidates-4 WFC-0105. NOT a duplicate: WFC-0105 is the "
        "owner-authored VAULT SKILL at ~/.agents/skills/ralph-loop/SKILL.md with "
        "licence UNDECLARED; this file's row 67 is the THIRD-PARTY PLUGIN at "
        ".claude/plugins/marketplaces/claude-plugins-official/plugins/ralph-loop, "
        "Apache-2.0, v1.0.0, shipping commands/hooks/scripts. Different artefact, "
        "different provenance, different licence. Both units independently "
        "classified their row ADOPT-WITH-WRAPPER. The wave now holds FIVE ralph "
        "artefacts (1 plugin + 4 vault skills: ralph-loop, ralph-hats, "
        "ralph-orchestrator-setup, ralphinho-rfc-pipeline) - a genuine MERGE "
        "decision for the orchestrator, not a double-count.",
        "licence_label_divergence_FLAGGED_NOT_RESOLVED": "For owner-authored vault skills this file records licence "
        "'owner-authored / private estate' with source_file 'no "
        "LICENSE file'; workflow-candidates-4 records the same "
        "class of artefact as 'UNDECLARED'. Same underlying fact, "
        "two labels. The sibling's is the more conservative. "
        "Surfacing rather than silently picking one - the union "
        "needs ONE label or the licence histogram will be wrong.",
    },
    "residual_risk": "Rows 86-96 (the 11 owner skills) are the weakest evidence in this file: existence, bytes, "
    "mtime and vault placement are measured, but stages/roles/stop-rules are inherited from the "
    "prior catalogue's summaries. Settling experiment: read the 11 SKILL.md bodies (approx 115 KB "
    "total) and replace each stop_rules string with a quoted predicate.",
}
hist = {}
for r in ROWS:
    hist[r["classification"]] = hist.get(r["classification"], 0) + 1
header["classification_histogram"] = hist

payload = [header] + ROWS
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
print(
    f"rows_total={len(ROWS)}  counted={len(counted)}  rejected={len(ROWS) - len(counted)}"
)
print("classification histogram:", hist)
