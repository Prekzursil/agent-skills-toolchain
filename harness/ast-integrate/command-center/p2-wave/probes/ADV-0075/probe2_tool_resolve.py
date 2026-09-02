#!/usr/bin/env python3
"""Named probe 2: tool-layer OS resolve (argv/inode/case-fold). Not a display check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import ordinary_identity, planted_homoglyph_fold_equal  # noqa: E402
from fixtures import ORDINARY, PAYLOADS, ensure_tree  # noqa: E402
from tool_layer import probe2_measure  # noqa: E402

UNIT = "ADV-0075"
ART = REPO / "command-center/adversarial/ADV-0075-filename-path-unicode-injection.json"
SCHEMA = REPO / "command-center/schema/injection-corpus-result.schema.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def probe2_payload(tree) -> dict:
    live = probe2_measure(tree)
    return {
        "probe": "probe2-tool-resolve",
        "unit_id": UNIT,
        "ordinary": live["ordinary"],
        "ordinary_basename": live["ordinary_basename"],
        "ordinary_open_ok": live["ordinary_open_ok"],
        "dash_parsed_as_flag": live["dash_parsed_as_flag"],
        "dash_without_has_payload": live["dash_without_has_payload"],
        "dash_with_has_payload": live["dash_with_has_payload"],
        "homoglyph_same_inode": live["homoglyph_same_inode"],
        "homoglyph_latin_inode": live["homoglyph_latin_inode"],
        "homoglyph_twin_inode": live["homoglyph_twin_inode"],
        "case_os_same_inode": live["case_os_same_inode"],
        "case_fold_collides": live["case_fold_collides"],
        "case_fold_source": live["case_fold_source"],
        "newline_argv_ok": live["newline_argv_ok"],
        "newline_unquoted_splits": live["newline_unquoted_splits"],
        "newline_unquoted_ifs_words": live["newline_unquoted_ifs_words"],
        "rtl_argv_ok": live["rtl_argv_ok"],
        "planted_homoglyph_fold_equal": planted_homoglyph_fold_equal(),
        "ordinary_payload": live["ordinary_payload"],
    }


def main() -> int:
    tree = ensure_tree()
    live = probe2_payload(tree)
    if not live["ordinary_open_ok"]:
        return fail("ordinary file did not open via tool argv", live)
    if not ordinary_identity(ORDINARY, live["ordinary_basename"]):
        return fail("ordinary basename identity", live)
    if live["ordinary_payload"] != PAYLOADS[ORDINARY]:
        return fail("ordinary payload mismatch")
    if not live["dash_parsed_as_flag"]:
        return fail("leading-dash was not parsed as a flag by cat argv", live)
    if live["homoglyph_same_inode"]:
        return fail("homoglyph and latin config share an inode")
    if live["case_os_same_inode"]:
        return fail("case pair collapsed at OS (unexpected on this Linux tree)")
    if not live["case_fold_collides"]:
        return fail("reconcile_delivery._fold did not collide case pair", live)
    if not live["newline_argv_ok"]:
        return fail("argv cat failed on newline name", live)
    if not live["newline_unquoted_splits"]:
        return fail("unquoted IFS did not split newline name", live)
    if not live["rtl_argv_ok"]:
        return fail("argv cat failed on RTL name", live)
    if not live["planted_homoglyph_fold_equal"]:
        return fail("planted homoglyph fold silent")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != UNIT:
            return fail("unit_id", doc.get("unit_id"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared {doc.get('state')}")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            return fail("jsonschema missing")
        errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errors:
            return fail("schema", [e.message for e in errors[:8]])
        targets = {t["id"]: t["verdict"] for t in doc.get("targets") or []}
        if targets.get("leading-dash") != "CONFIRMED":
            return fail("artifact leading-dash verdict", targets)
        if targets.get("homoglyph-twin") != "CONFIRMED":
            return fail("artifact homoglyph-twin verdict", targets)
        if targets.get("case-collision") != "CONFIRMED":
            return fail("artifact case-collision verdict", targets)
        art_p2 = None
        for item in doc.get("named_probes") or []:
            if item.get("id") == "probe2":
                art_p2 = item
                break
        if not art_p2 or "dash_parsed_as_flag" not in (art_p2.get("raw_output") or ""):
            return fail("artifact missing probe2 raw_output")

    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0075-probe2 tool-layer OS resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
