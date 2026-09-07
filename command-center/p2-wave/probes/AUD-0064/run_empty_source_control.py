#!/usr/bin/env python3
"""AUD-0064 empty-source both-states control.

Classification basis: decoded event cardinality (lines, units_seen, recent).
mtimes are unused as an OK signal — stall detection from mtimes alone is banned.

GOOD state: populated transcript dir → OK
BAD/empty state: empty transcript dir → EMPTY
Mutant: nonempty-frame classifier that returns OK on empty source → must go red
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROBE = Path(__file__).resolve().parent
UNIT = "AUD-0064"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_events(transcript_dir: Path) -> dict[str, int]:
    """Decode event cardinality from *.jsonl under transcript_dir. No mtime use."""
    lines = 0
    units: set[str] = set()
    recent = 0
    if not transcript_dir.is_dir():
        return {"lines": 0, "units_seen": 0, "recent_count": 0}
    for path in sorted(transcript_dir.rglob("*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            lines += 1
            recent += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            unit = obj.get("unit_id") or obj.get("agent_id") or obj.get("id")
            if unit:
                units.add(str(unit))
    return {"lines": lines, "units_seen": len(units), "recent_count": recent}


def classify_cardinality(stats: dict[str, int]) -> str:
    if stats["lines"] == 0 and stats["units_seen"] == 0 and stats["recent_count"] == 0:
        return "EMPTY"
    if stats["lines"] > 0 and stats["units_seen"] > 0:
        return "OK"
    if stats["lines"] > 0:
        return "OK"
    return "EMPTY"


def mutant_nonempty_frame(stats: dict[str, int]) -> str:
    """Broken classifier: any nonempty *frame claim* (even fabricated) is OK.

    Demonstrates that a pane rendering a fixed nonempty frame over an empty
    source must go red — the control harness rejects this mutant.
    """
    del stats  # intentionally ignored — mutant does not look at cardinality
    return "OK"


def write(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def run_correct(empty_dir: Path, good_dir: Path) -> tuple[bool, str, dict[str, Any]]:
    empty_stats = count_events(empty_dir)
    good_stats = count_events(good_dir)
    empty_cls = classify_cardinality(empty_stats)
    good_cls = classify_cardinality(good_stats)
    fired = empty_cls == "EMPTY"
    silent = good_cls == "OK"
    ok = fired and silent
    lines = [
        "CONTROL: point a monitor classifier at an empty event source and require EMPTY,",
        "then verify a populated source is OK.",
        "classification_basis=decoded event cardinality (lines, units_seen, recent); mtimes unused",
        (
            f"EMPTY_LEG|lines={empty_stats['lines']}|units_seen={empty_stats['units_seen']}|"
            f"recent_count={empty_stats['recent_count']}|classification={empty_cls}|expected=EMPTY"
        ),
        (
            f"GOOD_LEG|lines={good_stats['lines']}|units_seen={good_stats['units_seen']}|"
            f"recent_count={good_stats['recent_count']}|classification={good_cls}|expected=OK"
        ),
        f"fired_on_bad_state={str(fired).lower()}",
        f"silent_on_good_state={str(silent).lower()}",
        f"{'PASS' if ok else 'FAIL'}:AUD-0064-empty-source-control",
    ]
    raw = "\n".join(lines) + "\n"
    doc = {
        "mode": "correct",
        "ok": ok,
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "empty": {"stats": empty_stats, "classification": empty_cls},
        "good": {"stats": good_stats, "classification": good_cls},
        "mtime_stall_used": False,
        "measured_at": utc_now(),
    }
    return ok, raw, doc


def run_mutant(empty_dir: Path) -> tuple[bool, str, dict[str, Any]]:
    """Return (mutant_caught, raw, doc). Mutant must exit red on empty source."""
    empty_stats = count_events(empty_dir)
    mutant_cls = mutant_nonempty_frame(empty_stats)
    expected = "EMPTY"
    caught = mutant_cls != expected  # mutant claims OK → caught
    # Control harness: if mutant claims OK on empty, fire exit 1
    fired = caught
    lines = [
        "NEGATIVE CONTROL: a non-empty-frame mutant must go red on the empty event source.",
        "mutant_rule=any fabricated nonempty frame is OK (cardinality ignored)",
        (
            f"EMPTY_LEG|lines={empty_stats['lines']}|units_seen={empty_stats['units_seen']}|"
            f"mutant_classification={mutant_cls}|expected={expected}"
        ),
        f"observed_exit_code={1 if fired else 0}",
        f"{'FAIL' if fired else 'PASS'}:AUD-0064-empty-source-mutant",
    ]
    raw = "\n".join(lines) + "\n"
    doc = {
        "mode": "mutant",
        "mutant_caught": fired,
        "mutant_classification": mutant_cls,
        "expected": expected,
        "empty_stats": empty_stats,
        "mtime_stall_used": False,
        "measured_at": utc_now(),
    }
    return fired, raw, doc


def seed_fixtures(root: Path) -> tuple[Path, Path]:
    empty = root / "empty"
    good = root / "populated"
    empty.mkdir(parents=True, exist_ok=True)
    good.mkdir(parents=True, exist_ok=True)
    # empty: no jsonl files
    (good / "agent-1.jsonl").write_text(
        json.dumps({"unit_id": "AUD-0064", "event": "start", "ts": utc_now()})
        + "\n"
        + json.dumps({"unit_id": "AUD-0064", "event": "progress", "ts": utc_now()})
        + "\n",
        encoding="utf-8",
    )
    return empty, good


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="AUD-0064 empty-source both-states control")
    ap.add_argument(
        "--mode",
        choices=["both", "correct", "mutant"],
        default="both",
        help="both=correct+mutant (default); correct=EMPTY vs OK; mutant=nonempty-frame red",
    )
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="aud0064-empty-src-") as tmp:
        empty_dir, good_dir = seed_fixtures(Path(tmp))
        correct_ok, correct_raw, correct_doc = run_correct(empty_dir, good_dir)
        mutant_caught, mutant_raw, mutant_doc = run_mutant(empty_dir)

    write(PROBE / "control-empty-source-good.raw.txt", correct_raw)
    write(PROBE / "control-empty-source-mutant.raw.txt", mutant_raw)

    both_ok = correct_ok and mutant_caught
    both_lines = [
        "AUD-0064 both-states empty-source control",
        "classification_basis=decoded event cardinality; mtimes unused",
        f"STATE_GOOD_EXIT={0 if correct_doc['silent_on_good_state'] else 1}",
        f"STATE_GOOD_SILENT={str(correct_doc['silent_on_good_state']).lower()}",
        f"STATE_BAD_EXIT={0 if not correct_doc['fired_on_bad_state'] else 1}",
        f"STATE_BAD_FIRED={str(correct_doc['fired_on_bad_state']).lower()}",
        f"NEGATIVE_CONTROL_CAN_GO_RED={str(mutant_caught).lower()}",
        f"CONTROL_PASS={str(both_ok).lower()}",
        f"{'SUCCESS' if both_ok else 'FAILED'}:AUD-0064-both-states-control",
    ]
    both_raw = "\n".join(both_lines) + "\n"
    write(PROBE / "control-both-states.raw.txt", both_raw)

    summary = {
        "unit_id": UNIT,
        "ok": both_ok,
        "correct": correct_doc,
        "mutant": mutant_doc,
        "mtime_stall_used": False,
        "classification_basis": "decoded event cardinality (lines, units_seen, recent); mtimes unused",
        "measured_at": utc_now(),
    }
    (PROBE / "control-both-states.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.mode == "correct":
        print(correct_raw, end="")
        return 0 if correct_ok else 1
    if args.mode == "mutant":
        print(mutant_raw, end="")
        # Mutant harness exits 1 when mutant is caught (goes red) — that is SUCCESS for the control
        return 1 if mutant_caught else 0

    print(both_raw, end="")
    return 0 if both_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
