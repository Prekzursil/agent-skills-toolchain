#!/usr/bin/env python3
"""Probe 2: independent 8x500 re-run, torn-tail repair, tamper naming, replay."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import event_log as elog  # noqa: E402

OUT = HERE / "probe2-integrity.json"
WRITERS = 8
EACH = 500
EXPECTED = WRITERS * EACH


def _torn_case(tmp: Path) -> dict:
    path = tmp / "torn.jsonl"
    for i in range(10):
        elog.append_record(path, {"verb": "seed", "i": i, "unit": "CC-0007"})
    before = elog.read_log(path)
    raw = path.read_bytes()
    # Cut the final record mid-line (keep a prefix so the file is non-empty).
    cut = max(len(raw) - 40, raw.rfind(b"\n", 0, len(raw) - 1) + 8)
    path.write_bytes(raw[:cut])
    torn = elog.read_log(path)
    report = elog.repair(path)
    after = elog.read_log(path)
    ok = (
        before.ok
        and before.parsed == 10
        and torn.torn_tail is True
        and torn.ok is False
        and report.records_lost >= 1
        and report.torn_tail_before is True
        and after.ok
        and after.parsed == report.intact_records
        and after.parsed < 10
    )
    return {
        "ok": ok,
        "before_parsed": before.parsed,
        "torn_tail_detected": torn.torn_tail,
        "torn_bytes": torn.torn_bytes,
        "records_lost": report.records_lost,
        "intact_after_repair": report.intact_records,
        "after_ok": after.ok,
        "after_parsed": after.parsed,
        "reader_did_not_silently_accept": torn.ok is False,
    }


def _tamper_case(tmp: Path) -> dict:
    path = tmp / "tamper.jsonl"
    for i in range(12):
        elog.append_record(path, {"verb": "seed", "i": i, "payload": "clean", "unit": "CC-0007"})
    lines = path.read_text(encoding="utf-8").splitlines()
    victim = json.loads(lines[5])  # seq=6 (1-based)
    victim["payload"] = "TAMPERED-MID-CHAIN"
    lines[5] = json.dumps(victim, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = elog.read_log(path)
    named = result.chain_break_name or ""
    ok = (
        result.ok is False
        and result.chain_break_at == 6
        and "seq=6" in named
        and result.intact_links == 5
        and result.parsed >= 6
    )
    report = elog.repair(path)
    after = elog.read_log(path)
    return {
        "ok": ok and after.ok and report.records_lost >= 1 and after.parsed == 5,
        "chain_break_at": result.chain_break_at,
        "chain_break_name": result.chain_break_name,
        "chain_break_reason": result.chain_break_reason,
        "intact_links_before_repair": result.intact_links,
        "records_lost": report.records_lost,
        "after_parsed": after.parsed,
        "after_ok": after.ok,
        "named_the_record": "seq=6" in named,
    }


def _replay_case(tmp: Path) -> dict:
    path = tmp / "replay.jsonl"
    for i in range(7):
        elog.append_record(path, {"verb": "seed", "i": i, "unit": "CC-0007"})
    first = elog.replay(path)
    second = elog.replay(path)
    ok = len(first) == 7 and len(second) == 7 and [r["hash"] for r in first] == [
        r["hash"] for r in second
    ]
    return {
        "ok": ok,
        "first_count": len(first),
        "second_count": len(second),
        "did_not_double_count": len(second) == len(first),
    }


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cc0007-probe2-"))
    # Independent reviewer arm: cold file, separate process from probe1.
    cold = tmp / "cold-EVENTS.jsonl"
    independent = elog.run_concurrent(cold, writers=WRITERS, each=EACH, timeout=160.0)
    independent_ok = (
        independent["all_workers_ok"]
        and independent["chain_ok"]
        and independent["parsed"] == EXPECTED
        and independent["intact_links"] == EXPECTED
        and independent["interleaved_lines"] == 0
        and all(v == EACH for v in independent["writer_counts"].values())
    )
    torn = _torn_case(tmp)
    tamper = _tamper_case(tmp)
    replay = _replay_case(tmp)
    ok = independent_ok and torn["ok"] and tamper["ok"] and replay["ok"]
    doc = {
        "probe": "probe2-integrity",
        "unit_id": "CC-0007",
        "pass": ok,
        "reviewer": {
            "role": "independent-cold-concurrency-rerun",
            "cold_path": independent["path"],
            "pass": independent_ok,
            "parsed": independent["parsed"],
            "intact_links": independent["intact_links"],
            "interleaved_lines": independent["interleaved_lines"],
            "wall_seconds": independent["wall_seconds"],
            "writer_counts": independent["writer_counts"],
        },
        "torn_write": torn,
        "tamper": tamper,
        "replay": replay,
        "platform": sys.platform,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print(
        f"independent_parsed={independent['parsed']} torn_lost={torn['records_lost']} "
        f"tamper_at={tamper['chain_break_at']} replay={replay['first_count']}/{replay['second_count']}"
    )
    if not ok:
        print("FAILED:CC-0007-probe2 integrity controls did not all pass")
        return 1
    print("SUCCESS:CC-0007-probe2 independent 8x500 + torn + tamper + replay")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
