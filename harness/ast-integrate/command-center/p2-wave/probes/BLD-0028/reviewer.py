"""Independent re-derivation of the uncontrolled-zero count.

Traversal is a flatten-to-(path, value) walk, not harvest.py's recursive
visitor. Control evidence is scored from flattened key names. Counts must
agree with the producer; a split is reported, never voted away.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

ZERO_ARRAY_KEYS = frozenset({"findings", "violations", "issues", "defects"})
ZERO_COUNT_KEYS = frozenset(
    {
        "finding_count",
        "findings_count",
        "violation_count",
        "issue_count",
        "defect_count",
        "n_findings",
    }
)
RESULT_KEYS = frozenset(
    {
        "result",
        "verdict",
        "status",
        "classification",
        "answer",
        "outcome",
        "conclusion",
        "finding",
    }
)
ZERO_STRINGS = frozenset(
    {
        "no findings",
        "no-findings",
        "not found",
        "not-found",
        "no issues",
        "no-issues",
        "clean",
        "empty",
        "none",
        "0 findings",
        "zero findings",
    }
)
SKIP_KEYS = frozenset(
    {
        "example",
        "examples",
        "quote",
        "quoted",
        "mention",
        "question",
        "question_or_target",
        "tests_required",
        "description",
        "notes",
        "raw_output",
        "schema",
        "prompt",
    }
)
UNIT_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
QUOTED_RE = re.compile(
    r"""['\"][^'\"]*(no findings|not found|no issues|clean)[^'\"]*['\"]""",
    re.I,
)


def flatten(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for k, v in node.items():
            key = f"{prefix}/{k}" if prefix else str(k)
            rows.append((key, v))
            rows.extend(flatten(v, key))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            key = f"{prefix}/{i}" if prefix else str(i)
            rows.extend(flatten(item, key))
    return rows


def _leaf_name(path: str) -> str:
    return path.rsplit("/", 1)[-1].lower()


def _skipped(path: str) -> bool:
    parts = {p.lower() for p in path.split("/")}
    return bool(parts & SKIP_KEYS)


def empty_not_pass(pairs: list[tuple[str, Any]]) -> bool:
    for path, val in pairs:
        leaf = _leaf_name(path)
        if leaf in {
            "empty_live_is_not_a_pass",
            "empty_set_is_not_pass",
            "empty_is_not_a_pass",
            "empty_set_is_not_a_pass",
            "empty_corpus_is_not_green",
        } and val is True:
            return True
        if leaf == "empty_set_read_as_pass" and val is False:
            return True
    return False


def both_states(pairs: list[tuple[str, Any]]) -> bool:
    fired = False
    silent = False
    for path, val in pairs:
        leaf = _leaf_name(path)
        blob = path.lower()
        if leaf == "fired_on_bad" and val is True:
            fired = True
        if leaf == "silent_on_good" and val is True:
            silent = True
        if "known" in blob and "present" in blob and val is True:
            fired = True
        if "known" in blob and "broken" in blob and val is True:
            fired = True
        if leaf in {"fired", "fired_before_absence_reported"} and val is True:
            if "known" in blob or "present" in blob or "control" in blob:
                fired = True
    return fired and silent


def producer_from(doc: Any, path: Path) -> str:
    if isinstance(doc, dict):
        for key in ("unit_id", "id", "unit"):
            val = doc.get(key)
            if isinstance(val, str) and UNIT_ID_RE.match(val.strip()):
                return val.strip()
    if UNIT_ID_RE.match(path.stem):
        return path.stem
    return path.stem


def grade_json(path: Path) -> list[dict]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(doc, (dict, list)):
        return []
    pairs = flatten(doc)
    skip_empty = empty_not_pass(pairs)
    controlled = both_states(pairs)
    producer = producer_from(doc, path)
    found: list[dict] = []
    seen: set[str] = set()
    for pth, val in pairs:
        if _skipped(pth):
            continue
        leaf = _leaf_name(pth)
        claim = None
        if (
            leaf in ZERO_ARRAY_KEYS
            and isinstance(val, list)
            and len(val) == 0
            and not skip_empty
        ):
            claim = f"{leaf}=[]"
        elif leaf == "clean" and val is True:
            claim = "clean=true"
        elif leaf in ZERO_COUNT_KEYS and val == 0:
            claim = f"{leaf}=0"
        elif (
            leaf in RESULT_KEYS
            and isinstance(val, str)
            and val.strip().lower() in ZERO_STRINGS
        ):
            claim = f"{leaf}={val.strip()[:80]}"
        if not claim:
            continue
        ident = f"{producer}:{pth}"
        if ident in seen:
            continue
        seen.add(ident)
        found.append(
            {
                "id": ident,
                "producer": producer,
                "verdict": "controlled" if controlled else "uncontrolled",
                "claim": claim,
                "source": path.as_posix(),
            }
        )
    return found


def grade_paths(paths: Iterable[Path]) -> dict:
    inventory: list[dict] = []
    scanned = 0
    for path in paths:
        if not path.is_file():
            continue
        scanned += 1
        if path.suffix.lower() == ".json":
            inventory.extend(grade_json(path))
        elif path.suffix.lower() in {".md", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            stripped = QUOTED_RE.sub(" ", text)
            if not re.search(
                r"\b(result|verdict|finding|status|outcome)\s*[:=].*\b(no findings|not found|no issues)\b",
                stripped,
                re.I,
            ):
                continue
            inventory.append(
                {
                    "id": f"{path.stem}:md",
                    "producer": path.stem,
                    "verdict": "uncontrolled",
                    "claim": "markdown-result-zero",
                    "source": path.as_posix(),
                }
            )
    uncontrolled = [r for r in inventory if r["verdict"] == "uncontrolled"]
    controlled = [r for r in inventory if r["verdict"] == "controlled"]
    return {
        "reviewer_id": "BLD-0028-independent-flatten-recount",
        "independent": True,
        "scanned": scanned,
        "zeros_harvested": len(inventory),
        "controlled_count": len(controlled),
        "uncontrolled_count": len(uncontrolled),
        "uncontrolled_ids": sorted(r["id"] for r in uncontrolled),
        "controlled_ids": sorted(r["id"] for r in controlled),
        "inventory": inventory,
    }


grade_paths = grade_paths


def agree(producer: dict, review: dict) -> dict:
    p_u = int(producer.get("uncontrolled_count") or 0)
    r_u = int(review.get("uncontrolled_count") or 0)
    p_c = int(producer.get("controlled_count") or 0)
    r_c = int(review.get("controlled_count") or 0)
    ok = p_u == r_u and p_c == r_c
    return {
        "agree": ok,
        "producer_uncontrolled": p_u,
        "reviewer_uncontrolled": r_u,
        "producer_controlled": p_c,
        "reviewer_controlled": r_c,
        "verdict": "PASS" if ok else "FAIL",
    }
