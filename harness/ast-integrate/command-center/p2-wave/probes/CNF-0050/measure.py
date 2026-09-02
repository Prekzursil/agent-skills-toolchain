"""Literal rollback-guide measurement.

Zero improvisation: extracted commands run as written, or they are recorded
with a deviation. Missing named surfaces become missing-step rows, not skipped
rows.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from execute import is_wrong_recipe, run_literal
from extract import extract_fenced, extract_prompt, load_text, rollback_section
from paths import (
    CORRECTED_BLOB_RECIPE,
    MANIFEST_REL,
    REPO,
    RUNBOOK_REL,
)

EXPECTED_COVERAGE = (
    {
        "id": "missing-fetch-n1",
        "needles": ("fetch", "release store"),
        "command": "fetch the N-1 artifact from the release store",
        "source": "catalog:REL-0006/question_or_target",
        "detail": (
            "REL-0006 names fetchability of the N-1 artifact as the blocking "
            "precondition; the live rollback guide does not prescribe it"
        ),
    },
    {
        "id": "missing-sha256-pin",
        "needles": ("sha256",),
        "command": (
            "compare the fetched N-1 sha256 to the value recorded in "
            "ROLLBACK-MANIFEST.md"
        ),
        "source": "catalog:REL-0006/question_or_target",
        "detail": (
            "a plan that assumes an artifact nobody can fetch is not a plan; "
            "the pin is missing because the manifest file is missing"
        ),
    },
    {
        "id": "missing-downgrade-canary",
        "needles": ("downgrade", "canary"),
        "command": "downgrade the canary to the N-1 artifact",
        "source": "catalog:REL-0006/question_or_target",
        "detail": "no downgrade step is present in the live rollback surfaces",
    },
    {
        "id": "missing-acceptance-probe",
        "needles": ("acceptance probe", "acceptance-probe"),
        "command": (
            "prove restoration by re-running the N-1 acceptance probe, not by "
            "reading a version string"
        ),
        "source": "catalog:REL-0006/question_or_target",
        "detail": "the live guide does not name an acceptance probe",
    },
    {
        "id": "missing-mttr",
        "needles": ("mttr", "wall-clock"),
        "command": (
            "record wall-clock time from decision to restored behaviour as MTTR"
        ),
        "source": "catalog:REL-0006/question_or_target",
        "detail": "no MTTR measurement step is present in the live guide",
    },
)


def completeness(steps: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if len(steps) < 2:
        problems.append("vacuous:fewer-than-two-steps")
    for step in steps:
        sid = str(step.get("id") or "?")
        has_exit = isinstance(step.get("exit_code"), int)
        has_dev = (
            isinstance(step.get("deviation"), str)
            and len(step["deviation"]) >= 8
        )
        if not has_exit and not has_dev:
            problems.append(f"unrecorded:{sid}")
        if step.get("status") == "unexecuted" and not has_dev:
            problems.append(f"unexecuted:{sid}")
        if step.get("improvised") is True:
            filed = (
                "improvis" in str(step.get("deviation") or "").lower()
                or step.get("classification") == "documentation-defect"
            )
            if not filed:
                problems.append(f"improvisation-unfiled:{sid}")
    return (not problems), problems


def _existence_step(path: Path, rel: str, step_id: str) -> dict[str, Any]:
    proc = subprocess.run(
        ["test", "-f", str(path)],
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    step: dict[str, Any] = {
        "id": step_id,
        "source": rel,
        "line": 1,
        "command": f"test -f {rel}",
        "exit_code": int(proc.returncode),
        "status": "executed",
        "improvised": False,
        "stdout": "",
        "stderr": (proc.stderr or "")[-200:],
        "reviewer_ids": ["A-fenced", "B-prompt"],
    }
    if ok:
        step["classification"] = "ok"
    else:
        step["classification"] = "missing-step"
        step["deviation"] = (
            f"named input {rel} is absent; an operator cannot open the guide"
        )
    return step


def _union_extracted(
    a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    a_cmds = {r["command"]: r for r in a_rows}
    b_cmds = {r["command"]: r for r in b_rows}
    only_a = sorted(set(a_cmds) - set(b_cmds))
    only_b = sorted(set(b_cmds) - set(a_cmds))
    both = sorted(set(a_cmds) & set(b_cmds))
    union: list[dict[str, Any]] = []
    for cmd in sorted(set(a_cmds) | set(b_cmds)):
        src = a_cmds.get(cmd) or b_cmds.get(cmd)
        found_by = []
        if cmd in a_cmds:
            found_by.append("A-fenced")
        if cmd in b_cmds:
            found_by.append("B-prompt")
        union.append(
            {
                "command": cmd,
                "source": src["source"],
                "line": src["line"],
                "found_by": found_by,
                "extractor_disagreement": len(found_by) != 2,
            }
        )
    return union, {
        "only_a": only_a,
        "only_b": only_b,
        "both": both,
        "agree": not only_a and not only_b,
    }


def _file_wrong_recipes(text: str, rel: str) -> list[dict[str, Any]]:
    """Prescriptive git-archive in fenced blocks only (use-vs-mention)."""
    from extract import FENCE, normalize_command

    defects: list[dict[str, Any]] = []
    for match in FENCE.finditer(text):
        body = normalize_command(match.group(1))
        if is_wrong_recipe(body):
            line = text[: match.start()].count("\n") + 1
            defects.append(
                {
                    "id": f"wrong-recipe:{rel}:{line}",
                    "classification": "wrong-recipe",
                    "path": rel,
                    "line": line,
                    "detail": (
                        "fenced command prescribes git archive for blob "
                        f"bytes; corrected recipe: {CORRECTED_BLOB_RECIPE}"
                    ),
                    "corrected_recipe": CORRECTED_BLOB_RECIPE,
                    "command": body,
                }
            )
    return defects


def _coverage_blob(extracted: list[dict[str, Any]], texts: list[str]) -> str:
    parts = [e["command"].lower() for e in extracted]
    parts.extend(t.lower() for t in texts)
    return "\n".join(parts)


def measure_layout(
    *,
    guide_root: Path,
    named: list[str],
    sandbox: Path,
    include_catalog_coverage: bool,
    runbook_requires_section: bool = True,
) -> dict[str, Any]:
    sandbox.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, Any]] = []
    defects: list[dict[str, Any]] = []
    texts_for_coverage: list[str] = []
    extracted_all: list[dict[str, Any]] = []
    reviewer_a_rows: list[dict[str, Any]] = []
    reviewer_b_rows: list[dict[str, Any]] = []
    named_present: dict[str, bool] = {}

    for rel in named:
        path = guide_root / rel
        present = path.is_file()
        named_present[rel] = present
        sid = "exists-" + rel.replace("/", "-").replace(".", "-")
        steps.append(_existence_step(path, rel, sid))
        if not present:
            defects.append(
                {
                    "id": f"missing-file:{rel}",
                    "classification": "missing-step",
                    "path": rel,
                    "line": None,
                    "detail": (
                        f"{rel} is not on disk; every procedure it should "
                        "contain is missing"
                    ),
                }
            )
            continue
        text = load_text(path)
        texts_for_coverage.append(text)
        extract_text = text
        if runbook_requires_section and rel.endswith("RUNBOOK.md"):
            section, start_line = rollback_section(text)
            if section is None:
                defects.append(
                    {
                        "id": f"missing-rollback-section:{rel}",
                        "classification": "missing-step",
                        "path": rel,
                        "line": None,
                        "detail": (
                            f"{rel} has no heading containing 'rollback'; "
                            "two operators would not agree where the guide "
                            "starts"
                        ),
                    }
                )
                steps.append(
                    {
                        "id": f"missing-section-{rel.replace('/', '-')}",
                        "source": rel,
                        "line": 1,
                        "command": "(missing) RUNBOOK.md rollback section heading",
                        "classification": "missing-step",
                        "status": "not-executed-missing",
                        "improvised": False,
                        "deviation": (
                            "no rollback heading; section not invented; "
                            "commands outside a rollback section were not "
                            "executed as if they were the guide"
                        ),
                        "reviewer_ids": ["A-fenced", "B-prompt"],
                    }
                )
                extract_text = ""
            else:
                extract_text = section
                _ = start_line
        a_rows = extract_fenced(extract_text, rel)
        b_rows = extract_prompt(extract_text, rel)
        reviewer_a_rows.extend(a_rows)
        reviewer_b_rows.extend(b_rows)
        union, _cmp = _union_extracted(a_rows, b_rows)
        extracted_all.extend(union)
        defects.extend(_file_wrong_recipes(extract_text, rel))
        for item in union:
            ran = run_literal(item["command"], sandbox)
            step = {
                "id": (
                    f"run:{rel}:{item['line']}:"
                    f"{item['command'][:40].replace(' ', '-')}"
                ),
                "source": f"{rel}:{item['line']}",
                "line": item["line"],
                "command": item["command"],
                "found_by": item["found_by"],
                "extractor_disagreement": item["extractor_disagreement"],
                "improvised": ran["improvised"],
                "status": ran["status"],
                "classification": ran["classification"],
                "stdout": ran.get("stdout", ""),
                "stderr": ran.get("stderr", ""),
                "reviewer_ids": item["found_by"],
            }
            if isinstance(ran.get("exit_code"), int):
                step["exit_code"] = ran["exit_code"]
            if ran.get("deviation"):
                step["deviation"] = ran["deviation"]
            if ran.get("corrected_recipe"):
                step["corrected_recipe"] = ran["corrected_recipe"]
            if item["extractor_disagreement"]:
                extra = (
                    "extractor-disagreement: only "
                    + ",".join(item["found_by"])
                    + " found this command; two operators can diverge"
                )
                step["classification"] = (
                    "ambiguous-step"
                    if step["classification"] == "ok"
                    else step["classification"]
                )
                step["deviation"] = (
                    (step.get("deviation") + "; " if step.get("deviation") else "")
                    + extra
                )
                defects.append(
                    {
                        "id": f"disagree:{rel}:{item['line']}",
                        "classification": "ambiguous-step",
                        "path": rel,
                        "line": item["line"],
                        "detail": extra,
                    }
                )
            if ran["classification"] in {
                "documentation-defect",
                "ambiguous-step",
                "wrong-recipe",
                "blocked-external",
                "missing-step",
            }:
                defects.append(
                    {
                        "id": f"step:{step['id']}",
                        "classification": ran["classification"],
                        "path": rel,
                        "line": item["line"],
                        "detail": ran.get("deviation") or ran["classification"],
                        "corrected_recipe": ran.get("corrected_recipe"),
                    }
                )
            steps.append(step)

    blob = _coverage_blob(extracted_all, texts_for_coverage)
    if include_catalog_coverage:
        for spec in EXPECTED_COVERAGE:
            if all(n.lower() not in blob for n in spec["needles"]):
                steps.append(
                    {
                        "id": spec["id"],
                        "source": spec["source"],
                        "line": None,
                        "command": spec["command"],
                        "classification": "missing-step",
                        "status": "not-executed-missing",
                        "improvised": False,
                        "deviation": spec["detail"] + "; not invented or executed",
                        "reviewer_ids": ["A-fenced", "B-prompt"],
                    }
                )
                defects.append(
                    {
                        "id": spec["id"],
                        "classification": "missing-step",
                        "path": spec["source"],
                        "line": None,
                        "detail": spec["detail"],
                    }
                )

    a_verdict = _reviewer_verdict(reviewer_a_rows, named_present, "A-fenced")
    b_verdict = _reviewer_verdict(reviewer_b_rows, named_present, "B-prompt")
    complete, problems = completeness(steps)
    existence_fail = [
        s
        for s in steps
        if s.get("command", "").startswith("test -f ")
        and s.get("exit_code") != 0
    ]
    bad_classes = {
        "missing-step",
        "ambiguous-step",
        "wrong-recipe",
        "documentation-defect",
    }
    guide_followable = (
        complete
        and not existence_fail
        and not any(s.get("classification") in bad_classes for s in steps)
        and a_verdict["verdict"] == "FOLLOWABLE"
        and b_verdict["verdict"] == "FOLLOWABLE"
        and a_verdict["command_count"] > 0
    )
    return {
        "named_present": named_present,
        "steps": steps,
        "defects": _dedup_defects(defects),
        "reviewers": [a_verdict, b_verdict],
        "reviewer_disagreement": a_verdict["verdict"] != b_verdict["verdict"],
        "completeness_ok": complete,
        "completeness_problems": problems,
        "guide_followable": guide_followable,
        "unexecuted_count": sum(
            1
            for s in steps
            if s.get("status") == "unexecuted"
            or (
                not isinstance(s.get("exit_code"), int)
                and not (
                    isinstance(s.get("deviation"), str)
                    and len(s["deviation"]) >= 8
                )
            )
        ),
        "extracted_count": len(extracted_all),
    }


def _reviewer_verdict(
    rows: list[dict[str, Any]],
    named_present: dict[str, bool],
    reviewer_id: str,
) -> dict[str, Any]:
    missing = [rel for rel, ok in named_present.items() if not ok]
    followable = (not missing) and bool(rows)
    return {
        "reviewer_id": reviewer_id,
        "verdict": "FOLLOWABLE" if followable else "NOT-FOLLOWABLE",
        "independent": True,
        "saw_other_verdict_before_filing": False,
        "command_count": len(rows),
        "commands": [r["command"] for r in rows],
        "missing_named_inputs": missing,
        "notes": (
            "filed before the other reviewer's verdict was visible; "
            "disagreement is recorded, not voted away"
        ),
    }


def _dedup_defects(defects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for d in defects:
        key = d["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def measure_live(sandbox: Path) -> dict[str, Any]:
    report = measure_layout(
        guide_root=REPO,
        named=[MANIFEST_REL, RUNBOOK_REL],
        sandbox=sandbox,
        include_catalog_coverage=True,
        runbook_requires_section=True,
    )
    render = REPO / "tools" / "command-center" / "render.py"
    if render.is_file():
        text = render.read_text(encoding="utf-8")
        listed = "ROLLBACK-MANIFEST.md" in text and "RUNBOOK.md" in text
        renders_rollback = "def render_rollback" in text
        if listed and not renders_rollback:
            line = 47
            for i, raw in enumerate(text.splitlines(), 1):
                if '"ROLLBACK-MANIFEST.md"' in raw or raw.strip() == '"ROLLBACK-MANIFEST.md",':
                    line = i
                    break
            report["defects"].append(
                {
                    "id": "render-skips-rollback-guide",
                    "classification": "documentation-defect",
                    "path": "tools/command-center/render.py",
                    "line": line,
                    "detail": (
                        "CONTRACTED_ARTIFACTS lists ROLLBACK-MANIFEST.md and "
                        "RUNBOOK.md but outputs() only writes STATUS.md and "
                        "OWNER-DECISIONS.md; the documented generator cannot "
                        "produce the rollback guide"
                    ),
                }
            )
    return report


def canonical_steps(steps: list[dict[str, Any]]) -> list[tuple]:
    rows = []
    for s in steps:
        rows.append(
            (
                s.get("id"),
                s.get("source"),
                s.get("command"),
                s.get("classification"),
                s.get("exit_code"),
                bool(s.get("deviation")),
                s.get("status"),
            )
        )
    return rows


def dump(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, default=str)
