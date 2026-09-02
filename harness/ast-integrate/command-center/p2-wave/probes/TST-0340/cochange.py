#!/usr/bin/env python3
"""Snapshot/source co-change check (TST-0340).

A golden regenerated in the same change as the source it covers has
stopped being a test and become a transcript. For every commit or PR:

  1. take the set of changed paths
  2. intersect changed snapshot/golden files with the changed source
     files they cover (coverage map, else conservative name inference)
  3. require an explicit, reviewed justification when that intersection
     is non-empty

Empty or boilerplate justification fields are UNJUSTIFIED; the pair
stays FLAGGED. Changing a snapshot together with an unrelated source
does not flag.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0340"
SENTINEL = "SUCCESS:TST-0340"
OUT_REL = "command-center/receipts/TST-0340.json"
MAP_REL = "command-center/p2-wave/probes/TST-0340/fixtures/coverage-map.json"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "htmlcov",
        ".tox",
        ".eggs",
        ".nox",
        "site-packages",
        ".cursor",
    }
)
SNAPSHOT_DIR_NAMES = frozenset(
    {"__snapshots__", "__snapshot__", "snapshots", "golden", "goldens"}
)
SNAPSHOT_SUFFIXES = (
    ".snap",
    ".snap.json",
    ".snapshot",
    ".snapshot.json",
    ".golden",
    ".golden.json",
    ".gld",
)
NAME_HINT_RE = re.compile(r"(^|[._-])(golden|snapshot)([._-]|$)", re.I)
NAME_HINT_EXTS = (".txt", ".json", ".out", ".bin", ".yml", ".yaml")
SOURCE_EXTS = (".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".c", ".cc", ".cpp")

MIN_EXPLICIT = 40
BOILERPLATE_EXACT = frozenset(
    {
        "update snapshots",
        "update snapshot",
        "updated snapshots",
        "updated snapshot",
        "regenerate snapshots",
        "regenerate snapshot",
        "regen snapshots",
        "regen snapshot",
        "refresh snapshots",
        "refresh snapshot",
        "sync snapshots",
        "sync snapshot",
        "make tests pass",
        "fix tests",
        "fix the tests",
        "wip",
        "ok",
        "lgtm",
        "n/a",
        "na",
        "none",
        "see pr",
        "as discussed",
        "blanket regen",
        "update goldens",
        "update golden",
        "regenerate goldens",
        "regenerate golden",
        "refresh goldens",
        "refresh golden",
        "snapshots updated",
        "goldens updated",
    }
)
BOILERPLATE_RE = re.compile(
    r"^(updated?|regenerat(?:e|ed)|refresh(?:ed)?|sync(?:ed)?|regen)\s+"
    r"(the\s+)?(snapshots?|goldens?|fixtures?)"
    r"(\s+to\s+match(\s+the)?(\s+new|\s+updated)?\s+output)?\.?$",
    re.I,
)
UNREVIEWED_NAMES = frozenset(
    {"", "n/a", "na", "none", "bot", "ci", "unknown", "n/a.", "-"}
)


def norm_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def is_snapshot_path(rel: str) -> bool:
    p = norm_path(rel)
    parts = p.split("/")
    name = parts[-1]
    lower = name.lower()
    if any(lower.endswith(suf) for suf in SNAPSHOT_SUFFIXES):
        return True
    if any(part in SNAPSHOT_DIR_NAMES for part in parts[:-1]):
        return True
    if NAME_HINT_RE.search(name) and lower.endswith(NAME_HINT_EXTS):
        return True
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def coverage_index(doc: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if isinstance(doc.get("map"), dict):
        for snap, covers in doc["map"].items():
            out[norm_path(snap)] = [norm_path(c) for c in (covers or [])]
        return out
    for row in doc.get("snapshots") or []:
        if not isinstance(row, dict):
            continue
        snap = norm_path(str(row.get("snapshot") or ""))
        if not snap:
            continue
        covers = row.get("covers") or row.get("sources") or []
        out[snap] = [norm_path(c) for c in covers if c]
    return out


def load_coverage(path: Path | None = None) -> dict[str, list[str]]:
    target = path or (REPO / MAP_REL)
    if not target.is_file():
        return {}
    doc = load_json(target)
    if not isinstance(doc, dict):
        return {}
    return coverage_index(doc)


def infer_covers(snap: str) -> list[str]:
    """Conservative name-based covers when the map omits a snapshot."""
    p = norm_path(snap)
    parts = p.split("/")
    name = parts[-1]
    stem = name
    for suf in sorted(SNAPSHOT_SUFFIXES, key=len, reverse=True):
        if stem.lower().endswith(suf):
            stem = stem[: -len(suf)]
            break
    else:
        if "." in stem:
            stem = stem.rsplit(".", 1)[0]
    for extra in (".test", ".spec"):
        if stem.endswith(extra):
            stem = stem[: -len(extra)]
    parent_parts = parts[:-1]
    if parent_parts and parent_parts[-1] in SNAPSHOT_DIR_NAMES:
        parent_parts = parent_parts[:-1]
    parent = "/".join(parent_parts)
    candidates: list[str] = []
    for ext in SOURCE_EXTS:
        if parent:
            candidates.append(f"{parent}/{stem}{ext}")
            candidates.append(f"{parent}/test_{stem}{ext}")
        candidates.append(f"src/{stem}{ext}")
        candidates.append(f"{stem}{ext}")
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def covers_for(snap: str, index: dict[str, list[str]]) -> list[str]:
    key = norm_path(snap)
    if key in index:
        return list(index[key])
    return infer_covers(key)


def classify_justification(text: str, reviewed_by: str) -> tuple[str, str | None]:
    body = (text or "").strip()
    reviewer = (reviewed_by or "").strip()
    if not body:
        return "UNJUSTIFIED", "empty"
    compact = re.sub(r"\s+", " ", body).lower().rstrip(".,!;:")
    if compact in BOILERPLATE_EXACT or BOILERPLATE_RE.match(compact):
        return "UNJUSTIFIED", "boilerplate"
    if len(body) < MIN_EXPLICIT:
        return "UNJUSTIFIED", "too-short"
    rev_key = re.sub(r"\s+", " ", reviewer).lower().rstrip(".,")
    if rev_key in UNREVIEWED_NAMES or len(reviewer) < 8:
        return "UNJUSTIFIED", "unreviewed"
    return "JUSTIFIED", None


def load_justifications(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.is_file():
        return []
    doc = load_json(path)
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        rows = doc.get("pairs") or doc.get("justifications") or []
    else:
        return []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "snapshot": norm_path(str(row.get("snapshot") or "")),
                "source": norm_path(str(row.get("source") or row.get("covers") or "")),
                "justification": str(row.get("justification") or row.get("text") or ""),
                "reviewed_by": str(
                    row.get("reviewed_by")
                    or row.get("reviewed_by_id")
                    or row.get("reviewer")
                    or ""
                ),
            }
        )
    return out


def lookup_justification(
    rows: Iterable[dict[str, str]], snapshot: str, source: str
) -> dict[str, str]:
    snap = norm_path(snapshot)
    src = norm_path(source)
    for row in rows:
        if row.get("snapshot") == snap and row.get("source") == src:
            return row
    return {
        "snapshot": snap,
        "source": src,
        "justification": "",
        "reviewed_by": "",
    }


def mutant_empty_intersection(
    changed: Iterable[str], index: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Always-green mutant: never reports a co-change pair."""
    del changed, index
    return []


def intersection_pairs(
    changed: Iterable[str],
    index: dict[str, list[str]],
    justifications: Iterable[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    changed_n = {norm_path(p) for p in changed if p}
    just_rows = list(justifications or [])
    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    snapshots = [p for p in sorted(changed_n) if is_snapshot_path(p) or p in index]
    for snap in snapshots:
        for src in covers_for(snap, index):
            if src not in changed_n:
                continue
            key = (snap, src)
            if key in seen:
                continue
            seen.add(key)
            just = lookup_justification(just_rows, snap, src)
            klass, reason = classify_justification(
                just.get("justification") or "", just.get("reviewed_by") or ""
            )
            verdict = "PASS" if klass == "JUSTIFIED" else "FLAGGED"
            pairs.append(
                {
                    "snapshot": snap,
                    "source": src,
                    "justification": just.get("justification") or "",
                    "reviewed_by": just.get("reviewed_by") or "",
                    "justification_class": klass,
                    "unjustified_reason": reason,
                    "verdict": verdict,
                }
            )
    return pairs


def evaluate_change(
    changed: Iterable[str],
    index: dict[str, list[str]],
    justifications: Iterable[dict[str, str]] | None = None,
) -> dict[str, Any]:
    changed_n = sorted({norm_path(p) for p in changed if p})
    snaps = [p for p in changed_n if is_snapshot_path(p) or p in index]
    pairs = intersection_pairs(changed_n, index, justifications)
    flagged = [p for p in pairs if p["verdict"] == "FLAGGED"]
    justified = [p for p in pairs if p["verdict"] == "PASS"]
    named = [f"{p['snapshot']} ++ {p['source']}" for p in pairs]
    overall = "FLAGGED" if flagged else "PASS"
    return {
        "changed_files": changed_n,
        "changed_snapshots": snaps,
        "intersection": pairs,
        "intersection_size": len(pairs),
        "named_pairs": named,
        "flagged_count": len(flagged),
        "justified_count": len(justified),
        "verdict": overall,
    }


def discover_snapshots(root: Path) -> list[str]:
    found: list[str] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for name in filenames:
            full = base / name
            try:
                rel = full.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            if is_snapshot_path(rel):
                found.append(rel)
    return sorted(found)


def git_changed(repo: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "available": False,
        "inside_work_tree": False,
        "diff_name_only": [],
        "cached_name_only": [],
        "note": "not a git worktree",
    }
    if not (repo / ".git").exists():
        return info
    try:
        inside = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        info["note"] = f"git-unavailable:{type(exc).__name__}"
        return info
    if inside.returncode != 0 or (inside.stdout or "").strip() != "true":
        info["note"] = "git-rev-parse-not-inside"
        return info
    info["available"] = True
    info["inside_work_tree"] = True
    info["note"] = "git diff --name-only (unstaged and cached); untracked omitted"
    for key, args in (
        ("diff_name_only", ["git", "-C", str(repo), "diff", "--name-only"]),
        (
            "cached_name_only",
            ["git", "-C", str(repo), "diff", "--name-only", "--cached"],
        ),
    ):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            info[key] = []
            continue
        info[key] = [
            norm_path(line) for line in (proc.stdout or "").splitlines() if line.strip()
        ]
    return info


def fixture_paths() -> dict[str, str]:
    estate = "command-center/p2-wave/probes/TST-0340/fixtures/estate"
    base = "command-center/p2-wave/probes/TST-0340/fixtures"
    return {
        "widget_src": f"{estate}/src/widget.py",
        "widget_snap": f"{estate}/tests/__snapshots__/widget.snap",
        "gadget_src": f"{estate}/src/gadget.py",
        "gadget_snap": f"{estate}/tests/__snapshots__/gadget.snap",
        "coverage": MAP_REL,
        "planted": f"{base}/changes/planted.json",
        "unrelated": f"{base}/changes/unrelated.json",
        "legitimate": f"{base}/changes/legitimate.json",
        "just_none": f"{base}/justifications/none.json",
        "just_empty": f"{base}/justifications/empty.json",
        "just_boilerplate": f"{base}/justifications/boilerplate.json",
        "just_reviewed": f"{base}/justifications/reviewed.json",
    }


def _as_changed(doc: Any) -> list[str]:
    if isinstance(doc, list):
        return [norm_path(x) for x in doc]
    if isinstance(doc, dict):
        rows = doc.get("changed") or doc.get("files") or doc.get("paths") or []
        return [norm_path(x) for x in rows]
    return []


def run_named_scenarios(index: dict[str, list[str]] | None = None) -> dict[str, Any]:
    paths = fixture_paths()
    cov = index if index is not None else load_coverage(REPO / paths["coverage"])
    planted_changed = _as_changed(load_json(REPO / paths["planted"]))
    unrelated_changed = _as_changed(load_json(REPO / paths["unrelated"]))
    legitimate_changed = _as_changed(load_json(REPO / paths["legitimate"]))
    scenarios = {
        "planted": evaluate_change(
            planted_changed, cov, load_justifications(REPO / paths["just_none"])
        ),
        "unrelated": evaluate_change(
            unrelated_changed, cov, load_justifications(REPO / paths["just_none"])
        ),
        "legitimate": evaluate_change(
            legitimate_changed,
            cov,
            load_justifications(REPO / paths["just_reviewed"]),
        ),
        "empty_justification": evaluate_change(
            planted_changed, cov, load_justifications(REPO / paths["just_empty"])
        ),
        "boilerplate": evaluate_change(
            planted_changed,
            cov,
            load_justifications(REPO / paths["just_boilerplate"]),
        ),
    }
    widget = paths["widget_src"]
    widget_snap = paths["widget_snap"]
    planted_ok = (
        scenarios["planted"]["verdict"] == "FLAGGED"
        and scenarios["planted"]["intersection_size"] == 1
        and scenarios["planted"]["named_pairs"] == [f"{widget_snap} ++ {widget}"]
        and scenarios["planted"]["intersection"][0]["justification_class"]
        == "UNJUSTIFIED"
    )
    unrelated_ok = (
        scenarios["unrelated"]["verdict"] == "PASS"
        and scenarios["unrelated"]["intersection_size"] == 0
    )
    legitimate_ok = (
        scenarios["legitimate"]["verdict"] == "PASS"
        and scenarios["legitimate"]["intersection_size"] == 1
        and scenarios["legitimate"]["intersection"][0]["justification_class"]
        == "JUSTIFIED"
        and bool((scenarios["legitimate"]["intersection"][0]["justification"] or "").strip())
    )
    empty_ok = (
        scenarios["empty_justification"]["verdict"] == "FLAGGED"
        and scenarios["empty_justification"]["intersection"][0]["unjustified_reason"]
        == "empty"
    )
    boiler_ok = (
        scenarios["boilerplate"]["verdict"] == "FLAGGED"
        and scenarios["boilerplate"]["intersection"][0]["unjustified_reason"]
        == "boilerplate"
    )
    mutant_pairs = mutant_empty_intersection(planted_changed, cov)
    mutant_misses_planted = len(mutant_pairs) == 0 and planted_ok
    tests = [
        {
            "id": "planted-source-and-own-snapshot",
            "name": (
                "Planted case: change a source and regenerate its snapshot "
                "in one commit -> FLAGGED"
            ),
            "result": "PASS" if planted_ok else "FAIL",
        },
        {
            "id": "legitimate-reviewed-justification",
            "name": (
                "Legitimate case: a snapshot updated for an intentional, "
                "documented behaviour change passes with its justification recorded"
            ),
            "result": "PASS" if legitimate_ok else "FAIL",
        },
        {
            "id": "unrelated-snapshot-and-source",
            "name": (
                "Unrelated-change control: changing a snapshot and an "
                "unrelated source must not flag"
            ),
            "result": "PASS" if unrelated_ok else "FAIL",
        },
        {
            "id": "empty-justification-unjustified",
            "name": "Empty justification field is reported as unjustified",
            "result": "PASS" if empty_ok else "FAIL",
        },
        {
            "id": "boilerplate-justification-unjustified",
            "name": "Boilerplate justification field is reported as unjustified",
            "result": "PASS" if boiler_ok else "FAIL",
        },
        {
            "id": "always-green-mutant-misses-planted",
            "name": (
                "Always-empty intersection mutant misses the planted pair "
                "(detector is not a tautology)"
            ),
            "result": "PASS" if mutant_misses_planted else "FAIL",
        },
    ]
    return {
        "scenarios": scenarios,
        "tests": tests,
        "all_pass": all(t["result"] == "PASS" for t in tests),
        "mutant_empty_intersection_size": len(mutant_pairs),
        "paths": paths,
        "coverage_size": len(cov),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TST-0340 snapshot/source co-change check")
    ap.add_argument("--coverage", type=Path, default=None)
    ap.add_argument(
        "--changed",
        type=Path,
        default=None,
        help="JSON list or {changed:[...]} of repo-relative paths",
    )
    ap.add_argument("--justifications", type=Path, default=None)
    ap.add_argument(
        "--scenarios",
        action="store_true",
        help="Run the planted/unrelated/legitimate fixture scenarios",
    )
    args = ap.parse_args(argv)
    if args.scenarios or args.changed is None:
        bundle = run_named_scenarios()
        print(json.dumps({"unit": UNIT, **bundle}, indent=2, sort_keys=True))
        return 0 if bundle["all_pass"] else 1
    cov_path = args.coverage or (REPO / MAP_REL)
    cov = load_coverage(cov_path)
    changed = _as_changed(load_json(args.changed))
    just = load_justifications(args.justifications)
    report = evaluate_change(changed, cov, just)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["verdict"] == "FLAGGED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
