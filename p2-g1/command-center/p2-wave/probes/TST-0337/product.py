#!/usr/bin/env python3
"""Synthetic product + tests for TST-0337 impacted-test selector proof.

Dependency DAG (file-level):

  leaf_00 .. leaf_07   (no imports)
       \\  /   \\  /
       mid_00  mid_01  mid_02  mid_03
              \\    |    /
                 root
  independent          (isolated)

Each leaf exposes three functions:
  public()  — asserted by test_{leaf}_public only
  helper()  — used by the owning mid; NOT called by the leaf's public test
  secret()  — asserted ONLY by test_newfile_leaf_00_secret, which is
              deliberately absent from the coverage map (new-file case)
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

LEAVES = [f"leaf_{i:02d}" for i in range(8)]
MIDS = [f"mid_{i:02d}" for i in range(4)]
ROOT = "root"
INDEPENDENT = "independent"

# mid_i depends on leaf_{2i} and leaf_{2i+1}
MID_LEAVES = {MIDS[i]: (LEAVES[2 * i], LEAVES[2 * i + 1]) for i in range(4)}


def leaf_value(i: int) -> int:
    return 10 + i * 3


def leaf_offset(i: int) -> int:
    return 1


def leaf_source(i: int) -> str:
    return (
        f"VALUE = {leaf_value(i)}\n"
        f"OFFSET = {leaf_offset(i)}\n"
        "\n"
        "def public():\n"
        "    return VALUE + OFFSET\n"
        "\n"
        "def helper():\n"
        "    return VALUE * 3 + OFFSET\n"
        "\n"
        "def secret():\n"
        "    return VALUE + 100\n"
    )


def mid_source(mid: str) -> str:
    a, b = MID_LEAVES[mid]
    return (
        f"from {a} import helper as h0\n"
        f"from {b} import helper as h1\n"
        "\n"
        "def public():\n"
        "    return h0() + h1()\n"
    )


def root_source() -> str:
    imports = "\n".join(
        f"from {m} import public as {m}_public" for m in MIDS
    )
    add = " + ".join(f"{m}_public()" for m in MIDS)
    return f"{imports}\n\ndef public():\n    return {add}\n"


def independent_source() -> str:
    return "VALUE = 42\n\ndef public():\n    return VALUE\n"


def product_sources() -> dict[str, str]:
    src: dict[str, str] = {}
    for i, name in enumerate(LEAVES):
        src[name] = leaf_source(i)
    for mid in MIDS:
        src[mid] = mid_source(mid)
    src[ROOT] = root_source()
    src[INDEPENDENT] = independent_source()
    return src


def import_graph() -> dict[str, list[str]]:
    g = {name: [] for name in LEAVES}
    for mid, (a, b) in MID_LEAVES.items():
        g[mid] = [a, b]
    g[ROOT] = list(MIDS)
    g[INDEPENDENT] = []
    return g


def closure(module: str, graph: dict[str, list[str]] | None = None) -> set[str]:
    graph = graph or import_graph()
    seen: set[str] = set()
    stack = [module]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur) or [])
    return seen


def mapped_tests() -> dict[str, str]:
    """test_id -> entry module (the module the test imports)."""
    out: dict[str, str] = {}
    for leaf in LEAVES:
        out[f"test_{leaf}_public"] = leaf
    for mid in MIDS:
        out[f"test_{mid}"] = mid
    out["test_root"] = ROOT
    out["test_independent"] = INDEPENDENT
    return out


NEWFILE_TEST = "test_newfile_leaf_00_secret"


def all_test_ids() -> list[str]:
    return list(mapped_tests()) + [NEWFILE_TEST]


def coverage_map() -> dict[str, list[str]]:
    """File-level coverage map. NEWFILE_TEST is intentionally omitted."""
    cmap: dict[str, list[str]] = {}
    for test_id, entry in mapped_tests().items():
        files = sorted(f"{m}.py" for m in closure(entry))
        cmap[test_id] = files
    return cmap


def expected_values() -> dict[str, int]:
    """Oracle for the unmutated product."""
    vals = {}
    for i, leaf in enumerate(LEAVES):
        v, o = leaf_value(i), leaf_offset(i)
        vals[f"{leaf}.public"] = v + o
        vals[f"{leaf}.helper"] = v * 3 + o
        vals[f"{leaf}.secret"] = v + 100
    for mid, (a, b) in MID_LEAVES.items():
        vals[f"{mid}.public"] = vals[f"{a}.helper"] + vals[f"{b}.helper"]
    vals["root.public"] = sum(vals[f"{m}.public"] for m in MIDS)
    vals["independent.public"] = 42
    return vals


def run_one_test(test_id: str, mods: dict) -> None:
    exp = expected_values()
    if test_id.endswith("_public") and test_id.startswith("test_leaf_"):
        leaf = test_id[len("test_") : -len("_public")]
        got = mods[leaf].public()
        if got != exp[f"{leaf}.public"]:
            raise AssertionError(f"{test_id}: {got} != {exp[f'{leaf}.public']}")
        return
    if test_id.startswith("test_mid_"):
        mid = test_id[len("test_") :]
        got = mods[mid].public()
        if got != exp[f"{mid}.public"]:
            raise AssertionError(f"{test_id}: {got} != {exp[f'{mid}.public']}")
        return
    if test_id == "test_root":
        got = mods[ROOT].public()
        if got != exp["root.public"]:
            raise AssertionError(f"test_root: {got} != {exp['root.public']}")
        return
    if test_id == "test_independent":
        got = mods[INDEPENDENT].public()
        if got != exp["independent.public"]:
            raise AssertionError(f"test_independent: {got} != {exp['independent.public']}")
        return
    if test_id == NEWFILE_TEST:
        got = mods[LEAVES[0]].secret()
        if got != exp[f"{LEAVES[0]}.secret"]:
            raise AssertionError(f"{NEWFILE_TEST}: {got} != {exp[f'{LEAVES[0]}.secret']}")
        return
    raise KeyError(f"unknown test {test_id}")


def dump_coverage_map(path: Path | None = None) -> Path:
    import json

    path = path or (HERE / "fixtures" / "coverage_map.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "unit_id": "TST-0337",
        "kind": "file-level-coverage-map",
        "note": (
            "Deterministic map from import-graph closure. "
            f"{NEWFILE_TEST} is omitted on purpose (new-file default SELECTED)."
        ),
        "tests": coverage_map(),
        "unmapped_tests": [NEWFILE_TEST],
        "all_tests": all_test_ids(),
    }
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path
