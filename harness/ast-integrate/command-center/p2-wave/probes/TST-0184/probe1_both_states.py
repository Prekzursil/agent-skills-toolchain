#!/usr/bin/env python3
"""Probe 1: both-states — clean JSON parses; JSON5-isms reject with line:column.

Live SUT: tools.plugin.strict_json and tools.marketplace.permission_scan.load_manifest.
Lenient strip_json5 is the fixture-validity control (dirty docs are JSON5, not garbage).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.permission_scan import load_manifest  # noqa: E402
from tools.plugin.strict_json import (  # noqa: E402
    StrictJSONError,
    locate_json5_isms,
    parse_strict,
    strip_json5,
)

CLEAN = """{
  "name": "tst-0184-clean",
  "version": "1.0.0",
  "description": "strict-clean plugin manifest",
  "keywords": ["json", "strict"],
  "note": "http://example.invalid/path // not a comment"
}
"""

TRAILING_OBJECT = """{
  "name": "tst-0184-trailing-object",
  "version": "1.0.0",
}
"""

TRAILING_ARRAY = """{
  "name": "tst-0184-trailing-array",
  "keywords": ["a", "b",]
}
"""

LINE_COMMENT = """{
  "name": "tst-0184-line-comment"
  // planted line comment
}
"""

BLOCK_COMMENT = """{
  "name": "tst-0184-block",
  /* planted block comment */
  "version": "1.0.0"
}
"""

COMMENT_IN_STRING = """{
  "name": "has // slash-slash inside",
  "note": "also /* block-looking */ text"
}
"""


def expect_reject(label: str, text: str, kinds: set[str]) -> dict:
    try:
        parse_strict(text)
        raise AssertionError(f"{label}: strict parser accepted JSON5-ism")
    except StrictJSONError as exc:
        if exc.kind not in kinds:
            raise AssertionError(f"{label}: kind={exc.kind!r} not in {kinds}") from exc
        if exc.line < 1 or exc.column < 1:
            raise AssertionError(f"{label}: missing position {exc.to_dict()}") from exc
        loc = locate_json5_isms(text)
        if not loc:
            raise AssertionError(f"{label}: independent scanner silent") from exc
        stripped = strip_json5(text)
        json.loads(stripped)
        return {
            "kind": exc.kind,
            "label": label,
            "lenient_accepted": True,
            "line": exc.line,
            "column": exc.column,
            "position": f"{exc.line}:{exc.column}",
            "scanner_kinds": [f["kind"] for f in loc],
        }


def live_load(text: str, expect_ok: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0184-") as tmp:
        root = Path(tmp)
        (root / "plugin.json").write_text(text, encoding="utf-8")
        if expect_ok:
            data = load_manifest(root)
            return {"ok": True, "name": data.get("name")}
        try:
            load_manifest(root)
            return {"ok": True, "unexpected_accept": True}
        except (json.JSONDecodeError, StrictJSONError, ValueError) as exc:
            return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}


def main() -> int:
    clean = parse_strict(CLEAN)
    if not isinstance(clean, dict):
        print("FAILED:TST-0184-probe1 clean did not parse as object")
        return 1
    if clean.get("name") != "tst-0184-clean":
        print("FAILED:TST-0184-probe1 field mismatch")
        return 1
    if locate_json5_isms(CLEAN):
        print("FAILED:TST-0184-probe1 scanner false-positive on clean JSON")
        return 1
    in_string = parse_strict(COMMENT_IN_STRING)
    if "slash-slash" not in str(in_string.get("name")):
        print("FAILED:TST-0184-probe1 comment-in-string mangled")
        return 1
    if locate_json5_isms(COMMENT_IN_STRING):
        print("FAILED:TST-0184-probe1 scanner treated in-string slashes as comments")
        return 1

    rows = [
        expect_reject("trailing-object", TRAILING_OBJECT, {"trailing-comma"}),
        expect_reject("trailing-array", TRAILING_ARRAY, {"trailing-comma"}),
        expect_reject("line-comment", LINE_COMMENT, {"line-comment"}),
        expect_reject("block-comment", BLOCK_COMMENT, {"block-comment"}),
    ]
    live_clean = live_load(CLEAN, True)
    live_dirty = live_load(TRAILING_OBJECT, False)
    if live_dirty.get("ok") is True:
        print("FAILED:TST-0184-probe1 marketplace load_manifest accepted trailing comma")
        print(json.dumps(live_dirty, sort_keys=True))
        return 1
    if live_clean.get("name") != "tst-0184-clean":
        print("FAILED:TST-0184-probe1 live load_manifest missed clean name")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-both-states-json5-reject",
        "rejects": rows,
        "live_load_clean": live_clean,
        "live_load_trailing_comma": live_dirty,
        "clean_name": clean.get("name"),
        "comment_in_string_ok": True,
        "unit_id": "TST-0184",
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        "clean_ok=True rejects="
        + ",".join(f"{r['label']}@{r['position']}" for r in rows)
        + f" live_dirty_ok={live_dirty.get('ok')}"
    )
    print(
        "SUCCESS:TST-0184-probe1 both-states: strict-clean parses; "
        "trailing commas and comments reject with line:column"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
