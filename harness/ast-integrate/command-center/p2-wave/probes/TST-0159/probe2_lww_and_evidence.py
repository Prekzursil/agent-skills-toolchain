#!/usr/bin/env python3
"""Probe 2: independent hash/event-log evidence and last-write-wins mutant.

Does not reuse probe1's tempdir. Recomputes receipt hashes from disk bytes
and scans the event log for a DUPLICATE-COMPLETION that names the suppressed
write. Last-write-wins must fail that predicate.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402
from write_once_store import DUPLICATE_COMPLETION, sha256_path  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0159.json"
SENTINEL = "SUCCESS:TST-0159"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0159-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0159-probe2 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0159-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0159-probe2 self-declared:{st}")
        return 1
    ev = doc.get("evidence") or []
    if len(ev) < 2:
        print("FAILED:TST-0159-probe2 receipt missing two evidence signals")
        return 1
    neg = doc.get("negative_control") or {}
    if neg.get("ok") is not True:
        print("FAILED:TST-0159-probe2 receipt negative_control.ok is not true")
        return 1
    return 0


def _independent_fn_evidence(root: Path) -> dict:
    """Re-run the completed-then-retry path and hash/scan without store helpers."""
    fn = S.run_false_negative_timeout(root, last_write_wins=False)
    rec_path = root / "receipts" / f"{S.UNIT_COMPLETED}.json"
    log_path = root / "events.jsonl"
    disk_hash = sha256_path(rec_path)
    named = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("kind") != DUPLICATE_COMPLETION:
            continue
        if ev.get("unit_id") != S.UNIT_COMPLETED:
            continue
        suppressed = ev.get("suppressed_write") or {}
        if suppressed.get("reason") == "false-negative-timeout-retry":
            named.append(
                {
                    "seq": ev.get("seq"),
                    "existing_hash": ev.get("existing_hash"),
                    "suppressed_reason": suppressed.get("reason"),
                    "suppressed_result": suppressed.get("result"),
                }
            )
    independent_ok = (
        disk_hash == fn.get("hash_before") == fn.get("hash_after")
        and len(named) == 1
        and named[0]["existing_hash"] == disk_hash
        and named[0]["suppressed_result"] == S.RETRY_BODY["result"]
    )
    return {
        "disk_hash": disk_hash,
        "hash_before": fn.get("hash_before"),
        "hash_after": fn.get("hash_after"),
        "named_suppressed": named,
        "independent_ok": independent_ok,
        "fn": fn,
    }


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="tst0159-p2-") as tmp:
        base = Path(tmp)
        evidence = _independent_fn_evidence(base / "fn")
        lww = S.run_last_write_wins_must_fail(base / "lww")

    payload = {
        "probe": "probe2-lww-and-evidence",
        "unit_id": "TST-0159",
        "independent_ok": evidence.get("independent_ok"),
        "disk_hash": evidence.get("disk_hash"),
        "named_suppressed_count": len(evidence.get("named_suppressed") or []),
        "lww_ok": lww.get("ok"),
        "lww_write_once_holds": lww.get("write_once_holds"),
        "lww_hashes_equal": lww.get("hashes_equal"),
        "pass": bool(evidence.get("independent_ok") and lww.get("ok")),
    }
    print(json.dumps(payload, sort_keys=True))
    if not evidence.get("independent_ok"):
        print("FAILED:TST-0159-probe2 independent hash/event-log evidence")
        return 1
    if not lww.get("ok"):
        print("FAILED:TST-0159-probe2 last-write-wins did not fail write-once")
        return 1
    art = json.loads(ART.read_text(encoding="utf-8"))
    art_hash = (
        (art.get("both_states") or {})
        .get("false_negative_timeout", {})
        .get("hash_before")
    )
    if art_hash != evidence.get("disk_hash"):
        print(
            f"FAILED:TST-0159-probe2 hash drift receipt={art_hash} "
            f"live={evidence.get('disk_hash')}"
        )
        return 1
    art_lww = (art.get("negative_control") or {}).get("last_write_wins") or {}
    if art_lww.get("detector_fired_on_lww") is not True:
        print("FAILED:TST-0159-probe2 artifact LWW detector claim missing")
        return 1
    print(
        "disk=%s named=%s lww_fired=%s lww_holds=%s"
        % (
            evidence.get("disk_hash"),
            len(evidence.get("named_suppressed") or []),
            lww.get("detector_fired_on_lww"),
            lww.get("write_once_holds"),
        )
    )
    print(
        "SUCCESS:TST-0159-probe2 hashes unchanged, DUPLICATE-COMPLETION named "
        "the suppressed write, last-write-wins failed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
