"""Lesson writeback with both-states RED/GREEN gate (IMP-0374)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_subject(tree: Path) -> dict[str, Any]:
    script = tree / "subject.py"
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(tree),
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    failed = proc.returncode != 0 or "SUMMARY failed=0" not in out
    verdict = "RED" if failed else "GREEN"
    return {"verdict": verdict, "stdout": out, "returncode": proc.returncode}


def evaluate_both_states(test_file: Path, pre_tree: Path, post_tree: Path) -> dict[str, Any]:
    pre = _run_subject(Path(pre_tree))
    post = _run_subject(Path(post_tree))
    accepted = pre["verdict"] == "RED" and post["verdict"] == "GREEN"
    classification = "protective" if accepted else "non_protective"
    return {
        "pre": pre,
        "post": post,
        "accepted": accepted,
        "classification": classification,
        "test_file": str(test_file),
    }


def repo_target_path(repo_root: Path, lesson: dict[str, Any]) -> Path:
    kind = lesson.get("target_kind") or "skill"
    tid = lesson.get("target_id") or "id-guard"
    if kind == "skill":
        return Path(repo_root) / "skills" / tid / "SKILL.md"
    if kind == "rule":
        return Path(repo_root) / "rules" / f"{tid}.md"
    if kind == "workflow":
        return Path(repo_root) / "workflows" / f"{tid}.json"
    return Path(repo_root) / "selfimprove" / f"{tid}.md"


def verify_repo_not_only_live(repo_root: Path, live_or_lesson: Any, lesson: dict[str, Any] | None = None) -> dict[str, Any]:
    if lesson is None:
        lesson = live_or_lesson  # type: ignore[assignment]
        live_tree = None
    else:
        live_tree = live_or_lesson
    target = repo_target_path(repo_root, lesson)
    marker = f"RETAINED-LESSON:{lesson.get('lesson_id')}"
    in_repo = target.is_file() and marker in target.read_text(encoding="utf-8")
    live_only = False
    if live_tree is not None:
        live_target = repo_target_path(live_tree, lesson)
        live_only = (not in_repo) and live_target.is_file() and marker in live_target.read_text(
            encoding="utf-8"
        )
    ok = in_repo and not live_only
    return {"ok": ok, "in_repo": in_repo, "live_only": live_only, "path": str(target)}


def writeback(
    *,
    repo_root: Path,
    lesson: dict[str, Any],
    pre_tree: Path,
    post_tree: Path,
    live_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    if lesson.get("regression_kind") == "tautology":
        both = {
            "pre": {"verdict": "GREEN", "stdout": "SUMMARY failed=0\n"},
            "post": {"verdict": "GREEN", "stdout": "SUMMARY failed=0\n"},
        }
    else:
        both = evaluate_both_states(post_tree / "subject.py", pre_tree, post_tree)
    pre_v = both["pre"]["verdict"]
    post_v = both["post"]["verdict"]
    tautology = lesson.get("regression_kind") == "tautology" or (pre_v == "GREEN" and post_v == "GREEN")
    accepted = pre_v == "RED" and post_v == "GREEN" and not tautology
    classification = "protective" if accepted else "non_protective"
    retained = repo_root / "selfimprove" / "retained"
    rejected = repo_root / "selfimprove" / "rejected"
    retained.mkdir(parents=True, exist_ok=True)
    rejected.mkdir(parents=True, exist_ok=True)
    rec_path = (retained if accepted else rejected) / f"{lesson['lesson_id']}.json"
    rec_path.write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
    wrote_lesson = accepted
    regression_path = repo_root / "selfimprove" / "regressions" / f"{lesson['lesson_id']}.py"
    if accepted:
        regression_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(post_tree / "subject.py", regression_path)
        skill = repo_target_path(repo_root, lesson)
        skill.parent.mkdir(parents=True, exist_ok=True)
        marker = f"RETAINED-LESSON:{lesson['lesson_id']}"
        if lesson.get("target_kind") == "workflow":
            if skill.is_file():
                try:
                    doc = json.loads(skill.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    doc = {"lessons": []}
            else:
                doc = {"lessons": []}
            rows = list(doc.get("lessons") or [])
            if not any(r.get("lesson_id") == lesson["lesson_id"] for r in rows if isinstance(r, dict)):
                rows.append({"lesson_id": lesson["lesson_id"], "body": lesson.get("body")})
            doc["lessons"] = rows
            marker = f"RETAINED-LESSON:{lesson['lesson_id']}"
            notes = str(doc.get("notes") or "")
            if marker not in notes:
                doc["notes"] = (notes + "\n" + marker).strip()
            skill.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        else:
            prev = skill.read_text(encoding="utf-8") if skill.is_file() else ""
            if marker not in prev:
                skill.write_text(prev + f"\n\n{marker}\n{lesson.get('body')}\n", encoding="utf-8")
    return {
        "accepted": accepted,
        "classification": classification,
        "pre_verdict": pre_v,
        "post_verdict": post_v,
        "pre_stdout": both["pre"]["stdout"],
        "post_stdout": both["post"]["stdout"],
        "wrote_lesson": wrote_lesson,
        "regression_path": str(regression_path),
        "record_path": str(rec_path),
        "repo_verification": verify_repo_not_only_live(repo_root, live_root, lesson)
        if live_root is not None
        else verify_repo_not_only_live(repo_root, lesson),
    }
