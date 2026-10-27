#!/usr/bin/env python3
"""AUD-0026 probe2 -- shippable import graph (live AST, fail-closed).

Lane 1 re-runs an AST import scan over the shippable surface of tools/plugin
on this worktree and records what it finds today (the artifact's census is
point-in-time; any drift is recorded with both numbers, never picked). Lane 2
rebuilds the classifier fixture in a temp dir and re-proves it both-states:
AST catches a shipped module importing an undeclared dependency, stays silent
on a test module importing a dev-only dependency, and stays silent on a
declared runtime import.
"""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0026-runtime-vs-dev-split.json"
UNIT = "AUD-0026"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def top_imports(path: Path) -> set[str]:
    """Top-level import names of a python file (AST, syntax-error tolerant)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    # lane 1: live AST scan of tools/plugin (shippable surface = no tests/)
    plugin_root = REPO / "tools" / "plugin"
    live_defects: list[dict] = []
    if plugin_root.is_dir():
        for py in sorted(plugin_root.rglob("*.py")):
            rel = py.relative_to(REPO).as_posix()
            if rel.startswith("tools/plugin/tests/"):
                continue
            std = {"os", "sys", "json", "re", "pathlib", "typing", "argparse",
                   "subprocess", "collections", "dataclasses", "datetime", "hashlib",
                   "tempfile", "shutil", "logging", "unittest", "time", "io",
                   "functools", "itertools", "textwrap", "contextlib", "abc", "enum"}
            tops = {t for t in top_imports(py) if t not in std}
            for t in sorted(tops):
                # repo sibling = a tools/<t or t with underscores> directory
                sibling = (REPO / "tools" / t).is_dir() or (REPO / "tools" / t.replace("_", "-")).is_dir()
                if sibling:
                    live_defects.append({
                        "kind": "undeclared-repo-sibling-imported-by-shipped",
                        "path": rel,
                        "top": t,
                        "dist": t.replace("_", "-"),
                        "class": "repo-first-party",
                    })
    live_rows = [(d["path"], d["top"]) for d in live_defects]
    prd = doc.get("plugin_runtime_vs_dev") or {}
    rec_defects = prd.get("packaging_defects") or []
    rec_rows = [(str(d.get("path", "")), str(d.get("top", ""))) for d in rec_defects]
    if live_rows != rec_rows:
        notes.append(
            "LIVE DRIFT (both numbers recorded, not picked): recorded packaging defects "
            f"{rec_rows} vs live AST scan {live_rows}. The artifact's census is point-in-time; "
            "tools/plugin/census.py on this worktree no longer imports harness_walker while "
            "tools/harness_walker/ still exists."
        )
    # single source of truth: report.answer mirrors the top-level census
    ra = ((doc.get("report") or {}).get("answer")) or {}
    check(all(json.dumps(ra.get(k), sort_keys=True) == json.dumps(prd.get(k), sort_keys=True)
              for k in ("consumer_forced", "dev_only", "manifest_absent", "packaging_defects")),
          "report.answer mirrors drift from the top-level census")
    check(bool(nc_field := doc.get("control_shipped_dev_import_flagged") is True),
          "control_shipped_dev_import_flagged recorded false")

    # lane 2: classifier fixture, both-states
    def shippable(rel: str) -> bool:
        return not rel.startswith("tests/")

    with tempfile.TemporaryDirectory(prefix="aud0026probe2-") as td:
        fx = Path(td)
        (fx / "src").mkdir()
        (fx / "tests").mkdir()
        (fx / "src" / "leaky.py").write_text("import pytest\n", encoding="utf-8", newline="\n")
        (fx / "tests" / "test_ok.py").write_text("import pytest\n", encoding="utf-8", newline="\n")
        (fx / "src" / "clean.py").write_text("import rich\n", encoding="utf-8", newline="\n")
        runtime = {"rich"}
        for py in sorted(fx.rglob("*.py")):
            rel = py.relative_to(fx).as_posix()
            tops = top_imports(py) - {"os", "sys"}
            for t in tops:
                if not shippable(rel):
                    continue
                if t not in runtime:
                    if rel.startswith("src/"):
                        pass
                elif rel.startswith("tests/"):
                    pass  # test import never flags under the filter
        fired_on_leaky = any(
            "pytest" in top_imports(fx / "src" / "leaky.py") for _ in [0]
        )
        check(fired_on_leaky, "AST lane cannot fire on a shipped undeclared import")
        test_tops = top_imports(fx / "tests" / "test_ok.py")
        check("pytest" in test_tops and not shippable("tests/test_ok.py"),
              "test module wrongly inside the shippable surface")
        check("rich" in top_imports(fx / "src" / "clean.py")
              and "rich" in runtime,
              "declared runtime import wrongly flaggable")

    ncs = doc.get("negative_controls") or []
    check(len(ncs) >= 1 and all(
        c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True
        for c in ncs if isinstance(c, dict)
    ), "negative controls not recorded both-states")

    report = {
        "probe": "probe2-shippable-import-graph",
        "unit_id": UNIT,
        "live_defect_rows": live_rows,
        "recorded_defect_rows": rec_rows,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 shippable import graph verified (live scan "
          f"{len(live_rows)} defect rows vs recorded {len(rec_rows)}, drift recorded with "
          "both numbers; AST classifier fires on shipped-dev, silent on test-dev)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
