#!/usr/bin/env python3
"""Probe 2: UNTESTED cells reported not omitted; detector controls fire."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402

import compatibility as C  # noqa: E402

UNIT = "TST-0078"
OUT = "command-center/receipts/TST-0078.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
PUBLISHED = HERE / "fixtures" / "published"
SENTINEL = "SUCCESS:TST-0078"


def _ungated_copy(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)


def main() -> int:
    art_path = REPO / OUT
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        print("FAILED:TST-0078-probe2 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0078-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    contract = C.load_contract()
    axes = contract["axes"]
    expected = C.cartesian(axes)
    expected_ids = {
        C.cell_id(c["os"], c["client"], c["client_version"]) for c in expected
    }
    art_cells = doc["matrix"]["cells"]
    art_ids = {
        C.cell_id(c["os"], c["client"], c["client_version"]) for c in art_cells
    }
    if art_ids != expected_ids:
        print("FAILED:TST-0078-probe2 cartesian mismatch")
        print("missing", sorted(expected_ids - art_ids)[:8])
        print("extra", sorted(art_ids - expected_ids)[:8])
        return 1

    untested = [c for c in art_cells if c.get("outcome") == "UNTESTED"]
    if not untested:
        print("FAILED:TST-0078-probe2 UNTESTED omitted")
        return 1
    undeclared_live = []
    lookup = C.declared_map(contract)
    for axis_cell in expected:
        key = C.cell_id(axis_cell["os"], axis_cell["client"], axis_cell["client_version"])
        if key not in lookup:
            undeclared_live.append(axis_cell)
    if len(undeclared_live) != len(untested):
        print(
            "FAILED:TST-0078-probe2 UNTESTED count drift",
            len(undeclared_live),
            len(untested),
        )
        return 1
    for cell in untested:
        if cell.get("declared") == "SUPPORTED":
            print("FAILED:TST-0078-probe2 inferred SUPPORTED", cell)
            return 1
        if cell.get("attempted") is True:
            print("FAILED:TST-0078-probe2 UNTESTED marked attempted", cell)
            return 1

    dropped = [c for c in art_cells if c.get("outcome") != "UNTESTED"]
    dropped_check = C.completeness_ok(dropped, axes)
    if dropped_check["ok"] or not dropped_check["missing"]:
        print("FAILED:TST-0078-probe2 omit-untested mutant not detected", dropped_check)
        return 1
    honest = C.completeness_ok(art_cells, axes)
    if not honest["ok"]:
        print("FAILED:TST-0078-probe2 honest completeness failed", honest)
        return 1

    unsupported = next(
        c
        for c in art_cells
        if c.get("declared") == "UNSUPPORTED"
        and c.get("os") == "linux"
        and c.get("client") == "claude-code"
        and c.get("client_version") == "1.0.0"
    )
    with tempfile.TemporaryDirectory(prefix="tst0078-p2-") as tmp_s:
        tmp = Path(tmp_s)
        gated = C.attempt_install(
            PUBLISHED,
            tmp / "gated",
            {
                "os": unsupported["os"],
                "client": unsupported["client"],
                "client_version": unsupported["client_version"],
            },
            contract,
        )
        _ungated_copy(PUBLISHED, tmp / "ungated")
        ungated_present = (tmp / "ungated" / "plugin.json").is_file()
        if gated["installed"] or gated["plugin_present"] or gated["files_written"] != 0:
            print("FAILED:TST-0078-probe2 live gate installed unsupported", gated)
            return 1
        if not ungated_present:
            print("FAILED:TST-0078-probe2 ungated mutant did not land files")
            return 1
        if gated["outcome"] != "REFUSED":
            print("FAILED:TST-0078-probe2 gated outcome", gated["outcome"])
            return 1

    payload = {
        "probe": "probe2-untested-and-detector",
        "unit_id": UNIT,
        "cartesian": len(expected_ids),
        "untested": len(untested),
        "omit_untested_detected": True,
        "ungated_would_install_unsupported": True,
        "live_gate_refused_unsupported": True,
        "ok": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"SUCCESS:TST-0078-probe2 untested={len(untested)} "
        "omit-mutant-detected ungated-control"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
