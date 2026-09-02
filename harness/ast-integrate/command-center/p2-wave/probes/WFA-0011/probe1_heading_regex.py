#!/usr/bin/env python3
"""WFA-0011 probe 1: heading regex closing-anchor + id-set equality (signal A)."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import extract  # noqa: E402
from extract import (  # noqa: E402
    HEADING_ID_RE,
    has_closing_anchor,
    heading_ids,
    id_set_equal,
    load_json_records,
    naive_backtick_ids,
    unanchored_open_ids,
)
from fixtures import control_paths, write_control  # noqa: E402
from gate import compare_paths  # noqa: E402

UNIT = "WFA-0011"
ART = REPO / "command-center" / "wfa" / "WFA-0011-md-json-mirror-parity.json"
SENTINEL = "SUCCESS:WFA-0011"
BLOCKED = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
TRAPS_08 = {"wf-body-mention-trap", "wf-inline-heading-mention"}
TRAPS_09 = {"bp-body-mention-trap", "bp-inline-heading-mention"}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def rec_ids(text: str) -> list[str]:
    return [str(r.get("id") or "") for r in load_json_records(text)]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in BLOCKED:
        return fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    anchor = has_closing_anchor()
    src = inspect.getsource(extract)
    if not anchor["closing_anchor"]:
        return fail(f"closing-anchor-missing:{anchor}")
    if "`([A-Za-z]" not in HEADING_ID_RE.pattern:
        return fail("pattern-missing-opening-backtick-wrap")
    if ")`" not in HEADING_ID_RE.pattern:
        return fail("pattern-missing-closing-backtick")
    if not HEADING_ID_RE.pattern.rstrip().endswith("$"):
        return fail("pattern-missing-eol-anchor")
    if "HEADING_ID_RE" not in src or "NAIVE_BACKTICK_ID_RE" not in src:
        return fail("extractor-source-missing-named-regexes")

    write_control()
    paths = control_paths()
    md08 = paths["08_md"].read_text(encoding="utf-8")
    js08 = paths["08_json"].read_text(encoding="utf-8")
    md09 = paths["09_md"].read_text(encoding="utf-8")
    js09 = paths["09_json"].read_text(encoding="utf-8")

    honest08 = set(heading_ids(md08))
    naive08 = set(naive_backtick_ids(md08))
    open08 = set(unanchored_open_ids(md08))
    if honest08 & TRAPS_08:
        return fail(f"honest-fired-on-08-traps:{sorted(honest08 & TRAPS_08)}")
    if "Background" in honest08:
        return fail("honest-fired-on-planted-non-id-heading")
    if not TRAPS_08 <= naive08:
        return fail(f"naive-missed-08-traps naive={sorted(naive08)}")
    if not TRAPS_08 <= open08:
        return fail("unanchored-open-missed-08-traps")
    if not TRAPS_08.issubset(naive08 - honest08):
        return fail("closing-anchor-did-not-exclude-backtick-fp-class")

    honest09 = set(heading_ids(md09))
    naive09 = set(naive_backtick_ids(md09))
    if honest09 & TRAPS_09:
        return fail(f"honest-fired-on-09-traps:{sorted(honest09 & TRAPS_09)}")
    if not TRAPS_09 <= naive09:
        return fail("naive-missed-09-traps")

    a08 = id_set_equal(heading_ids(md08), rec_ids(js08))
    a09 = id_set_equal(heading_ids(md09), rec_ids(js09))
    if not a08["equal"]:
        return fail(f"08-id-set:{a08['only_markdown']} {a08['only_json']}")
    if not a09["equal"]:
        return fail(f"09-id-set:{a09['only_markdown']} {a09['only_json']}")
    if a08["markdown_n"] != 36 or a09["markdown_n"] != 36:
        return fail(f"control-n 08={a08['markdown_n']} 09={a09['markdown_n']}")

    live08 = compare_paths(paths["08_md"], paths["08_json"], REPO)
    live09 = compare_paths(paths["09_md"], paths["09_json"], REPO)
    if not live08["signal_a"]["equal"] or not live09["signal_a"]["equal"]:
        return fail("path-compare-id-set")

    if heading_ids("## Background\n\nNot an id.\n"):
        return fail("planted-non-id-heading-not-silent")

    out = {
        "ok": True,
        "closing_anchor": anchor,
        "honest_silent_on_traps": True,
        "naive_fires_on_traps": True,
        "id_set_08": {"equal": True, "n": a08["markdown_n"]},
        "id_set_09": {"equal": True, "n": a09["markdown_n"]},
        "naive_extra_08": sorted(naive08 - honest08),
        "naive_extra_09": sorted(naive09 - honest09),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "closing_anchor=True naive_fp_class=True "
        f"n08={a08['markdown_n']} n09={a09['markdown_n']}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 heading closing-anchor; id-set equality; traps silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
