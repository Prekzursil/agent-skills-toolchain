#!/usr/bin/env python3
"""IMP-0031 fixture-oracle + property tests for the three-way merger.

Runs standalone (`python3 -B tools/plugin/tests/test_three_way_merge.py`) and
prints one PASS line per test plus a terminal SUCCESS marker.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import base64
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.ours_invariant import make_triple, run_property, unique_ours_lines  # noqa: E402
from plugin.three_way_merge import merge_bytes, two_way_overwrite  # noqa: E402

FIXTURES = REPO / "tools" / "plugin" / "tests" / "fixtures" / "three_way" / "manifest.json"


def _blobs(fx: dict) -> tuple[bytes, bytes, bytes]:
    def blob(name: str, default: str) -> bytes:
        key_b64 = f"{name}_b64"
        if key_b64 in fx:
            return base64.b64decode(fx[key_b64])
        return fx[name].encode("utf-8")

    return blob("base", ""), blob("ours", ""), blob("theirs", "")


def test_fixture_oracle() -> None:
    manifest = json.loads(FIXTURES.read_text(encoding="utf-8"))
    failures: list[str] = []
    for fx in manifest["fixtures"]:
        b, o, t = _blobs(fx)
        res = merge_bytes(b, o, t, fx["path"])
        ok = res.status == fx["expected_status"] and res.strategy == fx["expected_strategy"]
        if not ok:
            failures.append(f"{fx['id']}: status={res.status}/{res.strategy}")
            continue
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
                failures.append(f"{fx['id']}: doc mismatch {got!r}")
        if "expected_text" in fx and res.text != fx["expected_text"]:
            failures.append(f"{fx['id']}: text mismatch {res.text!r}")
        if "expected_reason_contains" in fx:
            rep = json.dumps(res.report or {})
            if fx["expected_reason_contains"] not in rep:
                failures.append(f"{fx['id']}: report {rep}")
        if "expect_comments_preserved" in fx:
            if (res.report or {}).get("comments_preserved") != fx["expect_comments_preserved"]:
                failures.append(f"{fx['id']}: comments_preserved {(res.report or {}).get('comments_preserved')}")
        if "expected_conflict_regions" in fx:
            regions = [c.region for c in res.conflicts]
            if regions != fx["expected_conflict_regions"]:
                failures.append(f"{fx['id']}: regions {regions}")
        if "ours_side_must_contain" in fx and res.conflicts:
            ours_side = "\n".join(res.conflicts[0].ours)
            if fx["ours_side_must_contain"] not in ours_side:
                failures.append(f"{fx['id']}: ours side lost")
    if failures:
        print("FAIL test_fixture_oracle")
        for f in failures:
            print("  ", f)
        raise SystemExit(1)
    print("PASS test_fixture_oracle")


def test_json_structural_additive() -> None:
    res = merge_bytes(
        b'{"a": 1, "nested": {"c": 2}}\n',
        b'{"a": 1, "nested": {"c": 2}, "timeout": 30}\n',
        b'{"a": 1, "nested": {"c": 2, "gamma": 3}}\n',
        "settings.json",
    )
    assert res.status == "merged" and res.strategy == "json"
    got = json.loads(res.text or "{}")
    assert got == {"a": 1, "nested": {"c": 2, "gamma": 3}, "timeout": 30}, got
    print("PASS test_json_structural_additive")


def test_line_based_additive() -> None:
    res = merge_bytes(b"A\nC\n", b"A\nB\nC\n", b"A\nC\nD\n", "notes.md")
    assert res.status == "merged" and res.strategy == "line", (res.status, res.strategy)
    assert res.text == "A\nB\nC\nD\n", repr(res.text)
    print("PASS test_line_based_additive")


def test_binary_refuse() -> None:
    res = merge_bytes(b"\x00\x01", b"\x00\x01ours", b"\x00\x01theirs", "blob.bin")
    assert res.status == "refused" and res.strategy == "binary"
    assert "binary" in json.dumps(res.report)
    assert res.text is None and res.data is None
    print("PASS test_binary_refuse")


def test_property_unique_ours_lines_survive() -> None:
    rep = run_property(merge_bytes, n=200, seed=31)
    assert rep["ok"], rep
    assert rep["failures"] == 0 and rep["with_unique_ours_lines"] > 0, rep
    print("PASS test_property_unique_ours_lines_survive")


def test_negative_control_two_way_overwrite_fails_property() -> None:
    rng = random.Random(31)
    fired = 0
    for _ in range(200):
        base, ours, theirs = make_triple(rng)
        uniq = unique_ours_lines(base, ours, theirs)
        if not uniq:
            continue
        res = two_way_overwrite(
            "".join(base).encode(), "".join(ours).encode(), "".join(theirs).encode(), "notes.md"
        )
        text = res.text or ""
        if any(ln not in text for ln in uniq):
            fired += 1
    assert fired > 0, "two-way overwrite did NOT fail the property; control is inert"
    print(f"PASS test_negative_control_two_way_overwrite_fails_property (failures={fired})")


def main() -> int:
    test_fixture_oracle()
    test_json_structural_additive()
    test_line_based_additive()
    test_binary_refuse()
    test_property_unique_ours_lines_survive()
    test_negative_control_two_way_overwrite_fails_property()
    print("SUCCESS:IMP-0031 tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
