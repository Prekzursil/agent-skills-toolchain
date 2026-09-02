#!/usr/bin/env python3
"""Probe 2: both-states one-byte control, AST inspection, LF checkout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
import eol_gate as G  # noqa: E402

ART = REPO / E.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0012-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if E.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    live = G.live_measure()
    both = live["both_states"]
    inspection = live["inspection"]
    lf_co = live["lf_checkout"]
    reach6 = live["validate_reach6"]
    print(
        "eol_only_green={0} one_byte_red={1} did_not_disarm={2} "
        "inspect_pass={3} lf_checkout={4} reach6={5}".format(
            both["eol_only_portable_green"],
            both["one_byte_content_change_still_red"],
            both["portability_fix_did_not_disarm"],
            inspection["pass"],
            lf_co["verdict"],
            reach6["pass"],
        )
    )
    if not both["eol_only_portable_green"]:
        return fail("EOL-only portable gate not GREEN")
    if not both["one_byte_content_change_still_red"]:
        return fail("one-byte content change did not stay RED")
    if not both["portability_fix_did_not_disarm"]:
        return fail("portability fix disarmed the gate")
    if not both["naive_worktree_red_on_eol_only"]:
        return fail("naive worktree was not RED on EOL-only")
    if not inspection["pass"]:
        return fail(f"source inspection failed {inspection}")
    if not inspection["cat_file_uses_cat_file_dash_p"]:
        return fail("cat_file does not call git cat-file -p")
    if not inspection["git_show_uses_show"]:
        return fail("git_show does not call git show")
    if inspection["archive_call_in_gate_funcs"]:
        return fail(f"archive on gate path {inspection['archive_call_in_gate_funcs']}")
    if not inspection["archive_confined_to_measurement"]:
        return fail("archive not confined to measurement helper")
    if not lf_co["matches_ci"]:
        return fail("LF checkout verdict != CI")
    if not lf_co["bytes_equal_blob"]:
        return fail("LF checkout bytes != blob")
    if not reach6["pass"]:
        return fail("validate.py REACH-6 inspection failed")
    recipe_ok = (
        reach6.get("uses_blobread_content_bytes")
        or reach6.get("uses_git_cat_file")
        or reach6.get("lf_normalises_before_hash")
    )
    if not recipe_ok:
        return fail(
            "validate.py REACH-6 uses neither cat-file/blobread nor LF-normalise"
        )
    if reach6.get("prescribes_git_archive"):
        return fail("validate.py REACH-6 still hashes via git archive")

    src = (HERE / "eol_gate.py").read_text(encoding="utf-8")
    if "cat-file" not in src or "-p" not in src:
        return fail("eol_gate.py source lacks cat-file -p")
    live_insp = G.inspect_gate_source(src)
    if not live_insp["pass"]:
        return fail("re-parse inspection failed")

    art_both = doc.get("both_states") or {}
    if art_both.get("portability_fix_did_not_disarm") is not True:
        return fail("artifact both_states.portability_fix_did_not_disarm")
    art_ins = doc.get("inspection") or {}
    if art_ins.get("pass") is not True:
        return fail("artifact inspection.pass")
    art_lf = doc.get("lf_checkout") or {}
    if art_lf.get("matches_ci") is not True:
        return fail("artifact lf_checkout.matches_ci")

    print("both-states armed; cat-file -p on gate path; LF checkout matches CI")
    print("SUCCESS:WFA-0012-probe2 both-states inspection lf-checkout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
