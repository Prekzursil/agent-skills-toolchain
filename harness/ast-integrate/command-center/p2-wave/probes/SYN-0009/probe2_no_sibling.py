#!/usr/bin/env python3
"""Probe 2: SYN-0008 unread + independent reviewer re-derives first."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from denylist import posix  # noqa: E402
from reviewer import rederive  # noqa: E402
from schema_local import payload  # noqa: E402
from synthesizer import SIBLING_FIXTURE, SIBLING_LIVE, GuardedReader, run  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0009.raw-source-control.json"
LEAK_TOKEN = "never-read-syn-0008-candidates"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0009-probe2 {msg}")
    return 1


def main() -> int:
    # Reviewer MUST re-derive before this process opens the conclusion.
    derived = rederive(REPO)
    if derived.get("opened_output"):
        return fail("reviewer opened the unit conclusion")
    if not derived["known_present"] or not derived["exists_only_in_raw"]:
        return fail(f"reviewer missed known-present {derived}")
    if derived["digest_class_admitted"] != 0:
        return fail("reviewer inventory admitted digest-class")

    live = run(REPO, apply_deny=True)
    attempts = live["sibling_read_attempts"]
    if len(attempts) < 2:
        return fail(f"leak attempts missing {attempts}")
    results = {posix(a["path"]): a["result"] for a in attempts}
    if results.get(posix(SIBLING_LIVE)) != "DENIED":
        return fail(f"live SYN-0008 path not DENIED {results}")
    if results.get(posix(SIBLING_FIXTURE)) != "DENIED":
        return fail(f"fixture SYN-0008 path not DENIED {results}")
    for rec in live["read_log"]:
        if "SYN-0008" in rec.get("path", "") or "candidate-syntheses" in rec.get("path", ""):
            if rec.get("result") == "READ":
                return fail(f"read log contains sibling {rec}")
    if live["sibling_leak_present"]:
        return fail("leak token present under guard")

    sibling_fp = REPO / SIBLING_FIXTURE
    poison = sibling_fp.read_text(encoding="utf-8")
    if LEAK_TOKEN not in poison:
        return fail("fixture sibling missing leak token (control silent both states)")
    unguarded = sibling_fp.read_text(encoding="utf-8")
    if LEAK_TOKEN not in unguarded:
        return fail("unguarded sibling read lost the token")
    guarded = GuardedReader(REPO)
    denied = False
    try:
        guarded.request(SIBLING_FIXTURE)
    except Exception as exc:
        denied = "DENIED" in str(exc)
    if not denied:
        return fail("guarded request of sibling was not denied")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    body = payload(doc)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared {doc.get('state')}")
    if LEAK_TOKEN in text:
        return fail("artifact contains sibling leak token")
    kp = body.get("known_present_control") or {}
    if kp.get("fact_id") != derived["fact_id"] or kp.get("present") is not True:
        return fail("artifact known-present disagrees with reviewer re-derivation")
    if derived["source_path"] != kp.get("source_path"):
        return fail(
            f"source_path mismatch reviewer={derived['source_path']} artifact={kp.get('source_path')}"
        )
    art_attempts = body.get("sibling_read_attempts") or []
    if not any(a.get("result") == "DENIED" for a in art_attempts):
        return fail("artifact did not record DENIED sibling read")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if "SYN-0009-probe2" not in str(reviewer.get("reviewer_id") or ""):
        return fail("reviewer_id is not the independent probe2 reviewer")

    summary = {
        "reviewer_known_present": True,
        "reviewer_before_conclusion": True,
        "sibling_denied": True,
        "unguarded_token_present": True,
        "artifact_clean_of_leak": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "reviewer_first=True sibling_denied=True "
        f"source={derived['source_path']}"
    )
    print("SUCCESS:SYN-0009-probe2 no-sibling-read and independent reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
