"""Frozen I-family corpus: 31 slash commands + detector controls + skill stubs.

Live ~/.claude/commands and 08-WORKFLOW-CANDIDATE-REGISTRY.json are absent
on this Linux worktree. IDs include the eight registry sample ids from
WFA-0042 inspect plus names from the AUD-0014 command tree, sized to the
catalogued I-command family n=31. Bodies are native markdown for the
adapter; this is not a claim they were copied from the Windows live tree.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
IFAMILY = FIX / "i-family"
CONTROLS = FIX / "controls"
SKILLS = FIX / "skills"

# Eight ids from command-center/p2-wave/probes/WFA-0042/_inspect_source_out.json
SAMPLE_IDS = [
    "cmd-start-task",
    "cmd-orchestrate",
    "cmd-multi-workflow",
    "cmd-multi-plan",
    "cmd-multi-execute",
    "cmd-multi-frontend",
    "cmd-multi-backend",
    "cmd-review-design",
]


def _own(description: str, steps: list[str], extra_fm: str = "") -> str:
    body = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    extra = extra_fm if extra_fm.endswith("\n") or extra_fm == "" else extra_fm + "\n"
    return f"---\ndescription: {description}\n{extra}---\n\n{body}\n"


def _alias(description: str, skill: str) -> str:
    return (
        f"---\ndescription: {description}\nskill: {skill}\n---\n\n"
        f"Use the `{skill}` skill with $ARGUMENTS.\n"
    )


OWN: dict[str, str] = {
    "cmd-start-task": _own(
        "Start a bounded task with an explicit gate",
        [
            "Name the task, the owner, and the stop condition before any edit.",
            "Inventory the files that will change and refuse unbounded scope.",
            "Execute the smallest change that meets the stop condition.",
            "Gate: do not claim done until the stop condition is observed on disk.",
        ],
        extra_fm="argument-hint: [task]\nallowed-tools: Read, Edit, Bash\n",
    ),
    "cmd-orchestrate": _own(
        "Fan-out independent streams then barrier",
        [
            "Split the request into independent streams with one owner each.",
            "Dispatch each stream with its own stop rule.",
            "Wait on the barrier until every stream returns or times out.",
            "Merge artifacts and refuse if any stream skipped its gate.",
        ],
    ),
    "cmd-multi-workflow": _own(
        "Run a multi-workflow sequence",
        [
            "Select the workflow sequence from the request.",
            "Run each workflow in listed order; do not skip a failed gate.",
            "Record per-workflow receipts before starting the next.",
            "Stop on the first workflow that fails its gate.",
        ],
    ),
    "cmd-multi-plan": _own(
        "Plan across several workstreams",
        [
            "Write one plan per workstream with inputs, outputs, and a stop rule.",
            "Mark dependencies between plans; do not invent hidden edges.",
            "Present the plan set for a human checkpoint before execution.",
        ],
    ),
    "cmd-multi-execute": _own(
        "Execute an already-approved multi-plan",
        [
            "Load the approved plan set; refuse if any plan lacks a stop rule.",
            "Execute ready plans; hold dependents until upstream receipts exist.",
            "Barrier: do not merge until every planned stream has a receipt.",
        ],
    ),
    "cmd-multi-frontend": _own(
        "Frontend stream of a multi-agent split",
        [
            "Scope UI files only; do not edit backend contracts.",
            "Implement the visible change against the locked API.",
            "Verify the UI path by exercising the user-visible control, not a screenshot alone.",
        ],
    ),
    "cmd-multi-backend": _own(
        "Backend stream of a multi-agent split",
        [
            "Scope service and schema files only; do not restyle the UI.",
            "Implement the contract change and the failing test that names it.",
            "Gate: refuse to report done if the contract test was not run.",
        ],
    ),
    "cmd-review-design": _own(
        "Adversarial design review",
        [
            "Restate the design claim in one sentence.",
            "List invariants the design must preserve.",
            "Attack each invariant with a concrete counterexample.",
            "Gate: block the design if any invariant is untested.",
        ],
    ),
    "cmd-plan": _own(
        "Single-stream plan with a stop rule",
        [
            "Write the plan as ordered stages with a named stop rule.",
            "Name files that will change; unnamed files are out of scope.",
            "Human checkpoint before any write.",
        ],
    ),
    "cmd-quality-gate": _own(
        "Quality gate before merge",
        [
            "Run the unit's own tests; do not substitute a parent suite.",
            "Diff coverage against the files this change touched.",
            "Gate: refuse merge if a touched path has no test and no explicit waiver.",
        ],
    ),
    "cmd-loop-start": _own(
        "Start a bounded agent loop",
        [
            "Declare max iterations and the convergence predicate.",
            "Run one iteration; record the observation that feeds the predicate.",
            "Stop when the predicate holds or max iterations is reached; never spin open-ended.",
        ],
    ),
    "cmd-code-review": _own(
        "Code review with cited lines",
        [
            "Read the diff and quote the lines that decide each finding.",
            "Classify each finding as blocking or advisory with a reason.",
            "Gate: a finding without a file:line cite is dropped, not kept as vibe.",
        ],
    ),
    "cmd-handle-pr-comments": _own(
        "Resolve PR comments in order",
        [
            "List every unresolved comment with its path and line.",
            "Fix or refute each comment with a cited change.",
            "Reply only after the on-disk change exists.",
        ],
    ),
    "cmd-pr-shepherd": _own(
        "Shepherd a PR to merge-ready",
        [
            "Check CI, review, and required labels.",
            "Push only after local probes pass.",
            "Do not merge from this command; stop at merge-ready.",
        ],
    ),
    "cmd-setup": _own(
        "One-time workspace setup",
        [
            "Install declared tools at pinned versions.",
            "Write a receipt of versions actually present.",
            "Gate: refuse to continue if a pin is missing.",
        ],
    ),
    "cmd-evolve": _own(
        "Evolve a skill from a measured miss",
        [
            "Name the miss with a probe that currently fails.",
            "Change the smallest surface that makes that probe pass.",
            "Re-run the probe; keep the miss if it still fails.",
        ],
    ),
    "cmd-verify": _own(
        "Verify a claimed fix",
        [
            "Re-run the failing probe that motivated the change.",
            "Run one adjacent probe that should still pass.",
            "Gate: the original probe must go from fail to pass on disk.",
        ],
    ),
    "cmd-build-fix": _own(
        "Fix a broken build",
        [
            "Capture the failing compiler or test line verbatim.",
            "Change the cited site; do not rewrite neighbors.",
            "Re-run the same command; stop when it exits 0.",
        ],
    ),
    "cmd-grill-me": _own(
        "Adversarial questioning of a claim",
        [
            "Restate the claim as a falsifiable sentence.",
            "Ask for the measurement that would refute it.",
            "Refuse the claim if no measurement is named.",
        ],
    ),
}

# Thin aliases: invoke only. cmd-aside plants a numbered list in description
# (mention) that must not be read as stages.
ALIAS: dict[str, str] = {
    "cmd-loop-status": _alias("Show loop status", "loop-status"),
    "cmd-test-coverage": _alias("Show test coverage", "test-coverage"),
    "cmd-refactor-clean": _alias("Clean a refactor", "refactor-clean"),
    "cmd-brainstorm": _alias("Brainstorm a design", "brainstorm"),
    "cmd-start": _alias("Alias of start-task skill", "start-task"),
    "cmd-learn": _alias("Learn from a session", "learn"),
    "cmd-sessions": _alias("List sessions", "sessions"),
    "cmd-checkpoint": _alias("Write a checkpoint", "checkpoint"),
    "cmd-rollback": _alias("Roll back a checkpoint", "rollback"),
    "cmd-status": _alias("Show workspace status", "status"),
    "cmd-docs": _alias("Look up docs", "docs"),
    "cmd-aside": (
        "---\n"
        'description: "1. Park the thought 2. Return later 3. Never treat this list as stages"\n'
        "skill: aside\n"
        "---\n\n"
        "Use the `aside` skill with $ARGUMENTS.\n"
    ),
}

SKILL_BODIES: dict[str, str] = {
    name: f"---\nname: {name}\n---\n\nSkill `{name}` body. Commands that only invoke this skill add no stages.\n"
    for name in (
        "loop-status",
        "test-coverage",
        "refactor-clean",
        "brainstorm",
        "start-task",
        "learn",
        "sessions",
        "checkpoint",
        "rollback",
        "status",
        "docs",
        "aside",
    )
}

CONTROL_KNOWN_ALIAS = (
    "---\ndescription: Detector-control known alias\nskill: docs\n---\n\n"
    "Use the `docs` skill with $ARGUMENTS.\n"
)
CONTROL_KNOWN_OWN = _own(
    "Detector-control known own-procedure",
    [
        "Read the design document and list invariants.",
        "Check each invariant against the implementation.",
        "Gate: refuse merge if any invariant is untested.",
        "Write the review with cited line numbers.",
    ],
)

IFAMILY_IDS = list(OWN.keys()) + list(ALIAS.keys())


def materialize() -> dict[str, Path]:
    IFAMILY.mkdir(parents=True, exist_ok=True)
    CONTROLS.mkdir(parents=True, exist_ok=True)
    SKILLS.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for cid, text in {**OWN, **ALIAS}.items():
        p = IFAMILY / f"{cid}.md"
        p.write_text(text, encoding="utf-8", newline="\n")
        written[cid] = p
    p_alias = CONTROLS / "known-alias.md"
    p_own = CONTROLS / "known-own-procedure.md"
    p_alias.write_text(CONTROL_KNOWN_ALIAS, encoding="utf-8", newline="\n")
    p_own.write_text(CONTROL_KNOWN_OWN, encoding="utf-8", newline="\n")
    written["known-alias"] = p_alias
    written["known-own-procedure"] = p_own
    for name, text in SKILL_BODIES.items():
        p = SKILLS / f"{name}.md"
        p.write_text(text, encoding="utf-8", newline="\n")
        written[f"skill:{name}"] = p
    if len(OWN) + len(ALIAS) != 31:
        raise RuntimeError(f"I-family size {len(OWN)+len(ALIAS)} != 31")
    missing_sample = [s for s in SAMPLE_IDS if s not in OWN and s not in ALIAS]
    if missing_sample:
        raise RuntimeError(f"sample ids missing: {missing_sample}")
    return written
