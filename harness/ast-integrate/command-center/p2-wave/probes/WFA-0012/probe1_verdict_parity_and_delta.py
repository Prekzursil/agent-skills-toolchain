#!/usr/bin/env python3
"""Probe 1: verdict parity (signal A) and EOL delta arithmetic (signal B)."""
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
    print(f"FAILED:WFA-0012-probe1 {msg}")
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
    if doc.get("unit_id") != "WFA-0012":
        return fail("unit_id")

    live = G.live_measure()
    sa = live["signal_a"]
    sb = live["signal_b"]
    print(
        "portable={0} lf_copy={1} ci={2} naive={3} archive={4} "
        "payload_delta={5}/{6} notes_delta={7}/{8}".format(
            sa["windows_worktree_portable_verdict"],
            sa["lf_copy_verdict"],
            sa["ci_blob_verdict"],
            sa["naive_worktree_verdict"],
            sa["archive_verdict"],
            sb["payload"]["delta_bytes"],
            sb["payload"]["line_count"],
            sb["notes"]["delta_bytes"],
            sb["notes"]["line_count"],
        )
    )
    if not sa["identical_portable_and_ci"]:
        return fail("portable verdicts do not match CI")
    if sa["windows_worktree_portable_verdict"] != "GREEN":
        return fail("Windows-like portable gate not GREEN")
    if sa["lf_copy_verdict"] != "GREEN":
        return fail("LF copy gate not GREEN")
    if sa["naive_worktree_verdict"] != "RED":
        return fail("naive worktree hashing did not go RED")
    if sa["archive_verdict"] != "RED":
        return fail("git archive hashing did not go RED")
    if not sa["naive_differs_from_ci"]:
        return fail("naive route already matched CI; trap not live")
    if not live["archive_returns_crlf"]:
        return fail("git archive did not return CRLF")
    if live["blob_crlf"] != 0:
        return fail("cat-file blob is not LF")
    if not live["cat_file_equals_git_show"]:
        return fail("git show disagrees with git cat-file")
    if not live["eol_normalisation"]["routes_identical_after_lf"]:
        return fail("routes differ after LF normalisation")
    if live["content_bytes_route"] != "git cat-file":
        return fail(f"content_bytes route {live['content_bytes_route']}")
    if not sb["pure_eol_delta_equals_line_count"]:
        return fail("pure-EOL delta != line_count")
    if sb["payload"]["class"] != "EOL-ARTIFACT":
        return fail("payload not classified EOL-ARTIFACT")
    if sb["notes"]["class"] != "EOL-ARTIFACT":
        return fail("notes not classified EOL-ARTIFACT")
    subst = sb["same_length_content_substitution"]
    if subst["class"] != "CONTENT-DIFFERENCE" or subst["lf_bytes_equal"]:
        return fail("same-length substitution not distinguished from EOL")

    art_sa = doc.get("signal_a") or {}
    if art_sa.get("identical_portable_and_ci") is not True:
        return fail("artifact signal_a.identical_portable_and_ci")
    art_sb = doc.get("signal_b") or {}
    if art_sb.get("pure_eol_delta_equals_line_count") is not True:
        return fail("artifact signal_b.pure_eol_delta_equals_line_count")
    if art_sa.get("windows_worktree_portable_verdict") != sa[
        "windows_worktree_portable_verdict"
    ] or art_sa.get("naive_worktree_verdict") != sa["naive_worktree_verdict"]:
        return fail("artifact signal_a verdict drift")

    print(
        "identical_portable_and_ci=True delta==line_count "
        "substitution=CONTENT-DIFFERENCE"
    )
    print("SUCCESS:WFA-0012-probe1 verdict-parity and eol-delta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
