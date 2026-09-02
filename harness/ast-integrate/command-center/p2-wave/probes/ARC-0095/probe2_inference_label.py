#!/usr/bin/env python3
"""Named probe 2: inferred cells are visually and machine-distinct from tested.

A linux SUPPORTED cell must not paint its windows neighbour SUPPORTED.
With infer=true the neighbour is INFERRED (different token, glyph, css_class,
is_pass). With infer=false it stays NOT-CHECKED, still not SUPPORTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import matrix as M  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0095.json"

AXES = {
    "operating_system": ["linux", "windows"],
    "client": ["claude-code"],
    "client_version": ["2.0.0"],
    "shell": ["bash"],
    "package_version": ["0.1.0"],
}


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0095-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("contract artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:ARC-0095" not in blob:
        return fail("sentinel absent")
    rules = doc.get("evidence_rules") or {}
    if rules.get("adjacent_inference_never_supported") is not True:
        return fail("contract missing adjacent_inference_never_supported")
    if rules.get("adjacent_inference_label") != "INFERRED":
        return fail("contract inference label is not INFERRED")

    linux_id = M.cell_id(
        {
            "operating_system": "linux",
            "client": "claude-code",
            "client_version": "2.0.0",
            "shell": "bash",
            "package_version": "0.1.0",
        }
    )
    win_id = M.cell_id(
        {
            "operating_system": "windows",
            "client": "claude-code",
            "client_version": "2.0.0",
            "shell": "bash",
            "package_version": "0.1.0",
        }
    )
    receipt = M.make_receipt(
        operating_system="linux",
        client="claude-code",
        client_version="2.0.0",
        shell="bash",
        package_version="0.1.0",
        run_id="arc-0095-probe2-planted",
    )

    inferred_mx = M.generate(
        [receipt],
        axes=AXES,
        infer=True,
        program_ran_on=["linux"],
        expand_versions_from_receipts=False,
    )
    plain_mx = M.generate(
        [receipt],
        axes=AXES,
        infer=False,
        program_ran_on=["linux"],
        expand_versions_from_receipts=False,
    )
    tested = M.cell_by_id(inferred_mx, linux_id)
    inferred = M.cell_by_id(inferred_mx, win_id)
    neighbour_plain = M.cell_by_id(plain_mx, win_id)
    if tested is None or inferred is None or neighbour_plain is None:
        return fail("expected cells missing")

    if tested["status"] != "SUPPORTED" or not tested["is_pass"]:
        return fail(f"tested cell status={tested['status']!r}")
    if inferred["status"] != "INFERRED":
        return fail(f"inferred neighbour status={inferred['status']!r} want INFERRED")
    if inferred["status"] == "SUPPORTED":
        return fail("inferred cell labelled SUPPORTED")
    if inferred["is_pass"] or inferred["render"]["is_pass"]:
        return fail("inferred cell is_pass true (would read as a pass)")
    if inferred["render"]["token"] == tested["render"]["token"]:
        return fail("token collision INFERRED vs SUPPORTED")
    if inferred["render"]["glyph"] == tested["render"]["glyph"]:
        return fail("glyph collision INFERRED vs SUPPORTED")
    if inferred["render"]["css_class"] == tested["render"]["css_class"]:
        return fail("css_class collision INFERRED vs SUPPORTED")
    if inferred["render"]["color_role"] == tested["render"]["color_role"]:
        return fail("color_role collision INFERRED vs SUPPORTED")
    if inferred["render"]["machine_status"] != "INFERRED":
        return fail("machine_status not INFERRED")
    if neighbour_plain["status"] != "NOT-CHECKED":
        return fail(
            f"without infer, neighbour is {neighbour_plain['status']!r} not NOT-CHECKED"
        )
    if neighbour_plain["status"] == "SUPPORTED":
        return fail("adjacent cell inferred as SUPPORTED with infer=false")

    table = M.ascii_table(inferred_mx)
    if M.RENDER["SUPPORTED"]["glyph"] not in table:
        return fail("ascii table missing SUPPORTED glyph")
    if M.RENDER["INFERRED"]["glyph"] not in table:
        return fail("ascii table missing INFERRED glyph")
    if M.RENDER["SUPPORTED"]["glyph"] == M.RENDER["INFERRED"]["glyph"]:
        return fail("glyphs not distinct")

    # Naive renderer that only paints is_pass must not paint INFERRED.
    naive_pass_ids = [c["id"] for c in inferred_mx["cells"] if c["render"]["is_pass"]]
    if win_id in naive_pass_ids:
        return fail("naive is_pass renderer would paint INFERRED as pass")
    if linux_id not in naive_pass_ids:
        return fail("naive is_pass renderer dropped the tested cell")

    summary = {
        "probe": "probe2-inference-label",
        "unit_id": "ARC-0095",
        "pass": True,
        "tested_status": tested["status"],
        "inferred_status": inferred["status"],
        "plain_neighbour_status": neighbour_plain["status"],
        "token_distinct": inferred["render"]["token"] != tested["render"]["token"],
        "glyph_distinct": inferred["render"]["glyph"] != tested["render"]["glyph"],
        "css_class_distinct": inferred["render"]["css_class"]
        != tested["render"]["css_class"],
        "machine_distinct": inferred["status"] != tested["status"],
        "inferred_is_pass": inferred["is_pass"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"tested={tested['status']} inferred={inferred['status']} "
        f"plain_neighbour={neighbour_plain['status']} "
        f"glyph {tested['render']['glyph']}/{inferred['render']['glyph']}"
    )
    print("SUCCESS:ARC-0095-probe2 inference labelling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
