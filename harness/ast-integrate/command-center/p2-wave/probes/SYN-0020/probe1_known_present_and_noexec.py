#!/usr/bin/env python3
"""Named probe 1: known-present git-archive CONTRADICT + noexec both-states.

Re-extracts and re-classifies live. A clean noexec marker must skip; the
same command unmarked must be extracted. The planted pre-fix git-archive
recipe must be CONTRADICT. A negated mention must not be a prescription.
Artifact fingerprint must match this live run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    COMPLETION_SENTINEL,
    KNOWN_PRESENT_FIXTURE,
    KNOWN_PRESENT_SNIPPET,
    LIVE_CHECKLIST,
    NEGATED_MENTION,
    OUT_REL,
    UNIT_ID,
    domain,
)
from extract import extract_path  # noqa: E402
from report import measured  # noqa: E402
from statements import is_archive_lf_blob_prescription  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    live = measured()
    kp = live["known_present_control"]
    noexec = live["noexec_control"]
    mention = live["mention_control"]
    fp = live["fingerprint"]
    print(
        json.dumps(
            {
                "probe": "probe1-known-present-and-noexec",
                "known_present_fired": kp.get("fired"),
                "snippet_in_live_checklist": kp.get("snippet_in_live_checklist"),
                "snippet_in_planted_fixture": kp.get("snippet_in_planted_fixture"),
                "contradict_rows": len(kp.get("rows") or []),
                "noexec_pass": noexec.get("pass"),
                "mention_pass": mention.get("pass"),
                "fingerprint": fp,
            },
            sort_keys=True,
        )
    )
    if not kp.get("fired"):
        print("FAILED:SYN-0020-probe1 known-present control did not fire")
        return 1
    if not noexec.get("pass"):
        print("FAILED:SYN-0020-probe1 noexec both-states")
        return 1
    if not mention.get("pass"):
        print("FAILED:SYN-0020-probe1 mention treated as prescription")
        return 1
    if fp.get("agree_without_test_id") != 0:
        print("FAILED:SYN-0020-probe1 silent AGREE")
        return 1

    planted = REPO / KNOWN_PRESENT_FIXTURE
    if not planted.is_file():
        print("FAILED:SYN-0020-probe1 planted known-present fixture missing")
        return 1
    planted_text = planted.read_text(encoding="utf-8")
    if KNOWN_PRESENT_SNIPPET not in planted_text:
        print("FAILED:SYN-0020-probe1 snippet absent from planted fixture")
        return 1

    checklist = REPO / LIVE_CHECKLIST
    if not checklist.is_file():
        print("FAILED:SYN-0020-probe1 live RELEASE-CHECKLIST.md missing")
        return 1
    live_text = checklist.read_text(encoding="utf-8")
    if KNOWN_PRESENT_SNIPPET in live_text and not kp.get("snippet_in_live_checklist"):
        print("FAILED:SYN-0020-probe1 live snippet present but control missed it")
        return 1

    if not is_archive_lf_blob_prescription(
        "Verify formatting against the LF blob (git archive)."
    ):
        print("FAILED:SYN-0020-probe1 prescription detector missed the control line")
        return 1
    if is_archive_lf_blob_prescription(NEGATED_MENTION):
        print("FAILED:SYN-0020-probe1 negated mention counted as prescription")
        return 1

    readme = HERE / "fixtures" / "docs" / "README.md"
    got = extract_path(readme, REPO)
    if not any("SYN-0020-readme-ok" in c["invocation"] for c in got["commands"]):
        print("FAILED:SYN-0020-probe1 planted echo command not extracted")
        return 1
    if any(
        "syn0020-illustrative-must-not-run" in c["invocation"]
        for c in got["commands"]
    ):
        print("FAILED:SYN-0020-probe1 html-comment noexec leaked into executable set")
        return 1
    if any(
        "syn0020-fence-info-must-not-run" in c["invocation"]
        for c in got["commands"]
    ):
        print("FAILED:SYN-0020-probe1 fence-info noexec leaked into executable set")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0020-probe1 artifact missing")
        return 1
    art_text = ART.read_text(encoding="utf-8")
    doc = json.loads(art_text)
    if doc.get("unit_id") != UNIT_ID:
        print("FAILED:SYN-0020-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:SYN-0020-probe1 self-declared", doc.get("state"))
        return 1
    if COMPLETION_SENTINEL not in art_text:
        print("FAILED:SYN-0020-probe1 sentinel absent")
        return 1
    payload = domain(doc)
    art_kp = payload.get("known_present_control") or {}
    if art_kp.get("fired") is not True:
        print("FAILED:SYN-0020-probe1 artifact known_present_control.fired is not true")
        return 1
    art_fp = payload.get("fingerprint") or {}
    for key in (
        "known_present_fired",
        "contradict_git_archive_count",
        "noexec_both_states",
        "agree_without_test_id",
        "commands_extracted",
    ):
        if art_fp.get(key) != fp.get(key):
            print(
                f"FAILED:SYN-0020-probe1 fingerprint mismatch {key}: "
                f"art={art_fp.get(key)} live={fp.get(key)}"
            )
            return 1
    print("SUCCESS:SYN-0020-probe1 known-present CONTRADICT and noexec both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
