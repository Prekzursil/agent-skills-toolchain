#!/usr/bin/env python3
"""TST-0320 probe 2: idempotent cell writes + torn-row discard.

Independent of probe 1. Per-line schema is duplicated here (does not call
ledger.schema_errors as the pass predicate). Both-states controls:

  * honest append_cell of a completed cell does not grow the file
  * unsafe_always_append of the same cell does grow the file
  * planted newline-less JSON is discarded by the honest reader and counted
    by the naive parser
  * SIGKILL during atomic publish leaves a parseable published ledger
  * SIGKILL during naive in-place write produces a torn tail the honest
    reader discards
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from bench.cell import Cell  # noqa: E402
from bench.evaluate import evaluate_cell  # noqa: E402
from bench.ledger import (  # noqa: E402
    GENESIS_PREV,
    KIND,
    ResultsLedger,
    cells_from_corpus,
    inspect_published_bytes,
    load_corpus,
    make_record,
    naive_parse_including_torn,
    staging_paths,
    unsafe_direct_append,
)
from bench.runner import TournamentRunner  # noqa: E402

UNIT = "TST-0320"
CORPUS = REPO / "command-center" / "bench" / "cases" / "corpus.json"
KILL_TARGET = REPO / "tools" / "bench" / "kill_target.py"
ATOMIC_ITERS = 20
TS_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
# Duplicated on purpose: independent of ledger.REQUIRED.
PROBE2_REQUIRED = (
    "kind",
    "seq",
    "ts",
    "cell",
    "cell_id",
    "result",
    "prev_sha256",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def line_schema_errors(obj: object) -> list[str]:
    errs: list[str] = []
    if not isinstance(obj, dict):
        return ["not-object"]
    for key in PROBE2_REQUIRED:
        if key not in obj:
            errs.append(f"missing:{key}")
    if obj.get("kind") != KIND:
        errs.append("kind")
    seq = obj.get("seq")
    if type(seq) is not int or seq < 1:
        errs.append("seq")
    ts = obj.get("ts")
    if not isinstance(ts, str) or not TS_RE.match(ts):
        errs.append("ts")
    cell = obj.get("cell")
    if not isinstance(cell, dict):
        errs.append("cell")
    else:
        for key in ("candidate", "case", "harness_version", "seed"):
            if key not in cell:
                errs.append(f"cell.{key}")
    cid = obj.get("cell_id")
    if not isinstance(cid, str) or not SHA_RE.match(cid):
        errs.append("cell_id")
    result = obj.get("result")
    if not isinstance(result, dict):
        errs.append("result")
    prev = obj.get("prev_sha256")
    if not isinstance(prev, str) or not SHA_RE.match(prev):
        errs.append("prev_sha256")
    return errs


def schema_check_bytes(raw: bytes) -> dict:
    missing_nl = bool(raw) and not raw.endswith(b"\n")
    text = raw.decode("utf-8", errors="replace")
    if text.endswith("\n"):
        parts = text[:-1].split("\n")
    else:
        parts = text.split("\n") if text else []
    json_fail = 0
    schema_fail = 0
    ok = 0
    for part in parts:
        if part == "":
            json_fail += 1
            continue
        try:
            obj = json.loads(part)
        except json.JSONDecodeError:
            json_fail += 1
            continue
        if line_schema_errors(obj):
            schema_fail += 1
        else:
            ok += 1
    half = json_fail + schema_fail + (1 if missing_nl else 0)
    return {
        "missing_trailing_newline": missing_nl,
        "json_fail": json_fail,
        "schema_fail": schema_fail,
        "ok_lines": ok,
        "half_written": half,
        "line_count": len(parts),
    }


def kill_child(path: Path, mode: str, payload: int, chunk: int, delay_ms: float) -> int:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-B",
            str(KILL_TARGET),
            "--path",
            str(path),
            "--mode",
            mode,
            "--payload-bytes",
            str(payload),
            "--chunk-size",
            str(chunk),
            "--delay-ms",
            str(delay_ms),
            "--candidate",
            f"cand-{mode}",
            "--case",
            "case-kill",
        ],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    t0 = time.monotonic()
    before = path.stat().st_size if path.is_file() else 0
    while time.monotonic() - t0 < 2.5:
        if mode == "atomic" and staging_paths(path.parent):
            break
        if mode == "naive" and path.is_file() and path.stat().st_size > before:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.0004)
    if proc.poll() is None:
        time.sleep(0.001 if mode == "atomic" else 0.008)
        try:
            os.kill(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return proc.returncode if proc.returncode is not None else -9


def atomic_loop() -> dict:
    json_fail = 0
    schema_fail = 0
    missing_nl = 0
    ok_lines = 0
    ledgers = 0
    staging_hits = 0
    for _ in range(ATOMIC_ITERS):
        tmp = tempfile.mkdtemp(prefix="tst0320-p2a-")
        path = Path(tmp) / "results.jsonl"
        seed_cell = Cell("cand-seed", "case-seed", "tst-0320-h1", 320)
        ResultsLedger(path).append_cell(seed_cell, evaluate_cell(seed_cell))
        kill_child(path, "atomic", payload=65536, chunk=256, delay_ms=0.0)
        if staging_paths(Path(tmp)):
            staging_hits += 1
        raw = path.read_bytes() if path.is_file() else b""
        chk = schema_check_bytes(raw)
        json_fail += chk["json_fail"]
        schema_fail += chk["schema_fail"]
        missing_nl += 1 if chk["missing_trailing_newline"] else 0
        ok_lines += chk["ok_lines"]
        ledgers += 1
        try:
            for p in Path(tmp).iterdir():
                p.unlink()
            Path(tmp).rmdir()
        except OSError:
            pass
    return {
        "ledgers": ledgers,
        "json_fail": json_fail,
        "schema_fail": schema_fail,
        "missing_trailing_newline": missing_nl,
        "ok_lines": ok_lines,
        "half_written": json_fail + schema_fail + missing_nl,
        "staging_hits": staging_hits,
    }


def naive_kill_detector() -> dict:
    hits = 0
    trials = 8
    samples = []
    for _ in range(trials):
        tmp = tempfile.mkdtemp(prefix="tst0320-p2n-")
        path = Path(tmp) / "results.jsonl"
        seed_cell = Cell("cand-seed", "case-seed", "tst-0320-h1", 320)
        ResultsLedger(path).append_cell(seed_cell, evaluate_cell(seed_cell))
        kill_child(path, "naive", payload=4096, chunk=16, delay_ms=4.0)
        raw = path.read_bytes() if path.is_file() else b""
        chk = schema_check_bytes(raw)
        info = inspect_published_bytes(raw)
        torn = (
            chk["missing_trailing_newline"]
            or chk["json_fail"] > 0
            or chk["schema_fail"] > 0
            or info["torn_fragment"]
        )
        if torn:
            hits += 1
        samples.append(
            {
                "torn": torn,
                "missing_nl": chk["missing_trailing_newline"],
                "json_fail": chk["json_fail"],
                "honest_records": len(info["records"]),
                "bytes": len(raw),
            }
        )
        try:
            for p in Path(tmp).iterdir():
                p.unlink()
            Path(tmp).rmdir()
        except OSError:
            pass
    return {"trials": trials, "torn_hits": hits, "samples": samples}


def planted_torn_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0320-p2p-") as td:
        path = Path(td) / "results.jsonl"
        ledger = ResultsLedger(path)
        for i in range(3):
            cell = Cell("cand-plant", f"case-{i:02d}", "tst-0320-h1", 320)
            ledger.append_cell(cell, evaluate_cell(cell))
        raw_good = path.read_bytes()
        honest_good = inspect_published_bytes(raw_good)
        naive_good = naive_parse_including_torn(raw_good)

        extra_cell = Cell("cand-plant", "case-99", "tst-0320-h1", 320)
        extra = make_record(
            seq=4,
            prev_sha256=GENESIS_PREV,
            cell=extra_cell,
            result=evaluate_cell(extra_cell),
        )
        extra_line = json.dumps(extra, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        planted = raw_good + extra_line
        honest_bad = inspect_published_bytes(planted)
        naive_bad = naive_parse_including_torn(planted)

        truncated = raw_good + b'{"kind":"bench-result-v1","seq":4'
        honest_trunc = inspect_published_bytes(truncated)
        naive_trunc = naive_parse_including_torn(truncated)
    return {
        "good_honest_rows": len(honest_good["records"]),
        "good_naive_rows": len(naive_good["records"]),
        "good_torn": honest_good["torn_fragment"],
        "planted_honest_rows": len(honest_bad["records"]),
        "planted_naive_rows": len(naive_bad["records"]),
        "planted_naive_included_torn": naive_bad["included_torn"],
        "planted_honest_discarded": (
            len(honest_bad["records"]) == 3 and honest_bad["torn_fragment"] is True
        ),
        "trunc_honest_rows": len(honest_trunc["records"]),
        "trunc_naive_rows": len(naive_trunc["records"]),
        "trunc_honest_discarded": (
            len(honest_trunc["records"]) == 3 and honest_trunc["torn_fragment"] is True
        ),
        "silent_on_good": (
            len(honest_good["records"]) == 3 and not honest_good["torn_fragment"]
        ),
        "fired_on_planted": len(naive_bad["records"]) == 4
        and len(honest_bad["records"]) == 3,
    }


def idempotence_control() -> dict:
    cells = cells_from_corpus(load_corpus(CORPUS))
    with tempfile.TemporaryDirectory(prefix="tst0320-p2i-") as td:
        root = Path(td)
        honest = TournamentRunner(root / "honest", cells=cells)
        honest.run(session="full", resume=True)
        before = honest.ledger.row_count()
        refused = 0
        for cell in cells:
            out = honest.ledger.append_cell(cell, evaluate_cell(cell))
            if not out["appended"] and out["reason"] == "duplicate-cell":
                refused += 1
        after = honest.ledger.row_count()

        unsafe = TournamentRunner(root / "unsafe", cells=cells)
        unsafe.run(session="full", resume=True)
        unsafe_before = unsafe.ledger.row_count()
        grew = 0
        for cell in cells[:5]:
            out = unsafe.ledger.unsafe_always_append(cell, evaluate_cell(cell))
            if out["appended"]:
                grew += 1
        unsafe_after = unsafe.ledger.row_count()
        physical = unsafe.ledger_path.read_bytes().count(b"\n")
    return {
        "honest_before": before,
        "honest_after": after,
        "honest_refused": refused,
        "honest_grew": after != before,
        "unsafe_before": unsafe_before,
        "unsafe_after": unsafe_after,
        "unsafe_grew": unsafe_after > unsafe_before,
        "unsafe_extra": grew,
        "unsafe_physical_lines": physical,
    }


def main() -> int:
    loop = atomic_loop()
    plant = planted_torn_control()
    naive = naive_kill_detector()
    idem = idempotence_control()
    out = {
        "unit_id": UNIT,
        "probe": "probe2-idempotence-torn",
        "atomic_kill_loop": loop,
        "planted_truncation": plant,
        "naive_in_place_kill": naive,
        "idempotence": idem,
        "pass": (
            loop["ledgers"] == ATOMIC_ITERS
            and loop["half_written"] == 0
            and plant["silent_on_good"]
            and plant["fired_on_planted"]
            and plant["planted_honest_discarded"]
            and plant["trunc_honest_discarded"]
            and naive["torn_hits"] >= 1
            and (not idem["honest_grew"])
            and idem["honest_refused"] == idem["honest_before"]
            and idem["unsafe_grew"]
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"schema_half={loop['half_written']} planted={plant['fired_on_planted']} "
        f"naive_torn={naive['torn_hits']}/{naive['trials']} "
        f"honest_grew={idem['honest_grew']} unsafe_grew={idem['unsafe_grew']}"
    )
    if loop["ledgers"] != ATOMIC_ITERS:
        return fail(f"ledgers {loop['ledgers']}/{ATOMIC_ITERS}")
    if loop["half_written"] != 0:
        return fail(f"half_written={loop['half_written']}")
    if not plant["silent_on_good"] or not plant["fired_on_planted"]:
        return fail(f"planted control {plant}")
    if not plant["planted_honest_discarded"] or not plant["trunc_honest_discarded"]:
        return fail(f"honest reader did not discard torn {plant}")
    if naive["torn_hits"] < 1:
        return fail(f"naive detector did not fire {naive['samples']}")
    if idem["honest_grew"] or idem["honest_refused"] != idem["honest_before"]:
        return fail(f"idempotence honest {idem}")
    if not idem["unsafe_grew"]:
        return fail(f"unsafe append did not grow {idem}")
    print(
        f"SUCCESS:{UNIT}-probe2 idempotent cell writes; torn rows discarded; "
        "naive/planted controls fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
