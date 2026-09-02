#!/usr/bin/env python3
"""Read-only adapter: metaswarm 9-phase pipeline and gates → WorkflowIR.

Reads published skill markdown (fixtures, or a live plugin tree if present).
Does not import, exec, or vendor metaswarm runtime code.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "corpus"

import stop_grammar as SG  # noqa: E402

USAGE_ROW = re.compile(
    r"^\|\s*(\d+[a-z]?)\.\s+([^|]+)\|([^|]*)\|([^|]*)\|\s*$",
    re.I,
)

STOP = {
    "plan-review-gate": (
        "feasibility_verdict == PASS AND completeness_verdict == PASS "
        "AND scope_alignment_verdict == PASS"
    ),
    "design-review-gate": (
        "pm_verdict == APPROVED AND architect_verdict == APPROVED AND "
        "designer_verdict == APPROVED AND security_verdict == APPROVED AND "
        "cto_verdict == APPROVED"
    ),
    "loop-validate": (
        "tests_exit == 0 AND coverage_thresholds_met == true AND "
        "typecheck_pass == true AND lint_pass == true AND "
        "file_scope_respected == true"
    ),
    "loop-adversarial-review": "adversarial_verdict == PASS",
    "coverage-enforcement": "coverage_thresholds_met == true",
    "pre-pr-knowledge-capture": "self_reflect_complete == true",
    "final-comprehensive-review": (
        "tests_exit == 0 AND coverage_thresholds_met == true AND "
        "cross_unit_integration_ok == true"
    ),
}

LIVE_PLUGIN_GLOBS = (
    Path.home() / ".claude" / "plugins",
    Path.home() / ".claude" / "plugins" / "cache",
    REPO / "tools" / "editor" / "metaswarm",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def translation_defect(source_kind: str, ir_kind: str) -> bool:
    """True when a blocking source gate was downgraded to advisory in IR."""
    return source_kind == "BLOCKING" and ir_kind == "ADVISORY"


def classify_gate_kind(text: str) -> str:
    """Classify a source document's gate as BLOCKING or ADVISORY.

    Anti-pattern tables that name advisory treatment as a defect are
    BLOCKING sources. A document that only recommends ignoring FAIL is
    ADVISORY.
    """
    low = text.lower()
    if "treating fail as advisory" in low:
        return "BLOCKING"
    if "advisory quality gates" in low and "anti-pattern" in low:
        return "BLOCKING"
    if "not advisory" in low:
        return "BLOCKING"
    if "blocking state transition" in low:
        return "BLOCKING"
    if "fail means revise" in low or "fail means retry" in low:
        return "BLOCKING"
    if "cannot skip" in low and "gate" in low:
        return "BLOCKING"
    if "all 3 must" in low or "all three must" in low:
        return "BLOCKING"
    if "all five must" in low or "all 5 must" in low or "all six must" in low:
        return "BLOCKING"
    if "mandatory" in low and "before creating the pr" in low:
        return "BLOCKING"
    if "advisory recommendation" in low or "fail may be ignored" in low:
        return "ADVISORY"
    if "blocking" in low and "gate" in low:
        return "BLOCKING"
    return "UNKNOWN"


def discover_live() -> dict[str, Any]:
    hits: list[str] = []
    for root in LIVE_PLUGIN_GLOBS:
        if not root.exists() or root.is_file():
            continue
        for p in root.rglob("SKILL.md"):
            try:
                body = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if (
                "plan-review-gate" in body
                or "orchestrated-execution" in body
                or "Design Review Gate" in body
            ):
                hits.append(str(p))
    claude = [
        str(p)
        for p in (
            REPO / "CLAUDE.md",
            Path.home() / "CLAUDE.md",
            CORPUS / "CLAUDE.md",
            CORPUS / "templates-CLAUDE.md",
        )
        if p.is_file()
    ]
    registry = [
        str(p)
        for p in (
            REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
            REPO / "command-center" / "sources" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
            HERE.parent
            / "WFA-0019"
            / "fixtures"
            / "corpus"
            / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        )
        if p.is_file()
    ]
    return {
        "live_plugin_skill_hits": hits[:20],
        "live_plugin_present": bool(hits),
        "claude_md_paths": claude,
        "candidate_registry_paths": registry,
        "f_plugin_family_n21": "NOT-CHECKED:authoritative-registry-absent-on-this-tree",
    }


def load_corpus(corpus: Path | None = None) -> dict[str, str]:
    root = corpus or CORPUS
    names = {
        "usage": "USAGE.md",
        "start": "start.SKILL.md",
        "plan_review": "plan-review-gate.SKILL.md",
        "design_review": "design-review-gate.SKILL.md",
        "orchestrated": "orchestrated-execution.SKILL.md",
        "claude": "CLAUDE.md",
        "templates_claude": "templates-CLAUDE.md",
        "readme_9phase": "README-9phase.txt",
    }
    out: dict[str, str] = {}
    missing = []
    for key, name in names.items():
        path = root / name
        if not path.is_file():
            missing.append(name)
            continue
        out[key] = path.read_text(encoding="utf-8")
    if missing:
        raise FileNotFoundError(f"corpus missing: {missing}")
    return out


def parse_usage_phases(usage: str) -> list[dict[str, str]]:
    start = usage.find("## Workflow Phases")
    if start < 0:
        raise ValueError("USAGE.md missing ## Workflow Phases")
    rows: list[dict[str, str]] = []
    for line in usage[start:].splitlines():
        m = USAGE_ROW.match(line)
        if not m:
            continue
        rows.append(
            {
                "n": m.group(1),
                "name": m.group(2).strip(),
                "agents": m.group(3).strip(),
                "output": m.group(4).strip(),
            }
        )
    numbered = [r["n"] for r in rows if r["n"].isdigit()]
    if numbered != [str(i) for i in range(1, 10)]:
        raise ValueError(f"USAGE.md 9-phase table parse failed: {numbered}")
    extras = [r["n"] for r in rows if not r["n"].isdigit()]
    if extras != ["2a", "2b"]:
        raise ValueError(f"USAGE.md expected 2a/2b, got {extras}")
    return rows


def parse_ascii_boxes(block: str) -> list[str]:
    titles: list[str] = []
    in_box = False
    title: str | None = None
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("┌"):
            in_box = True
            title = None
            continue
        if s.startswith("└"):
            if in_box and title:
                titles.append(title)
            in_box = False
            title = None
            continue
        if in_box and title is None and "│" in line:
            inner = line.strip().strip("│").strip()
            if inner:
                title = re.sub(r"\s+", " ", inner)
    return titles


def workflow_overview_section(start_md: str) -> str:
    start = start_md.find("## Workflow Overview")
    if start < 0:
        raise ValueError("start.SKILL.md missing ## Workflow Overview")
    end = start_md.find("### GTG", start)
    if end < 0:
        end = start_md.find("## ", start + 10)
    return start_md[start:end]


def overview_titles(start_md: str) -> list[str]:
    return parse_ascii_boxes(workflow_overview_section(start_md))


def parse_loop_phases(usage_row_output: str) -> list[str]:
    head = usage_row_output.split("loop")[0]
    parts = re.split(r"\s*→\s*", head)
    names = [p.strip(" .") for p in parts if p.strip(" .")]
    if names != ["IMPLEMENT", "VALIDATE", "ADVERSARIAL REVIEW", "COMMIT"]:
        raise ValueError(f"4-phase loop parse failed: {names}")
    return names


def stop_node(expr: str, source_anchor: str) -> dict[str, Any]:
    ok, why = SG.accepts_unchanged(expr)
    if not ok:
        raise ValueError(f"stop expression rejected: {why} expr={expr!r}")
    tree = SG.parse(expr)
    return {
        "expression": expr,
        "grammar": "CNL-0010/A10-stopping-expression",
        "accepted_unchanged": True,
        "ast": tree["ast"],
        "source_anchor": source_anchor,
    }


def _corpus_name(key: str) -> str:
    return {
        "usage": "USAGE.md",
        "start": "start.SKILL.md",
        "plan_review": "plan-review-gate.SKILL.md",
        "design_review": "design-review-gate.SKILL.md",
        "orchestrated": "orchestrated-execution.SKILL.md",
        "claude": "CLAUDE.md",
        "templates_claude": "templates-CLAUDE.md",
        "readme_9phase": "README-9phase.txt",
    }[key]


def _anchor(path: str, needle: str, texts: dict[str, str]) -> str:
    body = texts[path]
    idx = body.find(needle)
    if idx < 0:
        raise ValueError(f"anchor needle missing in {path}: {needle!r}")
    line = body[:idx].count("\n") + 1
    return f"fixtures/corpus/{_corpus_name(path)}:{line}:{needle}"


def gate(
    gid: str,
    name: str,
    texts: dict[str, str],
    source_key: str,
    needle: str,
    stop_key: str,
    after: str,
    before: str,
) -> dict[str, Any]:
    src = texts[source_key]
    kind = classify_gate_kind(src)
    if kind != "BLOCKING":
        raise ValueError(f"{gid} source classified {kind}, expected BLOCKING")
    expr = STOP[stop_key]
    return {
        "id": gid,
        "name": name,
        "kind": "GATE",
        "gate_kind": kind,
        "blocking": True,
        "fail_means": "retry-or-escalate-never-skip",
        "advisory_downgrade": False,
        "after": after,
        "before": before,
        "stop": stop_node(expr, _anchor(source_key, needle, texts)),
        "source_anchor": _anchor(source_key, needle, texts),
        "source_kind_classified": kind,
    }


def stage(
    sid: str,
    name: str,
    ordinal: int,
    usage_n: str | None,
    texts: dict[str, str],
    source_key: str,
    needle: str,
    *,
    blocking: bool = False,
    stop_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": sid,
        "name": name,
        "kind": "STAGE",
        "ordinal": ordinal,
        "usage_phase": usage_n,
        "blocking": blocking,
        "source_anchor": _anchor(source_key, needle, texts),
    }
    if stop_key:
        node["stop"] = stop_node(STOP[stop_key], node["source_anchor"])
        node["gate_kind"] = "BLOCKING" if blocking else "ADVISORY"
    if extra:
        node.update(extra)
    return node


def _walk_nodes(ir: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    nodes.extend(ir.get("stages") or [])
    nodes.extend(ir.get("gates") or [])
    for st in ir.get("stages") or []:
        nodes.extend(st.get("substages") or [])
    return [n for n in nodes if isinstance(n, dict)]


def _assert_all_anchored(ir: dict[str, Any]) -> None:
    for n in _walk_nodes(ir):
        if not n.get("source_anchor"):
            raise ValueError(f"IR node missing source_anchor: {n.get('id')}")
        stop = n.get("stop")
        if isinstance(stop, dict) and not stop.get("source_anchor"):
            raise ValueError(f"stop missing source_anchor on {n.get('id')}")


def _assert_no_advisory_downgrade(ir: dict[str, Any], texts: dict[str, str]) -> None:
    for key in ("plan_review", "design_review", "orchestrated"):
        sk = classify_gate_kind(texts[key])
        if sk != "BLOCKING":
            raise ValueError(f"{key} should classify BLOCKING, got {sk}")
    for n in _walk_nodes(ir):
        if n.get("blocking") is True and n.get("gate_kind") == "ADVISORY":
            raise ValueError(f"advisory downgrade on {n.get('id')}")
        if n.get("id") in {
            "plan-review-gate",
            "design-review-gate",
            "loop-validate",
            "loop-adversarial-review",
            "pre-pr-knowledge-capture",
            "coverage-enforcement",
        }:
            if n.get("gate_kind") != "BLOCKING":
                raise ValueError(f"{n.get('id')} not BLOCKING in IR")


def build_ir(corpus: Path | None = None) -> dict[str, Any]:
    texts = load_corpus(corpus)
    usage_rows = parse_usage_phases(texts["usage"])
    titles = overview_titles(texts["start"])
    enf = texts["claude"]
    enf_start = enf.find("## Workflow Enforcement (MANDATORY)")
    if enf_start < 0:
        raise ValueError("CLAUDE.md missing ## Workflow Enforcement (MANDATORY)")
    enf_end = enf.find("## External Tools", enf_start)
    enf_body = enf[enf_start : enf_end if enf_end > 0 else None]
    pos_design = enf_body.find("Design Review Gate")
    pos_plan = enf_body.find("Plan Review Gate")
    pos_reflect = enf_body.find("`/self-reflect`")
    if not (0 <= pos_design < pos_plan < pos_reflect):
        raise ValueError(
            "CLAUDE.md Workflow Enforcement order is not "
            "design-review then plan-review then self-reflect"
        )

    loop_row = next(r for r in usage_rows if r["n"] == "5")
    loop_names = parse_loop_phases(loop_row["output"])

    plan_gate = gate(
        "plan-review-gate",
        "Plan Review Gate",
        texts,
        "plan_review",
        "ALL three must PASS",
        "plan-review-gate",
        after="planning",
        before="design-review-gate",
    )
    design_gate = gate(
        "design-review-gate",
        "Design Review Gate",
        texts,
        "design_review",
        "All five must approve before proceeding to implementation",
        "design-review-gate",
        after="plan-validation",
        before="work-unit-decomposition",
    )
    if "ALL SIX must approve" not in texts["start"]:
        raise ValueError("start.SKILL.md lost ALL SIX must approve")

    cov = gate(
        "coverage-enforcement",
        "Coverage enforcement",
        texts,
        "orchestrated",
        "Coverage enforcement (BLOCKING",
        "coverage-enforcement",
        after="loop-implement",
        before="loop-adversarial-review",
    )
    knowledge = gate(
        "pre-pr-knowledge-capture",
        "Pre-PR Knowledge Capture",
        texts,
        "orchestrated",
        "Pre-PR Knowledge Capture (MANDATORY)",
        "pre-pr-knowledge-capture",
        after="final-comprehensive-review",
        before="pr-creation",
    )

    validate_gate = {
        "id": "loop-validate",
        "name": "VALIDATE",
        "kind": "GATE",
        "gate_kind": "BLOCKING",
        "blocking": True,
        "fail_means": "retry-or-escalate-never-skip",
        "after": "loop-implement",
        "before": "loop-adversarial-review",
        "stop": stop_node(
            STOP["loop-validate"],
            _anchor("orchestrated", "VALIDATE → REVIEW", texts),
        ),
        "source_anchor": _anchor(
            "orchestrated", "Quality gates are BLOCKING STATE TRANSITIONS", texts
        ),
        "source_kind_classified": classify_gate_kind(texts["orchestrated"]),
    }
    review_gate = {
        "id": "loop-adversarial-review",
        "name": "ADVERSARIAL REVIEW",
        "kind": "GATE",
        "gate_kind": "BLOCKING",
        "blocking": True,
        "fail_means": "retry-or-escalate-never-skip",
        "after": "loop-validate",
        "before": "loop-commit",
        "stop": stop_node(
            STOP["loop-adversarial-review"],
            _anchor("orchestrated", "REVIEW → COMMIT", texts),
        ),
        "source_anchor": _anchor(
            "orchestrated", "ONLY if adversarial review returns PASS", texts
        ),
        "source_kind_classified": "BLOCKING",
    }

    substages = [
        stage(
            "loop-implement",
            "IMPLEMENT",
            51,
            "5",
            texts,
            "orchestrated",
            "Phase 1: IMPLEMENT",
            extra={"loop": "orchestrated-execution"},
        ),
        {
            **validate_gate,
            "ordinal": 52,
            "usage_phase": "5",
            "loop": "orchestrated-execution",
        },
        {
            **review_gate,
            "ordinal": 53,
            "usage_phase": "5",
            "loop": "orchestrated-execution",
        },
        stage(
            "loop-commit",
            "COMMIT",
            54,
            "5",
            texts,
            "orchestrated",
            "Phase 4: COMMIT",
            extra={"loop": "orchestrated-execution"},
        ),
    ]

    stages = [
        stage("research", "Research", 1, "1", texts, "usage", "1. Research"),
        stage("planning", "Planning", 2, "2", texts, "usage", "2. Planning"),
        stage(
            "external-dependency-detection",
            "External Dependency Detection",
            21,
            "2a",
            texts,
            "usage",
            "2a. External Dependency Detection",
        ),
        stage(
            "plan-validation",
            "Plan Validation",
            22,
            "2b",
            texts,
            "usage",
            "2b. Plan Validation",
        ),
        {**design_gate, "ordinal": 3, "usage_phase": "3", "kind": "GATE"},
        stage(
            "work-unit-decomposition",
            "Work Unit Decomposition",
            4,
            "4",
            texts,
            "usage",
            "4. Work Unit Decomposition",
        ),
        {
            "id": "orchestrated-execution",
            "name": "Orchestrated Execution",
            "kind": "LOOP",
            "ordinal": 5,
            "usage_phase": "5",
            "blocking": True,
            "loop_phases": loop_names,
            "substages": substages,
            "source_anchor": _anchor("usage", "5. Orchestrated Execution", texts),
            "convergence": "all-work-units-PASS-before-final-review",
            "retries": {"max": 3, "then": "ESCALATE"},
        },
        stage(
            "final-comprehensive-review",
            "Final Comprehensive Review",
            6,
            "6",
            texts,
            "orchestrated",
            "Final Comprehensive Review",
            blocking=True,
            stop_key="final-comprehensive-review",
        ),
        stage("pr-creation", "PR Creation", 7, "7", texts, "usage", "7. PR Creation"),
        stage("pr-shepherd", "PR Shepherd", 8, "8", texts, "usage", "8. PR Shepherd"),
        stage("closure", "Closure", 9, "9", texts, "usage", "9. Closure"),
    ]

    rendered = [
        {"id": "research", "kind": "STAGE", "blocking": False},
        {"id": "planning", "kind": "STAGE", "blocking": False},
        {"id": "plan-review-gate", "kind": "GATE", "blocking": True},
        {"id": "external-dependency-detection", "kind": "STAGE", "blocking": False},
        {"id": "plan-validation", "kind": "STAGE", "blocking": False},
        {"id": "design-review-gate", "kind": "GATE", "blocking": True},
        {"id": "work-unit-decomposition", "kind": "STAGE", "blocking": False},
        {"id": "orchestrated-execution", "kind": "LOOP", "blocking": True},
        {"id": "loop-implement", "kind": "STAGE", "blocking": False},
        {"id": "loop-validate", "kind": "GATE", "blocking": True},
        {"id": "loop-adversarial-review", "kind": "GATE", "blocking": True},
        {"id": "loop-commit", "kind": "STAGE", "blocking": False},
        {"id": "final-comprehensive-review", "kind": "STAGE", "blocking": True},
        {"id": "pre-pr-knowledge-capture", "kind": "GATE", "blocking": True},
        {"id": "pr-creation", "kind": "STAGE", "blocking": False},
        {"id": "pr-shepherd", "kind": "STAGE", "blocking": False},
        {"id": "closure", "kind": "STAGE", "blocking": False},
    ]

    known_titles = {
        "Research Phase",
        "Planning Phase",
        "Plan Review Gate",
        "External Dependency Detection",
        "Plan Validation (Pre-Flight)",
        "DESIGN REVIEW GATE (PARALLEL)",
        "Work Unit Decomposition",
        "ORCHESTRATED EXECUTION LOOP (per work unit)",
        "Final Comprehensive Review",
        "PR Creation (Auto-Shepherd)",
        "PR Shepherd (Automatic)",
        "Close Epic & Extract Learnings",
    }
    extras = [t for t in titles if t not in known_titles]

    ir = {
        "ir_kind": "WorkflowIR",
        "id": "metaswarm-9-phase-pipeline",
        "execution_semantics": None,
        "runtime_import": False,
        "governance_order_source": _anchor(
            "claude", "## Workflow Enforcement (MANDATORY)", texts
        ),
        "usage_9phase_source": _anchor("usage", "## Workflow Phases", texts),
        "overview_titles": titles,
        "governance_mandatory_gates": [
            {
                "id": "design-review-gate",
                "trigger": "after-brainstorming",
                "blocking": True,
                "source_anchor": _anchor("claude", "### After Brainstorming", texts),
            },
            {
                "id": "plan-review-gate",
                "trigger": "after-plan-created",
                "blocking": True,
                "source_anchor": _anchor("claude", "### After Any Plan Is Created", texts),
            },
            {
                "id": "coverage-enforcement",
                "trigger": "validate-and-before-pr",
                "blocking": True,
                "source_anchor": _anchor(
                    "claude", "BLOCKING gate before PR creation", texts
                ),
            },
            {
                "id": "pre-pr-knowledge-capture",
                "trigger": "before-finishing-branch",
                "blocking": True,
                "source_anchor": _anchor(
                    "claude", "### Before Finishing a Development Branch", texts
                ),
            },
        ],
        "rendered_sequence": rendered,
        "stages": stages,
        "gates": [plan_gate, design_gate, cov, validate_gate, review_gate, knowledge],
        "lossy_field_ledger": [
            {
                "construct": "start.SKILL.md Issue Orchestrator / Human Approval & Merge / Release Engineer boxes",
                "why": "Present in the start-skill overview but not in the USAGE.md 9-phase table; recorded rather than silently dropped or promoted into the 9-phase floor.",
                "source_anchor": _anchor("start", "Issue Orchestrator", texts),
                "action": "omit-from-translated-stages",
                "observed_titles": extras,
            },
            {
                "construct": "design-review reviewer cardinality 5 vs 6",
                "why": "CLAUDE.md Workflow Enforcement and design-review-gate/SKILL.md require five agents (PM, Architect, Designer, Security, CTO). start.SKILL.md overview and USAGE.md phase 3 name six (adds UX Reviewer). Governance stop expression uses five; the sixth reviewer is recorded here, not silently added.",
                "source_anchor": _anchor(
                    "claude", "all 5 review agents", texts
                ),
                "action": "stop-expression-uses-five; sixth-reviewer-cited",
                "six_agent_anchor": _anchor("start", "ALL SIX must approve", texts),
            },
            {
                "construct": "linear start-skill overview puts Plan Review before Design Review",
                "why": "start.SKILL.md Workflow Overview boxes order Plan Review Gate then Design Review Gate. CLAUDE.md Workflow Enforcement (the project-governance intercepts) fires Design Review after brainstorming and Plan Review after a plan exists — design-review then plan-review on the /start-task route. IR governance_mandatory_gates follows CLAUDE.md; rendered_sequence keeps the linear USAGE lifecycle with the plan-review intercept visible.",
                "source_anchor": _anchor(
                    "claude", "/start-task` → complexity assessment", texts
                ),
                "action": "split-governance-order-from-linear-lifecycle",
            },
            {
                "construct": "README 9-phase omits Plan Review Gate as a numbered phase",
                "why": "README lists Research → Plan → Design Review Gate → ...; plan review is a mandatory intercept in start.SKILL.md sitting between planning and design review. IR preserves the intercept rather than collapsing it.",
                "source_anchor": _anchor(
                    "readme_9phase", "A structured 9-phase workflow", texts
                ),
                "action": "insert-blocking-intercept",
            },
            {
                "construct": "USAGE.md Closure vs orchestrated-execution §8.5 pre-PR capture",
                "why": "USAGE phase 9 is post-pipeline knowledge curation; §8.5 requires /self-reflect BEFORE PR creation. Both are represented: blocking gate before pr-creation, and Closure as stage 9.",
                "source_anchor": _anchor(
                    "orchestrated", "BEFORE creating the PR", texts
                ),
                "action": "split-into-gate-plus-stage",
            },
        ],
    }
    _assert_all_anchored(ir)
    _assert_no_advisory_downgrade(ir, texts)
    return ir


def corpus_files(corpus: Path | None = None) -> list[dict[str, Any]]:
    root = corpus or CORPUS
    rows = []
    for p in sorted(root.iterdir()):
        if p.is_file():
            raw = p.read_bytes()
            rows.append(
                {
                    "path": str(p.relative_to(REPO)).replace("\\", "/"),
                    "bytes": len(raw.replace(b"\r\n", b"\n")),
                    "sha256": sha256_bytes(raw),
                }
            )
    return rows


def runtime_import_audit() -> dict[str, Any]:
    forbidden_py = re.compile(r"^\s*(?:import|from)\s+metaswarm\b", re.MULTILINE)
    hits: list[str] = []
    runtime_files: list[str] = []
    for p in HERE.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(REPO)).replace("\\", "/")
        if p.suffix.lower() in {".ts", ".js", ".mjs", ".cjs"}:
            runtime_files.append(rel)
        if p.suffix == ".py":
            text = p.read_text(encoding="utf-8", errors="replace")
            if forbidden_py.search(text):
                hits.append(rel)
    return {
        "metaswarm_python_imports": hits,
        "vendored_js_ts": runtime_files,
        "clean": not hits and not runtime_files,
    }


if __name__ == "__main__":
    ir = build_ir()
    print(json.dumps({"stages": len(ir["stages"]), "gates": len(ir["gates"])}))
    print("SUCCESS:WFA-0046-adapter")
