#!/usr/bin/env python3
"""TST-0041 event-schema and append-only conformance suite.

The verifier does not call tools/event-ledger/ledger.schema_errors. Seeding
and concurrent appends use LedgerWriter so the production publisher is what
is measured. Never mutates command-center/events/EVENTS.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER_DIR = REPO / "tools" / "event-ledger"
LIVE_REL = "command-center/events/EVENTS.jsonl"
LIVE = REPO / LIVE_REL
RUN_LEDGER_REL = "command-center/events/run-ledger.jsonl"
RUN_LEDGER = REPO / RUN_LEDGER_REL
UNIT = "TST-0041"
KIND = "run-ledger-v1"
GENESIS_PREV = "0" * 64
TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = (
    "kind",
    "seq",
    "ts",
    "actor",
    "unit_id",
    "phase",
    "from_state",
    "to_state",
    "correlation_id",
    "causality_id",
    "payload",
    "prev_sha256",
)


def encode_record(record: dict[str, Any]) -> bytes:
    text = json.dumps(record, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if "\n" in text or "\r" in text:
        raise ValueError("record JSON must be a single line")
    return (text + "\n").encode("utf-8")


def field_errors(obj: Any) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    if not isinstance(obj, dict):
        return [("record-object", "not-object")]
    missing = [k for k in REQUIRED if k not in obj]
    if missing:
        hits.append(("required-fields", "missing:" + ",".join(missing)))
    if obj.get("kind") != KIND:
        hits.append(("kind-run-ledger-v1", f"kind={obj.get('kind')!r}"))
    seq = obj.get("seq")
    if type(seq) is not int or seq < 1:
        hits.append(("seq-positive-int", f"seq={seq!r}"))
    ts = obj.get("ts")
    if not isinstance(ts, str) or not TS_RE.match(ts):
        hits.append(("ts-timezone", f"ts={ts!r}"))
    uid = obj.get("unit_id")
    if not isinstance(uid, str) or not uid.strip():
        hits.append(("unit-id-nonempty", f"unit_id={uid!r}"))
    for key in (
        "actor",
        "phase",
        "from_state",
        "to_state",
        "correlation_id",
        "causality_id",
    ):
        val = obj.get(key)
        if not isinstance(val, str) or not val:
            hits.append(("required-fields", f"empty:{key}"))
    if not isinstance(obj.get("payload"), dict):
        hits.append(("payload-object", f"payload={type(obj.get('payload')).__name__}"))
    prev = obj.get("prev_sha256")
    if not isinstance(prev, str) or not SHA_RE.match(prev):
        hits.append(("prev-sha256-format", f"prev={prev!r}"))
    return hits


def verify_log(raw: bytes) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    line_blobs: list[bytes] = []
    if not raw:
        return {
            "ok": True,
            "vacuous_empty": True,
            "violations": [],
            "rules_hit": [],
            "records": [],
            "line_count": 0,
            "parsed_ok": 0,
            "prefix_sha256": hashlib.sha256(b"").hexdigest(),
        }
    if not raw.endswith(b"\n"):
        violations.append(
            {
                "rule": "jsonl-complete-lines",
                "detail": "missing-trailing-newline",
                "line": None,
            }
        )
    parts = raw.split(b"\n")
    if raw.endswith(b"\n"):
        parts = parts[:-1]
    for i, part in enumerate(parts, 1):
        if part == b"":
            violations.append(
                {"rule": "jsonl-complete-lines", "detail": "empty-line", "line": i}
            )
            continue
        try:
            obj = json.loads(part.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            violations.append(
                {"rule": "record-object", "detail": type(exc).__name__, "line": i}
            )
            continue
        hits = field_errors(obj)
        for rule, detail in hits:
            violations.append({"rule": rule, "detail": detail, "line": i})
        if hits:
            continue
        records.append(obj)
        line_blobs.append(part + b"\n")

    expected = 1
    prev = GENESIS_PREV
    last_seq: int | None = None
    for rec, blob in zip(records, line_blobs):
        seq = rec["seq"]
        if last_seq is not None and seq < last_seq:
            violations.append(
                {
                    "rule": "seq-monotonic-consecutive",
                    "detail": f"decrease:{last_seq}->{seq}",
                    "line": expected,
                }
            )
        if seq != expected:
            violations.append(
                {
                    "rule": "seq-monotonic-consecutive",
                    "detail": f"seq:{seq}!={expected}",
                    "line": expected,
                }
            )
        if rec.get("prev_sha256") != prev:
            violations.append(
                {
                    "rule": "hash-chain",
                    "detail": f"chain-break-at-{expected}",
                    "line": expected,
                }
            )
        prev = hashlib.sha256(blob).hexdigest()
        last_seq = seq
        expected += 1

    rules_hit = sorted({v["rule"] for v in violations})
    return {
        "ok": not violations,
        "vacuous_empty": False,
        "violations": violations,
        "rules_hit": rules_hit,
        "records": records,
        "line_count": len(parts),
        "parsed_ok": len(records),
        "prefix_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _import_ledger():
    if str(LEDGER_DIR) not in sys.path:
        sys.path.insert(0, str(LEDGER_DIR))
    import ledger as L  # noqa: WPS433

    return L


def seed_n(path: Path, n: int, tag: str) -> None:
    writer = _import_ledger().LedgerWriter(path)
    for i in range(n):
        writer.append(
            actor="TST-0041-suite",
            unit_id=UNIT,
            phase="4",
            from_state="absent" if i == 0 else "appended",
            to_state="seeded" if i == 0 else "appended",
            correlation_id=f"{tag}-{i}",
            causality_id="suite",
            payload={"i": i, "tag": tag},
        )


def good_bytes(n: int = 3, tag: str = "good") -> bytes:
    tmp = Path(tempfile.mkdtemp(prefix="tst0041-good-"))
    path = tmp / "events.jsonl"
    seed_n(path, n, tag)
    raw = path.read_bytes()
    try:
        path.unlink()
        tmp.rmdir()
    except OSError:
        pass
    return raw


def tamper_first_record(raw: bytes) -> bytes:
    parts = raw.split(b"\n")
    if raw.endswith(b"\n"):
        parts = parts[:-1]
    if len(parts) < 2:
        raise ValueError("tamper requires at least two complete lines")
    rec = json.loads(parts[0].decode("utf-8"))
    payload = dict(rec.get("payload") or {})
    payload["tamper"] = "TST-0041-edit-earlier-line"
    rec["payload"] = payload
    rest = b"".join(p + b"\n" for p in parts[1:])
    return encode_record(rec) + rest


def reorder_first_two(raw: bytes) -> bytes:
    parts = raw.split(b"\n")
    if raw.endswith(b"\n"):
        parts = parts[:-1]
    if len(parts) < 2:
        raise ValueError("reorder requires at least two complete lines")
    parts = [parts[1], parts[0], *parts[2:]]
    return b"".join(p + b"\n" for p in parts)


def planted_interleave() -> bytes:
    first = encode_record(
        {
            "kind": KIND,
            "seq": 1,
            "ts": "2026-08-24T18:00:00Z",
            "actor": "a",
            "unit_id": UNIT,
            "phase": "4",
            "from_state": "a",
            "to_state": "b",
            "correlation_id": "a",
            "causality_id": "a",
            "payload": {"who": "a", "pad": "A" * 80},
            "prev_sha256": GENESIS_PREV,
        }
    )
    second = encode_record(
        {
            "kind": KIND,
            "seq": 2,
            "ts": "2026-08-24T18:00:01Z",
            "actor": "b",
            "unit_id": UNIT,
            "phase": "4",
            "from_state": "b",
            "to_state": "c",
            "correlation_id": "b",
            "causality_id": "b",
            "payload": {"who": "b", "pad": "B" * 80},
            "prev_sha256": "ab" * 32,
        }
    )
    return first[:40] + second[:40] + first[40:] + second[40:]


def _mutants_from_good(good: bytes) -> list[dict[str, Any]]:
    recs = [json.loads(p.decode("utf-8")) for p in good.split(b"\n")[:-1]]

    def recode(mutated: list[dict[str, Any]]) -> bytes:
        return b"".join(encode_record(r) for r in mutated)

    missing_unit = json.loads(json.dumps(recs[0]))
    del missing_unit["unit_id"]
    missing_seq = json.loads(json.dumps(recs[0]))
    del missing_seq["seq"]
    empty_unit = json.loads(json.dumps(recs[0]))
    empty_unit["unit_id"] = ""
    bad_ts = json.loads(json.dumps(recs[0]))
    bad_ts["ts"] = "2026-08-24 18:00:00"
    bad_payload = json.loads(json.dumps(recs[0]))
    bad_payload["payload"] = "not-an-object"
    dec_seq = json.loads(json.dumps(recs))
    if len(dec_seq) >= 2:
        dec_seq[1]["seq"] = 0
    dup_seq = json.loads(json.dumps(recs))
    if len(dup_seq) >= 2:
        dup_seq[1]["seq"] = dup_seq[0]["seq"]
    bad_prev = json.loads(json.dumps(recs))
    if len(bad_prev) >= 2:
        bad_prev[1]["prev_sha256"] = GENESIS_PREV
    return [
        {"id": "missing-unit-id", "rule": "unit-id-nonempty", "raw": encode_record(missing_unit)},
        {"id": "missing-seq", "rule": "required-fields", "raw": encode_record(missing_seq)},
        {"id": "empty-unit-id", "rule": "unit-id-nonempty", "raw": encode_record(empty_unit)},
        {"id": "ts-without-timezone", "rule": "ts-timezone", "raw": encode_record(bad_ts)},
        {"id": "payload-not-object", "rule": "payload-object", "raw": encode_record(bad_payload)},
        {"id": "seq-decrease", "rule": "seq-monotonic-consecutive", "raw": recode(dec_seq)},
        {"id": "seq-duplicate", "rule": "seq-monotonic-consecutive", "raw": recode(dup_seq)},
        {"id": "broken-hash-chain", "rule": "hash-chain", "raw": recode(bad_prev)},
        {"id": "missing-trailing-newline", "rule": "jsonl-complete-lines", "raw": good.rstrip(b"\n")},
        {"id": "non-json-line", "rule": "record-object", "raw": b"this is not json\n"},
        {"id": "tamper-earlier-line", "rule": "hash-chain", "raw": tamper_first_record(good)},
        {"id": "reorder-prior-events", "rule": "seq-monotonic-consecutive", "raw": reorder_first_two(good)},
        {"id": "planted-interleave", "rule": "record-object", "raw": planted_interleave()},
    ]


def mutant_fires(mutant: dict[str, Any], bad_v: dict[str, Any]) -> bool:
    if bad_v["ok"]:
        return False
    if mutant["id"] == "reorder-prior-events":
        return (
            "seq-monotonic-consecutive" in bad_v["rules_hit"]
            or "hash-chain" in bad_v["rules_hit"]
        )
    if mutant["id"] == "planted-interleave":
        return (
            "record-object" in bad_v["rules_hit"]
            or "jsonl-complete-lines" in bad_v["rules_hit"]
        )
    if mutant["rule"] in bad_v["rules_hit"]:
        return True
    return bool(bad_v["violations"])


def both_states() -> dict[str, Any]:
    good = good_bytes(3, "both")
    good_v = verify_log(good)
    rows = []
    for mutant in _mutants_from_good(good):
        bad_v = verify_log(mutant["raw"])
        fired = mutant_fires(mutant, bad_v)
        rows.append(
            {
                "id": mutant["id"],
                "rule": mutant["rule"],
                "silent_on_good": good_v["ok"],
                "fired_on_bad": fired,
                "bad_rules": bad_v["rules_hit"],
                "pass": bool(good_v["ok"] and fired),
            }
        )
    return {
        "good_ok": good_v["ok"],
        "good_parsed": good_v["parsed_ok"],
        "rows": rows,
        "all_pass": bool(good_v["ok"] and all(r["pass"] for r in rows)),
    }


def tamper_control() -> dict[str, Any]:
    good = good_bytes(3, "tamper")
    good_v = verify_log(good)
    bad = tamper_first_record(good)
    bad_v = verify_log(bad)
    return {
        "silent_on_good": good_v["ok"],
        "fired_on_bad": (not bad_v["ok"]) and ("hash-chain" in bad_v["rules_hit"]),
        "prefix_changed": good_v["prefix_sha256"] != bad_v["prefix_sha256"],
        "good_prefix": good_v["prefix_sha256"],
        "bad_prefix": bad_v["prefix_sha256"],
        "bad_rules": bad_v["rules_hit"],
        "pass": bool(
            good_v["ok"]
            and (not bad_v["ok"])
            and "hash-chain" in bad_v["rules_hit"]
            and good_v["prefix_sha256"] != bad_v["prefix_sha256"]
        ),
    }


def reorder_control() -> dict[str, Any]:
    good = good_bytes(3, "reorder")
    good_v = verify_log(good)
    bad = reorder_first_two(good)
    bad_v = verify_log(bad)
    fired = (not bad_v["ok"]) and (
        "seq-monotonic-consecutive" in bad_v["rules_hit"]
        or "hash-chain" in bad_v["rules_hit"]
    )
    return {
        "silent_on_good": good_v["ok"],
        "fired_on_bad": fired,
        "bad_rules": bad_v["rules_hit"],
        "pass": bool(good_v["ok"] and fired),
    }


def inspect_rel(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return {"path": rel, "present": False, "ok": False, "detail": "absent"}
    raw = path.read_bytes()
    v = verify_log(raw)
    return {
        "path": rel,
        "present": True,
        "bytes": len(raw),
        "ok": v["ok"],
        "parsed_ok": v["parsed_ok"],
        "line_count": v["line_count"],
        "seq": [r.get("seq") for r in v["records"]],
        "unit_ids": [r.get("unit_id") for r in v["records"]],
        "rules_hit": v["rules_hit"],
        "violations": v["violations"][:12],
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "detector_fired": (not v["ok"]) and bool(v["rules_hit"]),
    }


def live_log() -> dict[str, Any]:
    return inspect_rel(LIVE_REL)


def run_ledger_log() -> dict[str, Any]:
    return inspect_rel(RUN_LEDGER_REL)


def _append_one(path: Path, tag: str) -> None:
    _import_ledger().LedgerWriter(path).append(
        actor="TST-0041-conc",
        unit_id=UNIT,
        phase="4",
        from_state="appended",
        to_state="appended",
        correlation_id=f"conc-{tag}",
        causality_id="concurrent",
        payload={"tag": tag, "pad": "x" * 64},
    )


def _naive_chunk_write(path: Path, blob: bytes, chunk: int, delay_s: float) -> None:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        off = 0
        while off < len(blob):
            os.write(fd, blob[off : off + chunk])
            off += chunk
            if delay_s:
                time.sleep(delay_s)
    finally:
        os.close(fd)


def concurrent_atomic(writers: int = 8) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0041-ca-"))
    path = tmp / "events.jsonl"
    seed_n(path, 1, "conc-seed")
    procs: list[subprocess.Popen] = []
    for i in range(writers):
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    str(HERE / "suite.py"),
                    "append-one",
                    str(path),
                    str(i),
                ],
                cwd=str(REPO),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    codes = [p.wait(timeout=60) for p in procs]
    raw = path.read_bytes() if path.is_file() else b""
    v = verify_log(raw)
    try:
        path.unlink()
        tmp.rmdir()
    except OSError:
        pass
    torn = (not v["ok"]) and (
        "record-object" in v["rules_hit"] or "jsonl-complete-lines" in v["rules_hit"]
    )
    return {
        "writers": writers,
        "child_codes": codes,
        "parsed_ok": v["parsed_ok"],
        "line_count": v["line_count"],
        "ok": v["ok"],
        "rules_hit": v["rules_hit"],
        "torn": torn,
        "lost_updates_possible": v["parsed_ok"] < 1 + writers,
        "pass": bool(v["ok"] and v["parsed_ok"] >= 2 and not torn),
        "note": (
            "LedgerWriter publishes via os.replace of a complete snapshot. "
            "Concurrent appends may lose updates (last writer wins) but must "
            "not leave interleaved or torn JSONL."
        ),
    }


def concurrent_naive_or_planted() -> dict[str, Any]:
    planted = verify_log(planted_interleave())
    planted_fire = (not planted["ok"]) and (
        "record-object" in planted["rules_hit"]
        or "jsonl-complete-lines" in planted["rules_hit"]
    )
    naive_hits = 0
    samples = []
    trials = 3
    for i in range(trials):
        tmp = Path(tempfile.mkdtemp(prefix="tst0041-naive-"))
        path = tmp / "events.jsonl"
        path.write_bytes(b"")
        line_a = json.dumps({"who": "a", "pad": "A" * 1800, "i": i}, sort_keys=True)
        line_b = json.dumps({"who": "b", "pad": "B" * 1800, "i": i}, sort_keys=True)
        blob_a = (line_a + "\n").encode("utf-8")
        blob_b = (line_b + "\n").encode("utf-8")
        pa = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(HERE / "suite.py"),
                "naive-chunk",
                str(path),
                blob_a.hex(),
                "12",
                "0.002",
            ],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pb = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(HERE / "suite.py"),
                "naive-chunk",
                str(path),
                blob_b.hex(),
                "12",
                "0.002",
            ],
            cwd=str(REPO),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pa.wait(timeout=30)
        pb.wait(timeout=30)
        raw = path.read_bytes()
        v = verify_log(raw)
        torn = (not v["ok"]) and (
            "record-object" in v["rules_hit"]
            or "jsonl-complete-lines" in v["rules_hit"]
        )
        if torn:
            naive_hits += 1
        samples.append({"torn": torn, "bytes": len(raw), "rules": v["rules_hit"]})
        try:
            path.unlink()
            tmp.rmdir()
        except OSError:
            pass
    return {
        "planted_fired": planted_fire,
        "planted_rules": planted["rules_hit"],
        "naive_trials": trials,
        "naive_torn_hits": naive_hits,
        "naive_samples": samples,
        "pass": planted_fire,
    }


def run_all() -> dict[str, Any]:
    live = live_log()
    run_ledger = run_ledger_log()
    both = both_states()
    tamper = tamper_control()
    reorder = reorder_control()
    atomic = concurrent_atomic(8)
    naive = concurrent_naive_or_planted()
    live_ok_or_detected = bool(
        live.get("present")
        and (live.get("ok") or live.get("detector_fired"))
    )
    suite_ok = bool(
        both["all_pass"]
        and tamper["pass"]
        and reorder["pass"]
        and atomic["pass"]
        and not atomic["torn"]
        and naive["pass"]
        and live_ok_or_detected
    )
    return {
        "unit_id": UNIT,
        "ok": suite_ok,
        "live": live,
        "run_ledger": run_ledger,
        "both_states": both,
        "tamper": tamper,
        "reorder": reorder,
        "concurrent_atomic": atomic,
        "interleave_control": naive,
    }


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "append-one":
        _append_one(Path(argv[2]), argv[3])
        return 0
    if len(argv) >= 2 and argv[1] == "naive-chunk":
        _naive_chunk_write(
            Path(argv[2]), bytes.fromhex(argv[3]), int(argv[4]), float(argv[5])
        )
        return 0
    result = run_all()
    print(json.dumps(result, sort_keys=True, default=str))
    if not result["ok"]:
        print(f"FAILED:{UNIT}-suite")
        return 1
    print(
        f"live_ok={result['live']['ok']} tamper={result['tamper']['pass']} "
        f"reorder={result['reorder']['pass']} "
        f"atomic_torn={result['concurrent_atomic']['torn']} "
        f"both={result['both_states']['all_pass']}"
    )
    print(f"SUCCESS:{UNIT}-suite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
