#!/usr/bin/env python3
"""IMP-0031 probe1: fixture oracle — merge output equals the manifest oracle.

7 fixture triples (JSON structural, TOML structural, markdown line-diff3
additive + disjoint, binary refuse, reviewer key-reorder-plus-comment, and a
both-changed conflict). Independent of the implementer's own tests because the
comparison targets are hand-authored in the manifest, not derived from the
merger output.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import base64
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.three_way_merge import merge_bytes  # noqa: E402

MANIFEST = REPO / "tools" / "plugin" / "tests" / "fixtures" / "three_way" / "manifest.json"


def _blob(fx: dict, name: str) -> bytes:
    if f"{name}_b64" in fx:
        return base64.b64decode(fx[f"{name}_b64"])
    return fx[name].encode("utf-8")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    passed: list[str] = []
    failed: list[str] = []
    for fx in manifest["fixtures"]:
        b, o, t = _blob(fx, "base"), _blob(fx, "ours"), _blob(fx, "theirs")
        res = merge_bytes(b, o, t, fx["path"])
        problems: list[str] = []
        if res.status != fx["expected_status"]:
            problems.append(f"status={res.status} want={fx['expected_status']}")
        if res.strategy != fx["expected_strategy"]:
            problems.append(f"strategy={res.strategy} want={fx['expected_strategy']}")
        if "expected_doc" in fx:
            import tomllib

            if fx["expected_strategy"] == "json":
                body = "\n".join(
                    ln for ln in (res.text or "").splitlines()
                    if not ln.lstrip().startswith("//")
                )
                got = json.loads(body)
            else:
                got = tomllib.loads(res.text or "")
            if got != fx["expected_doc"]:
                problems.append(f"doc mismatch got={got!r}")
        if "expected_text" in fx and res.text != fx["expected_text"]:
            problems.append(f"text mismatch got={res.text!r}")
        if "expected_reason_contains" in fx:
            if fx["expected_reason_contains"] not in json.dumps(res.report or {}):
                problems.append(f"report mismatch {res.report!r}")
        if "expect_comments_preserved" in fx:
            if (res.report or {}).get("comments_preserved") != fx["expect_comments_preserved"]:
                problems.append(f"comments_preserved={(res.report or {}).get('comments_preserved')}")
        if "expected_conflict_regions" in fx:
            regions = sorted(c.region for c in res.conflicts)
            if regions != sorted(fx["expected_conflict_regions"]):
                problems.append(f"regions={regions}")
        if "ours_side_must_contain" in fx and res.conflicts:
            if fx["ours_side_must_contain"] not in "\n".join(res.conflicts[0].ours):
                problems.append("ours-side line lost from conflict record")
        if problems:
            failed.append(f"{fx['id']}: " + "; ".join(problems))
        else:
            passed.append(fx["id"])
    print(json.dumps({"fixtures": len(passed) + len(failed), "passed": len(passed),
                      "failed": failed}, sort_keys=True))
    if failed:
        print(f"FAILED:IMP-0031-probe1 {failed}")
        return 1
    print(f"SUCCESS:IMP-0031-probe1 {len(passed)}/{len(passed) + len(failed)} fixture oracle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
