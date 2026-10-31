"""Wrappers around security-relevant gates that already exist on this tree.

These are not A7 DESIGN inventions. They are live code paths.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

FIRE = True
PASS = False
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def _load_module(rel: str, name: str):
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stub_pat():
    return _load_module("command-center/p2-wave/_probe_delivered.py", "probe_delivered").STUB_PAT


def stub_text_gate(text: str) -> bool:
    return FIRE if stub_pat().search(text or "") else PASS


def existence_skip_reports_missing(units: list[dict[str, Any]], root: Path) -> bool:
    """True (FIRE) only if a missing output_path is reported as a failure.

    Live `_probe_delivered.py` skips missing files (`if not fp.exists(): continue`).
    That skip is fail-open: absent input never becomes a FAIL row.
    """
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = root / str(p)
        if not fp.exists():
            return PASS
    return PASS


def existence_visible_rows(units: list[dict[str, Any]], root: Path) -> list[str]:
    visible: list[str] = []
    for u in units:
        p = u.get("output_path")
        if not p:
            continue
        fp = root / str(p)
        if fp.exists():
            visible.append(str(u.get("id") or p))
    return visible


def schema_review_gate(doc: Any) -> bool:
    """FIRE if architecture-review schema rejects the document."""
    schema = json.loads(
        (REPO / "command-center/schema/architecture-review.schema.json").read_text(
            encoding="utf-8"
        )
    )
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    return FIRE if errs else PASS


def measure_artifact_gate(path: Path, sentinel: str) -> bool:
    """Artifact half of `_measure_one_delivered.py` (exists/parse/state/sentinel).

    FIRE means the gate refuses the artifact. Absent file fail-closes.
    """
    if not path.is_file() or path.stat().st_size <= 0:
        return FIRE
    try:
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return FIRE
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            return FIRE
        if sentinel and sentinel not in text:
            return FIRE
    return PASS


def a1_loader():
    path = REPO / "command-center/p2-wave/probes/ARC-0009/a1_loader.py"
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    import a1_loader as mod  # type: ignore

    return mod


def write_a1_tree(root: Path, *, extra: bool, duplicate: bool) -> Path:
    """Minimal A1 tree for unlisted-skip and duplicate-id both-states."""
    cap = root / "capabilities" / "skills"
    cap.mkdir(parents=True, exist_ok=True)
    listed = cap / "skill.listed.skill.json"
    listed.write_text(
        json.dumps({"id": "skill.listed", "kind": "skill"}, indent=2) + "\n",
        encoding="utf-8",
    )
    files = ["capabilities/skills/skill.listed.skill.json"]
    if extra:
        extra_p = cap / "skill.extra.skill.json"
        extra_p.write_text(
            json.dumps({"id": "skill.extra", "kind": "skill"}, indent=2) + "\n",
            encoding="utf-8",
        )
    if duplicate:
        dup = cap / "skill.dup.skill.json"
        dup.write_text(
            json.dumps({"id": "skill.listed", "kind": "skill"}, indent=2) + "\n",
            encoding="utf-8",
        )
        files.append("capabilities/skills/skill.dup.skill.json")
    (root / "MANIFEST.json").write_text(
        json.dumps({"files": files}, indent=2) + "\n", encoding="utf-8"
    )
    return root
