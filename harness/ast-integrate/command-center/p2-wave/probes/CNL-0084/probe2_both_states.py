#!/usr/bin/env python3
"""Probe 2: both-states control, independent recount, ladder, negatives, schema.

Signal 1: detector.classify (fingerprint equality + DFS cycle).
Signal 2: independent JSON canonicalization of ledger fields plus Kahn's
algorithm on the await-graph (a different graph walk, a different data
projection). They must agree on FIRE vs SILENT.

Also: productive disagreement and stalled runtime stay SILENT for deadlock;
ladder rungs fire in order; the design note validates and carries SUCCESS:CNL-0084.
"""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from detector import classify_path, load_run  # noqa: E402

NOTE = REPO / "command-center" / "design" / "council" / "CNL-0084-deadlock-detection-and-the-escalation-ladder.md"
SCHEMA = REPO / "command-center" / "schema" / "council-design-note.schema.json"
LEDGER_KEYS = (
    "claim_ids",
    "evidence_hashes",
    "vote_tally",
    "dissent_brief_ids",
    "open_questions",
)


def independent_frozen(run: dict, stuck_n: int = 2) -> bool:
    windows = run.get("windows") or []
    if len(windows) < stuck_n:
        return False
    blobs = []
    for window in windows[-stuck_n:]:
        piece = {k: window.get(k) for k in LEDGER_KEYS}
        blobs.append(json.dumps(piece, sort_keys=True, separators=(",", ":")))
    return len(set(blobs)) == 1


def independent_cycle_kahn(awaiting: dict | None) -> bool:
    graph = {str(k): [str(x) for x in (v or [])] for k, v in (awaiting or {}).items()}
    nodes: set[str] = set(graph)
    for vs in graph.values():
        nodes.update(vs)
    if not nodes:
        return False
    indeg = {n: 0 for n in nodes}
    for src, vs in graph.items():
        for dst in vs:
            indeg[dst] = indeg.get(dst, 0) + 1
            indeg.setdefault(src, indeg.get(src, 0))
    q = deque([n for n, d in indeg.items() if d == 0])
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for dst in graph.get(n, []):
            indeg[dst] -= 1
            if indeg[dst] == 0:
                q.append(dst)
    return seen < len(nodes)


def independent_deadlocked(path: Path) -> dict:
    run = load_run(path)
    last = (run.get("windows") or [{}])[-1]
    expected = set(str(x) for x in (last.get("seats_expected") or []))
    returned: set[str] = set()
    for w in run.get("windows") or []:
        returned |= set(str(x) for x in (w.get("seats_returned") or []))
    missing = sorted(expected - returned)
    frozen = independent_frozen(run, int(run.get("stuck_windows") or 2))
    cyclic = independent_cycle_kahn(last.get("awaiting") or {})
    stopping = bool(last.get("stopping_satisfied"))
    turns = int(last.get("turns_emitted") or 0)
    min_turns = int(run.get("min_turns") or 2)
    deadlocked = (
        not stopping
        and not missing
        and turns >= min_turns
        and frozen
        and cyclic
    )
    return {
        "deadlocked": deadlocked,
        "frozen": frozen,
        "cyclic": cyclic,
        "missing": missing,
        "stopping": stopping,
    }


def expect_label(path: Path, want: str, errors: list[str]) -> dict:
    got = classify_path(path)
    if got["label"] != want:
        errors.append(f"{path.name} want={want} got={got['label']}")
    return got


def main() -> int:
    errors: list[str] = []
    good_p = HERE / "fixtures" / "known_good_slow_progress.json"
    bad_p = HERE / "fixtures" / "planted_bad_deadlock.json"
    dissent_p = HERE / "fixtures" / "productive_disagreement.json"
    stall_p = HERE / "fixtures" / "stalled_runtime.json"
    after_rec = HERE / "fixtures" / "ladder_after_recruit.json"
    after_rep = HERE / "fixtures" / "ladder_after_replace.json"
    after_ref = HERE / "fixtures" / "ladder_after_reframe.json"
    full = HERE / "fixtures" / "ladder_full_roster.json"

    good = expect_label(good_p, "PROGRESSING", errors)
    bad = expect_label(bad_p, "DEADLOCKED", errors)
    dissent = expect_label(dissent_p, "PROGRESSING", errors)
    stall = expect_label(stall_p, "STALLED_RUNTIME", errors)

    if good["fired"] or not good["silent"]:
        errors.append("known-good both-states: expected SILENT")
    if not bad["fired"] or bad["silent"]:
        errors.append("planted-bad both-states: expected FIRE")
    if dissent["fired"]:
        errors.append("productive disagreement declared deadlocked")
    if stall["fired"]:
        errors.append("stalled runtime declared deadlocked")

    ig = independent_deadlocked(good_p)
    ib = independent_deadlocked(bad_p)
    if ig["deadlocked"] != good["deadlocked"]:
        errors.append("independent recount disagrees on known-good")
    if ib["deadlocked"] != bad["deadlocked"]:
        errors.append("independent recount disagrees on planted-bad")
    if ig["deadlocked"]:
        errors.append("Kahn+canonicalization fired on known-good")
    if not ib["deadlocked"]:
        errors.append("Kahn+canonicalization silent on planted-bad")

    rec = classify_path(after_rec)
    rep = classify_path(after_rep)
    ref = classify_path(after_ref)
    ful = classify_path(full)
    want_rungs = {
        "planted-bad": (bad, "recruit"),
        "after-recruit": (rec, "replace"),
        "after-replace": (rep, "reframe"),
        "after-reframe": (ref, "escalate_to_owner"),
        "full-roster": (ful, "replace"),
    }
    for name, (verdict, rung) in want_rungs.items():
        got = (verdict.get("next_rung") or {}).get("rung")
        if got != rung:
            errors.append(f"ladder {name} want={rung} got={got}")
        if not verdict.get("deadlocked"):
            errors.append(f"ladder {name} not deadlocked")
    owner = ref.get("next_rung") or {}
    packet = owner.get("owner_packet") or {}
    if "UNRESOLVED" not in str(packet.get("recommendation") or ""):
        errors.append("owner packet missing UNRESOLVED recommendation")
    if not packet.get("default_if_silent"):
        errors.append("owner packet missing default_if_silent")
    if "May this council stop" not in str(packet.get("question") or ""):
        errors.append("owner packet is not one foundation-level question")

    if not NOTE.is_file() or NOTE.stat().st_size <= 0:
        errors.append("design note missing")
    else:
        text = NOTE.read_text(encoding="utf-8")
        if "SUCCESS:CNL-0084" not in text:
            errors.append("sentinel absent from design note")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"design note unparseable: {exc}")
            doc = None
        if isinstance(doc, dict):
            if str(doc.get("state") or "").upper() in {
                "BLOCKED",
                "FAILED",
                "SEVERED",
                "TIMEOUT",
            }:
                errors.append(f"self-declared {doc.get('state')}")
            schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
            try:
                jsonschema.validate(doc, schema)
            except jsonschema.ValidationError as exc:
                errors.append(f"schema: {exc.message}")
            garbage = [
                {},
                {"totally": "unrelated", "passing_tests": 999999},
                {"x": "x" * 2000},
            ]
            rejected = 0
            for g in garbage:
                try:
                    jsonschema.validate(g, schema)
                except jsonschema.ValidationError:
                    rejected += 1
            if rejected != 3:
                errors.append(f"schema accepts garbage ({rejected}/3 rejected)")

    payload = {
        "probe": "probe2_both_states",
        "unit_id": "CNL-0084",
        "both_states": {
            "known_good_silent": good["silent"],
            "planted_bad_fired": bad["fired"],
            "independent_known_good_deadlocked": ig["deadlocked"],
            "independent_planted_bad_deadlocked": ib["deadlocked"],
        },
        "negatives": {
            "productive_disagreement_label": dissent["label"],
            "stalled_runtime_label": stall["label"],
        },
        "ladder": {
            name: (verdict.get("next_rung") or {}).get("rung")
            for name, (verdict, _r) in want_rungs.items()
        },
        "owner_packet": packet,
        "pass": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))
    if errors:
        print("FAILED:CNL-0084-probe2 " + "; ".join(errors))
        return 1
    print(
        "both-states FIRE on planted-bad SILENT on known-good; "
        "Kahn recount agrees; productive-disagreement=PROGRESSING "
        "stalled=STALLED_RUNTIME; ladder recruit-replace-reframe-owner"
    )
    print("SUCCESS:CNL-0084-probe2 both-states independent-recount ladder negatives schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
