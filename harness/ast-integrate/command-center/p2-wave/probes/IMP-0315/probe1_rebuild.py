#!/usr/bin/env python3
"""Named probe 1: rebuild five recorded councils from their logs.

For each recorded council:
  * rebuild_from_log(events.jsonl) byte-equals the original artifact.json
  * a second rebuild is byte-identical to the first (deterministic replay)
  * derived views (transcript, votes, confidence, minority) are non-empty
    where the recording put events of that kind

Also live-records a pause/resume on a temp log and asserts the post-resume
artifact matches a straight-through recording of the same spec.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import fixture_root, record_one, specs, write_fixtures  # noqa: E402
from tools.council.artifacts.store import (  # noqa: E402
    EventStore,
    rebuild_from_log,
    replay_from_log,
)

ART = REPO / "command-center/receipts/IMP-0315.json"
STORE = REPO / "tools/council/artifacts/store.py"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable: {exc}"
    if "SUCCESS:IMP-0315" not in text:
        return "sentinel absent"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if doc.get("unit_id") != "IMP-0315":
        return f"unit_id {doc.get('unit_id')}"
    return None


def main() -> int:
    if not STORE.is_file():
        print("FAILED:IMP-0315-probe1 store.py missing")
        return 1
    rec_err = _check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0315-probe1 {rec_err}")
        return 1

    root = fixture_root()
    write_fixtures(root)

    rows = []
    for spec in specs():
        log = root / spec["id"] / "events.jsonl"
        original = (root / spec["id"] / "artifact.json").read_bytes()
        rebuilt = rebuild_from_log(log)
        replayed = replay_from_log(log)
        store = EventStore(log)
        views = store.views()
        art = store.artifact()
        match = rebuilt == original
        replay_ok = replayed == rebuilt
        rows.append(
            {
                "id": spec["id"],
                "events": art["event_count"],
                "original_sha256": _digest(original),
                "rebuild_sha256": _digest(rebuilt),
                "byte_identical": match,
                "replay_identical": replay_ok,
                "status": art["status"],
                "decision_kind": (art.get("decision") or {}).get("kind"),
                "transcript_n": len(views["transcript"]),
                "votes_n": len(views["vote_history"]),
                "confidence_n": len(views["confidence_trajectory"]),
                "minority_n": len(views["minority_report"]),
            }
        )
        if not match or not replay_ok:
            print(f"FAILED:IMP-0315-probe1 rebuild mismatch {spec['id']}")
            print(json.dumps(rows[-1], indent=2))
            return 1
        if art["status"] != "completed":
            print(f"FAILED:IMP-0315-probe1 status={art['status']} id={spec['id']}")
            return 1
        if not views["transcript"] or not views["vote_history"] or not views["confidence_trajectory"]:
            print(f"FAILED:IMP-0315-probe1 empty derived view {spec['id']}")
            return 1

    split = next(r for r in rows if r["id"] == "c-split-dissent")
    if split["minority_n"] < 1:
        print("FAILED:IMP-0315-probe1 dissent lost on rebuild")
        return 1
    node = next(r for r in rows if r["id"] == "c-no-decision")
    if node["decision_kind"] != "NO-DECISION":
        print("FAILED:IMP-0315-probe1 NO-DECISION coerced")
        return 1
    dip = next(r for r in rows if r["id"] == "c-confidence-dip")
    if dip["confidence_n"] < 6:
        print("FAILED:IMP-0315-probe1 confidence trajectory truncated")
        return 1

    pause_spec = next(s for s in specs() if s["id"] == "c-pause-resume")
    with tempfile.TemporaryDirectory(prefix="imp0315-p1-") as tmp:
        tmp_p = Path(tmp)
        live = record_one(tmp_p / "live.jsonl", pause_spec)
        # Re-open as a new instance (process-equivalent: no borrowed fold).
        resumed = EventStore(tmp_p / "live.jsonl")
        if resumed.artifact_bytes() != live:
            print("FAILED:IMP-0315-probe1 reopen after pause/resume diverged")
            return 1
        events = resumed.events()
        kinds = [e["kind"] for e in events]
        if "council.paused" not in kinds or "council.resumed" not in kinds:
            print("FAILED:IMP-0315-probe1 pause/resume events missing")
            return 1
        pause_at = kinds.index("council.paused")
        prefix = events[: pause_at + 1]
        # Fold of the paused prefix must restore round-1 votes.
        from tools.council.artifacts.store import artifact_from_state, fold_events

        paused_state = fold_events(prefix)
        if paused_state["status"] != "paused":
            print(f"FAILED:IMP-0315-probe1 prefix status={paused_state['status']}")
            return 1
        if len(paused_state["votes"]) != 3:
            print(f"FAILED:IMP-0315-probe1 paused votes={len(paused_state['votes'])}")
            return 1
        resumed_art = artifact_from_state(fold_events(events))
        if len(resumed_art["vote_history"]) != 6:
            print("FAILED:IMP-0315-probe1 resume dropped round-1 votes")
            return 1

    if len(rows) != 5:
        print(f"FAILED:IMP-0315-probe1 n={len(rows)} want=5")
        return 1

    out = {
        "pass": True,
        "probe": "probe1-rebuild-from-log",
        "unit_id": "IMP-0315",
        "councils": rows,
        "all_byte_identical": all(r["byte_identical"] and r["replay_identical"] for r in rows),
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0315-probe1 rebuild from log on 5 recorded councils")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
